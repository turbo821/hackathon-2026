from datetime import date
from typing import Literal
from collections import defaultdict

from fastapi import APIRouter, Query
from sqlalchemy import and_, delete, or_, select
from sqlalchemy.orm import Session, joinedload

from app.auth import DB, CurrentUser
from app.errors import ApiError
from app.models import PaymentOccurrence, RecurringPayment
from app.models.payment_occurrence import (
    PAID_SOURCE_SITE,
    STATE_OVERDUE,
    STATE_PAID,
    STATE_PAID_LATE,
    STATE_PENDING,
    STATUS_PAID,
    STATUS_UNPAID,
)
from app.schemas.payments import Currency, OccurrenceOut, OccurrenceUpdate, Status
from app.services.periods import ensure_all_occurrences, ensure_occurrences
from app.services.serializers import occurrence_to_dict
from app.timeutils import today

router = APIRouter(prefix="/payment-occurrences", tags=["payment-occurrences"])

StateFilter = Literal["pending", "overdue", "paid", "paid_late", "unpaid_all"]


def _state_filter(state: str, on: date):
    O = PaymentOccurrence
    if state == STATE_PENDING:
        return and_(O.status == STATUS_UNPAID, O.due_date >= on)
    if state == STATE_OVERDUE:
        return and_(O.status == STATUS_UNPAID, O.due_date < on)
    if state == STATE_PAID:
        return and_(
            O.status == STATUS_PAID, or_(O.paid_at.is_(None), O.paid_at <= O.due_date)
        )
    if state == STATE_PAID_LATE:
        return and_(O.status == STATUS_PAID, O.paid_at > O.due_date)
    return O.status == STATUS_UNPAID  # unpaid_all

def _clean_occurrences(
    db: Session,
    recurring_payment_id: int | None = None,
    protect_id: int | None = None,
) -> int:
    """Удаляет из БД «лишние» периоды (см. правило в исходной реализации).

    protect_id — ID периода, который удалять нельзя. Используется в
    update_occurrence, чтобы клиент не получил 404, если чистка удалила
    бы запись, которую он только что обновил. Инвариант «U, P сверху»
    при этом восстанавливается при следующем чтении списка.
    """
    q = select(
        PaymentOccurrence.id,
        PaymentOccurrence.recurring_payment_id,
        PaymentOccurrence.status,
        PaymentOccurrence.due_date,
    )
    if recurring_payment_id is not None:
        q = q.where(
            PaymentOccurrence.recurring_payment_id == recurring_payment_id
        )
    q = q.order_by(
        PaymentOccurrence.recurring_payment_id,
        PaymentOccurrence.due_date.desc(),
        PaymentOccurrence.id.desc(),
    )

    by_payment: dict[int, list] = defaultdict(list)
    for row in db.execute(q).all():
        by_payment[row.recurring_payment_id].append(row)

    to_delete: list[int] = []
    for occs in by_payment.values():
        paid = [o for o in occs if o.status == STATUS_PAID]

        if not paid:
            earliest = occs[-1]
            to_delete.extend(
                o.id
                for o in occs
                if o.id != earliest.id and o.id != protect_id
            )
            continue

        latest_paid = paid[0]
        unpaid_after = [
            o
            for o in occs
            if o.status == STATUS_UNPAID and o.due_date > latest_paid.due_date
        ]
        if not unpaid_after:
            continue

        first_unpaid = unpaid_after[-1]
        to_delete.extend(
            o.id
            for o in unpaid_after
            if o.due_date > first_unpaid.due_date and o.id != protect_id
        )

    if to_delete:
        db.execute(
            delete(PaymentOccurrence).where(PaymentOccurrence.id.in_(to_delete))
        )
        db.flush()
    return len(to_delete)

def _get_occurrence(db: Session, occurrence_id: int) -> PaymentOccurrence:
    occ = db.get(
        PaymentOccurrence,
        occurrence_id,
        options=[joinedload(PaymentOccurrence.marked_by)],
        populate_existing=True,
    )
    if occ is None:
        raise ApiError(404, "Платёж не найден")
    return occ
