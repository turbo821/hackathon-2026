from flask import g
from flask.views import MethodView
from flask_smorest import Blueprint, abort
from sqlalchemy import and_, or_
from sqlalchemy.orm import joinedload

from app.auth import login_required
from app.extensions import db
from app.logging_config import get_logger
from app.models import PaymentOccurrence, RecurringPayment
from app.models.payment_occurrence import (
    STATE_OVERDUE,
    STATE_PAID,
    STATE_PAID_LATE,
    STATE_PENDING,
    STATUS_PAID,
    STATUS_UNPAID,
)
from app.schemas.payments import OccurrenceQuerySchema, OccurrenceSchema, OccurrenceUpdateSchema
from app.services.audit import audit
from app.services.periods import ensure_all_occurrences, ensure_occurrences
from app.services.serializers import occurrence_to_dict
from app.timeutils import today

logger = get_logger(__name__)

router = Blueprint(
    "payment_occurrences",
    __name__,
    url_prefix="/api/v1/payment-occurrences",
    description="Периоды платежей: что и когда оплатить, что оплачено и что просрочено",
)


def _state_filter(state: str, on):
    O = PaymentOccurrence
    if state == STATE_PENDING:
        return and_(O.status == STATUS_UNPAID, O.due_date >= on)
    if state == STATE_OVERDUE:
        return and_(O.status == STATUS_UNPAID, O.due_date < on)
    if state == STATE_PAID:
        return and_(O.status == STATUS_PAID, or_(O.paid_at.is_(None), O.paid_at <= O.due_date))
    if state == STATE_PAID_LATE:
        return and_(O.status == STATUS_PAID, O.paid_at > O.due_date)
    if state == "unpaid_all":
        return O.status == STATUS_UNPAID
    raise ValueError(state)


def _get_occurrence(occurrence_id: int) -> PaymentOccurrence:
    occ = db.session.get(
        PaymentOccurrence,
        occurrence_id,
        options=[
            joinedload(PaymentOccurrence.recurring_payment),
            joinedload(PaymentOccurrence.marked_by),
        ],
    )
    if occ is None:
        abort(404, message="Платёж не найден")
    return occ


@router.route("")
class OccurrenceList(MethodView):
    @login_required
    @router.arguments(OccurrenceQuerySchema, location="query")
    @router.response(200, OccurrenceSchema(many=True))
    def get(self, args):
        """Получение списка платежей, оплаченные и просроченные

        Каждый элемент — конкретный период регулярного платежа со своим сроком и статусом.
        Фильтры: `state` (pending / overdue / paid / paid_late / unpaid_all), `status`,
        `currency`, `recurring_payment_id`, `date_from`, `date_to`.
        """
        on = today()
        ensure_all_occurrences(on)

        query = PaymentOccurrence.query.join(RecurringPayment).options(
            joinedload(PaymentOccurrence.recurring_payment),
            joinedload(PaymentOccurrence.marked_by),
        )
        if args.get("state"):
            query = query.filter(_state_filter(args["state"], on))
        if args.get("status"):
            query = query.filter(PaymentOccurrence.status == args["status"])
        if args.get("currency"):
            query = query.filter(RecurringPayment.currency == args["currency"])
        if args.get("recurring_payment_id"):
            query = query.filter(
                PaymentOccurrence.recurring_payment_id == args["recurring_payment_id"]
            )
        if args.get("date_from"):
            query = query.filter(PaymentOccurrence.due_date >= args["date_from"])
        if args.get("date_to"):
            query = query.filter(PaymentOccurrence.due_date <= args["date_to"])
        if not args["include_inactive"]:
            query = query.filter(RecurringPayment.is_active.is_(True))
        if not args["include_future"]:
            query = query.filter(PaymentOccurrence.due_date <= on)

        order = PaymentOccurrence.due_date.desc() if args["order"] == "desc" else PaymentOccurrence.due_date.asc()
        items = query.order_by(order, RecurringPayment.name).all()
        return [occurrence_to_dict(o, on) for o in items]


@router.route("/<int:occurrence_id>")
class OccurrenceItem(MethodView):
    @login_required
    @router.response(200, OccurrenceSchema)
    @router.alt_response(404, description="Платёж не найден")
    def get(self, occurrence_id):
        """Получение конкретного платежа"""
        return occurrence_to_dict(_get_occurrence(occurrence_id), today())

    @login_required
    @router.arguments(OccurrenceUpdateSchema)
    @router.response (200, OccurrenceSchema)
    @router.alt_response(404, description="Платёж не найден")
    @router.alt_response(409, description="Нельзя исправить дату у неоплаченного периода")
    def patch(self, data, occurrence_id):
        """Подтверждение или отмена оплаты, исправление фактической даты оплаты

        - `{"status": "paid"}` — оплачено сегодня;
        - `{"status": "paid", "paid_at": "2026-10-20"}` — оплачено в указанную дату;
        - `{"paid_at": "2026-10-19"}` — исправить дату у оплаченного периода
          (просрочка пересчитывается, срок не меняется);
        - `{"status": "unpaid"}` — отменить отметку, дата очищается.

        Доступно и администратору, и пользователю.
        """
        occ = _get_occurrence(occurrence_id)
        on = today()
        user = g.current_user
        before = {"status": occ.status, "paid_at": occ.paid_at.isoformat() if occ.paid_at else None}

        if "status" not in data and occ.status != STATUS_PAID:
            abort(409, message="Сначала отметьте оплату (status=paid), потом исправляйте дату")

        new_status = data.get("status", occ.status)
        if new_status == STATUS_PAID:
            if "paid_at" in data and data["paid_at"] is None:
                abort(422, message="Для оплаченного периода нужна дата оплаты")
            occ.status = STATUS_PAID
            occ.paid_at = data.get("paid_at") or occ.paid_at or on
            occ.marked_by_id = user.id
        else:
            occ.status = STATUS_UNPAID
            occ.paid_at = None
            occ.marked_by_id = None

        after = {"status": occ.status, "paid_at": occ.paid_at.isoformat() if occ.paid_at else None}
        if before != after:
            action = {
                (STATUS_UNPAID, STATUS_PAID): "occurrence.mark_paid",
                (STATUS_PAID, STATUS_UNPAID): "occurrence.mark_unpaid",
            }.get((before["status"], after["status"]), "occurrence.change_paid_at")
            audit(
                action,
                user=user,
                entity_type="payment_occurrence",
                entity_id=occ.id,
                details={
                    "payment": occ.recurring_payment.name,
                    "due_date": occ.due_date.isoformat(),
                    "before": before,
                    "after": after,
                },
            )

        db.session.flush()
        # Оплатили текущий период заранее → сразу появится следующий
        ensure_occurrences(occ.recurring_payment, on)
        db.session.commit()
        return occurrence_to_dict(_get_occurrence(occurrence_id), on)
