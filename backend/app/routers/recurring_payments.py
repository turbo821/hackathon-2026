from fastapi import APIRouter, Request, Response
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.auth import DB, AdminUser, CurrentUser
from app.errors import ApiError
from app.logging_config import get_logger
from app.models import PaymentOccurrence, RecurringPayment
from app.models.payment_occurrence import STATUS_UNPAID
from app.schemas.payments import RecurringPaymentCreate, RecurringPaymentOut
from app.services.audit import audit
from app.services.periods import ensure_all_occurrences, ensure_occurrences
from app.services.reminders import remind_for_payment
from app.services.serializers import recurring_payment_to_dict
from app.timeutils import today, utcnow

logger = get_logger(__name__)

router = APIRouter(prefix="/recurring-payments", tags=["recurring-payments"])

ADMIN_ONLY = {403: {"description": "Только администратор"}}


@router.get("", response_model=list[RecurringPaymentOut], summary="Получение списка регулярных платежей")
def list_payments(db: DB, user: CurrentUser, include_inactive: bool = False):
    """По умолчанию только активные. `include_inactive=true` — вместе с прекращёнными."""
    on = today()
    ensure_all_occurrences(db, on)
    query = select(RecurringPayment).options(selectinload(RecurringPayment.occurrences))
    if not include_inactive:
        query = query.where(RecurringPayment.is_active.is_(True))
    items = db.scalars(query.order_by(RecurringPayment.is_active.desc(), RecurringPayment.name)).all()
    return [recurring_payment_to_dict(rp, on) for rp in items]


@router.post(
    "",
    response_model=RecurringPaymentOut,
    status_code=201,
    summary="Создание регулярного платежа",
    responses=ADMIN_ONLY,
)
def create_payment(data: RecurringPaymentCreate, db: DB, admin: AdminUser, request: Request):
    """Сразу создаются периоды. Если срок ближайшей оплаты ближе, чем через 3 дня,
    напоминание в Telegram отправляется сразу."""
    on = today()
    rp = RecurringPayment(
        name=data.name,
        amount=data.amount,
        currency=data.currency,
        period=data.period,
        first_due_date=data.first_due_date,
        anchor_day=data.first_due_date.day,
        created_by_id=admin.id,
    )
    db.add(rp)
    db.flush()
    ensure_occurrences(db, rp, on)
    audit(
        db,
        "recurring_payment.create",
        user=admin,
        entity_type="recurring_payment",
        entity_id=rp.id,
        details={
            "name": rp.name,
            "amount": f"{rp.amount:.2f}",
            "currency": rp.currency,
            "first_due_date": rp.first_due_date.isoformat(),
            "period": rp.period,
        },
        request=request,
    )
    db.commit()

    # Напоминание сразу, если срок уже в окне 3 дней. Ошибка Telegram не ломает создание.
    try:
        remind_for_payment(db, rp, on)
    except Exception:
        logger.exception(f"Не удалось проверить напоминание для платежа #{rp.id}")
        db.rollback()

    db.refresh(rp)
    return recurring_payment_to_dict(rp, on)


@router.get(
    "/{payment_id}",
    response_model=RecurringPaymentOut,
    summary="Получение регулярного платежа",
    responses={404: {"description": "Платёж не найден"}},
)
def get_payment(payment_id: int, db: DB, user: CurrentUser):
    rp = db.get(RecurringPayment, payment_id)
    if rp is None:
        raise ApiError(404, "Платёж не найден")
    on = today()
    if ensure_occurrences(db, rp, on):
        db.commit()
    return recurring_payment_to_dict(rp, on)


@router.delete(
    "/{payment_id}",
    status_code=204,
    summary="Прекращение регулярного платежа и его напоминаний с сохранением истории",
    responses={**ADMIN_ONLY, 404: {"description": "Платёж не найден"}},
)
def delete_payment(payment_id: int, db: DB, admin: AdminUser, request: Request):
    """Платёж помечается неактивным: новые периоды и напоминания больше не создаются.
    Оплаченные и уже наступившие периоды остаются в истории;
    будущие неоплаченные периоды удаляются."""
    rp = db.get(RecurringPayment, payment_id)
    if rp is None or not rp.is_active:
        raise ApiError(404, "Платёж не найден или уже прекращён")

    future_unpaid = db.scalars(
        select(PaymentOccurrence).where(
            PaymentOccurrence.recurring_payment_id == rp.id,
            PaymentOccurrence.status == STATUS_UNPAID,
            PaymentOccurrence.due_date > today(),
        )
    ).all()
    for occ in future_unpaid:
        db.delete(occ)

    rp.is_active = False
    rp.ended_at = utcnow()
    audit(
        db,
        "recurring_payment.delete",
        user=admin,
        entity_type="recurring_payment",
        entity_id=rp.id,
        details={"name": rp.name, "removed_future_periods": len(future_unpaid)},
        request=request,
    )
    db.commit()
    return Response(status_code=204)
