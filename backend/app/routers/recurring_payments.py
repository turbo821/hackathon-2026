from fastapi import APIRouter, Response
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.auth import DB, AdminUser, CurrentUser
from app.errors import ApiError
from app.logging_config import get_logger
from app.models import PaymentOccurrence, RecurringPayment
from app.models.payment_occurrence import STATUS_UNPAID
from app.schemas.payments import RecurringPaymentCreate, RecurringPaymentOut
from app.services.periods import ensure_all_occurrences, ensure_occurrences
from app.services.recurring_notifications import notify_recurring_created
from app.services.reminders import remind_for_payment
from app.services.serializers import recurring_payment_to_dict
from app.timeutils import today, utcnow

logger = get_logger(__name__)

router = APIRouter(prefix="/recurring-payments", tags=["recurring-payments"])

ADMIN_ONLY = {403: {"description": "Только администратор"}}


@router.get(
    "",
    response_model=list[RecurringPaymentOut],
    summary="Получение списка регулярных платежей",
)
def list_payments(db: DB, user: CurrentUser, include_inactive: bool = False):
    """По умолчанию только активные. `include_inactive=true` — вместе с прекращёнными.

    Читается одна таблица: периоды хранят слепок полей платежа, поэтому
    подтягивать их здесь не нужно.
    """
    on = today()
    ensure_all_occurrences(db, on)
    query = select(RecurringPayment)
    if not include_inactive:
        query = query.where(RecurringPayment.is_active.is_(True))
    items = db.scalars(
        query.order_by(RecurringPayment.is_active.desc(), RecurringPayment.name)
    ).all()
    return [recurring_payment_to_dict(rp) for rp in items]


@router.post(
    "",
    response_model=RecurringPaymentOut,
    status_code=201,
    summary="Создание регулярного платежа",
    responses=ADMIN_ONLY,
)
def create_payment(data: RecurringPaymentCreate, db: DB, admin: AdminUser):
    """Сразу создаются периоды.

    В общий чат уходит оповещение о новом платеже. Если срок ближайшей оплаты
    ближе, чем через 3 дня, дополнительно приходит напоминание об оплате.
    """
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
    db.commit()

    # Ошибка Telegram не должна ломать создание платежа.
    try:
        notify_recurring_created(db, rp, created_by=admin.username, on=on)
    except Exception:
        logger.exception(f"Не удалось отправить оповещение о новом платеже #{rp.id}")
        db.rollback()

    try:
        remind_for_payment(db, rp, on)
    except Exception:
        logger.exception(f"Не удалось проверить напоминание для платежа #{rp.id}")
        db.rollback()

    db.refresh(rp)
    return recurring_payment_to_dict(rp)


@router.delete(
    "/{payment_id}",
    status_code=204,
    summary="Прекращение регулярного платежа и его напоминаний с сохранением истории",
    responses={**ADMIN_ONLY, 404: {"description": "Платёж не найден"}},
)
def delete_payment(payment_id: int, db: DB, admin: AdminUser):
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
    # Периоды помнят, что их платёж прекращён (одна правда в БД, без JOIN)
    db.execute(
        update(PaymentOccurrence)
        .where(PaymentOccurrence.recurring_payment_id == rp.id)
        .values(payment_ended_at=rp.ended_at)
    )
    db.commit()
    return Response(status_code=204)