@router.get(
    "",
    response_model=list[OccurrenceOut],
    summary="Получение списка платежей, оплаченные и просроченные",
)
def list_occurrences(
    db: DB,
    user: CurrentUser,
    state: StateFilter | None = Query(
        None,
        description="pending / overdue / paid / paid_late / unpaid_all (= pending + overdue)",
    ),
    status: Status | None = None,
    currency: Currency | None = None,
    recurring_payment_id: int | None = None,
    date_from: date | None = Query(None, description="Срок оплаты с (включительно)"),
    date_to: date | None = Query(None, description="Срок оплаты по (включительно)"),
    include_inactive: bool = Query(
        True, description="Включать периоды прекращённых платежей"
    ),
    include_future: bool = Query(
        True, description="Включать ещё не наступившие периоды"
    ),
    order: Literal["asc", "desc"] = "desc",
):
    """Каждый элемент — конкретный период регулярного платежа со своим сроком и статусом.

    Период хранит слепок полей платежа, поэтому список читается по одной таблице.
    """
    on = today()
    ensure_all_occurrences(db, on)
    _clean_occurrences(db)

    query = select(PaymentOccurrence).options(joinedload(PaymentOccurrence.marked_by))
    if state:
        query = query.where(_state_filter(state, on))
    if status:
        query = query.where(PaymentOccurrence.status == status)
    if currency:
        query = query.where(PaymentOccurrence.currency == currency)
    if recurring_payment_id:
        query = query.where(
            PaymentOccurrence.recurring_payment_id == recurring_payment_id
        )
    if date_from:
        query = query.where(PaymentOccurrence.due_date >= date_from)
    if date_to:
        query = query.where(PaymentOccurrence.due_date <= date_to)
    if not include_inactive:
        query = query.where(PaymentOccurrence.payment_ended_at.is_(None))
    if not include_future:
        query = query.where(PaymentOccurrence.due_date <= on)

    due = (
        PaymentOccurrence.due_date.desc()
        if order == "desc"
        else PaymentOccurrence.due_date.asc()
    )
    items = db.scalars(query.order_by(due, PaymentOccurrence.name)).all()
    return [occurrence_to_dict(o, on) for o in items]


@router.get(
    "/{occurrence_id}",
    response_model=OccurrenceOut,
    summary="Получение конкретного платежа",
    responses={404: {"description": "Платёж не найден"}},
)
def get_occurrence(occurrence_id: int, db: DB, user: CurrentUser):
    return occurrence_to_dict(_get_occurrence(db, occurrence_id), today())


@router.patch(
    "/{occurrence_id}",
    response_model=OccurrenceOut,
    summary="Подтверждение или отмена оплаты, исправление фактической даты оплаты",
    responses={
        404: {"description": "Платёж не найден"},
        409: {"description": "Нельзя исправить дату у неоплаченного периода"},
    },
)
def update_occurrence(
    occurrence_id: int, data: OccurrenceUpdate, db: DB, user: CurrentUser
):
    """
    - {"status": "paid"} — оплачено сегодня;
    - {"status": "paid", "paid_at": "2026-10-20"} — оплачено в указанную дату;
    - {"paid_at": "2026-10-19"} — исправить дату у оплаченного периода
      (просрочка пересчитывается, срок не меняется);
    - {"status": "unpaid"} — отменить отметку, дата очищается.

    Доступно и администратору, и пользователю.
    """
    fields = data.model_fields_set
    occ = _get_occurrence(db, occurrence_id)
    on = today()

    if "status" not in fields and occ.status != STATUS_PAID:
        raise ApiError(
            409, "Сначала отметьте оплату (status=paid), потом исправляйте дату"
        )
    new_status = data.status if "status" in fields and data.status else occ.status
    if new_status == STATUS_PAID:
        if "paid_at" in fields and data.paid_at is None:
            raise ApiError(422, "Для оплаченного периода нужна дата оплаты")
        occ.status = STATUS_PAID
        occ.paid_at = data.paid_at or occ.paid_at or on
        occ.marked_by_id = user.id
        occ.paid_source = PAID_SOURCE_SITE
    else:
        occ.status = STATUS_UNPAID
        occ.paid_at = None
        occ.marked_by_id = None
        occ.paid_source = None

    db.flush()
    # Оплатили текущий период заранее → сразу появится следующий
    payment = db.get(RecurringPayment, occ.recurring_payment_id)
    if payment is not None:
        ensure_occurrences(db, payment, on)
    _clean_occurrences(db, occ.recurring_payment_id, protect_id=occurrence_id)  # <-- только затронутый шаблон
    db.commit()
    return occurrence_to_dict(_get_occurrence(db, occurrence_id), on)