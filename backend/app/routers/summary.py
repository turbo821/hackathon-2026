from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Query
from sqlalchemy import select
from sqlalchemy.orm import joinedload

from app.auth import DB, CurrentUser
from app.models import PaymentOccurrence, RecurringPayment
from app.models.payment_occurrence import STATUS_PAID
from app.models.recurring_payment import CURRENCIES
from app.schemas.payments import SummaryOut
from app.services.periods import ensure_all_occurrences
from app.timeutils import today

router = APIRouter(prefix="/payments", tags=["summary"])


@router.get("/summary", response_model=SummaryOut, summary="Получение итоговых сумм платежей по валютам")
def summary(
    db: DB,
    user: CurrentUser,
    date_from: date | None = Query(None, description="Срок оплаты с (включительно)"),
    date_to: date | None = Query(None, description="Срок оплаты по (включительно)"),
    on_date: date | None = Query(None, description="Дата, на которую считаются статусы и просрочка (по умолчанию сегодня)"),
):
    """Суммы считаются отдельно по каждой валюте (RUB, USD, EUR), конвертации нет."""
    on = on_date or today()
    ensure_all_occurrences(db, today())

    query = select(PaymentOccurrence).join(RecurringPayment).options(joinedload(PaymentOccurrence.recurring_payment))
    if date_from:
        query = query.where(PaymentOccurrence.due_date >= date_from)
    if date_to:
        query = query.where(PaymentOccurrence.due_date <= date_to)

    zero = Decimal("0.00")
    totals = {
        cur: {
            "currency": cur,
            "total": zero, "paid": zero, "unpaid": zero, "overdue": zero,
            "count_total": 0, "count_paid": 0, "count_unpaid": 0, "count_overdue": 0,
        }
        for cur in CURRENCIES
    }

    for occ in db.scalars(query).unique():
        rp = occ.recurring_payment
        t = totals[rp.currency]
        t["total"] += rp.amount
        t["count_total"] += 1
        # Статус «на дату»: оплата после on_date считается ещё не сделанной
        paid_on_date = occ.status == STATUS_PAID and (occ.paid_at is None or occ.paid_at <= on)
        if paid_on_date:
            t["paid"] += rp.amount
            t["count_paid"] += 1
        else:
            t["unpaid"] += rp.amount
            t["count_unpaid"] += 1
            if on > occ.due_date:
                t["overdue"] += rp.amount
                t["count_overdue"] += 1

    return {"date_from": date_from, "date_to": date_to, "on_date": on, "currencies": list(totals.values())}
