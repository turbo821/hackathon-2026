"""Журнал оплат: кто, сколько, какой платёж, когда и откуда (панель администратора)."""

from datetime import date

from fastapi import APIRouter, Query
from sqlalchemy import select
from sqlalchemy.orm import joinedload

from app.auth import DB, AdminUser
from app.models import PaymentOccurrence
from app.models.payment_occurrence import STATUS_PAID
from app.schemas.payments import PaymentLogOut
from app.services.serializers import payment_log_to_dict

router = APIRouter(prefix="/payments", tags=["payments"])


@router.get("", response_model=list[PaymentLogOut], summary="Журнал оплат (администратор)")
def payments_log(
    db: DB,
    admin: AdminUser,
    user_id: int | None = None,
    recurring_payment_id: int | None = None,
    date_from: date | None = Query(None, description="Дата оплаты с (включительно)"),
    date_to: date | None = Query(None, description="Дата оплаты по (включительно)"),
    limit: int = Query(200, ge=1, le=1000),
):
    """Кто оплатил, сколько, какой платёж, когда и откуда — сайт или Telegram."""
    query = select(PaymentOccurrence).options(joinedload(PaymentOccurrence.marked_by))
    query = query.where(PaymentOccurrence.status == STATUS_PAID)
    if user_id:
        query = query.where(PaymentOccurrence.marked_by_id == user_id)
    if recurring_payment_id:
        query = query.where(PaymentOccurrence.recurring_payment_id == recurring_payment_id)
    if date_from:
        query = query.where(PaymentOccurrence.paid_at >= date_from)
    if date_to:
        query = query.where(PaymentOccurrence.paid_at <= date_to)

    items = db.scalars(
        query.order_by(PaymentOccurrence.paid_at.desc(), PaymentOccurrence.id.desc()).limit(limit)
    ).all()
    return [payment_log_to_dict(o) for o in items]