"""Преобразование моделей в словари для ответов API."""

from datetime import date

from app.models import PaymentOccurrence, RecurringPayment
from app.models.payment_occurrence import STATE_OVERDUE, STATUS_UNPAID


def occurrence_to_dict(occ: PaymentOccurrence, on: date) -> dict:
    rp = occ.recurring_payment
    state = occ.state(on)
    return {
        "id": occ.id,
        "recurring_payment_id": rp.id,
        "name": rp.name,
        "amount": rp.amount,
        "currency": rp.currency,
        "due_date": occ.due_date,
        "status": occ.status,
        "paid_at": occ.paid_at,
        "state": state,
        "is_overdue": state == STATE_OVERDUE,
        "overdue_days": occ.overdue_days(on),
        "days_until_due": (occ.due_date - on).days,
        "reminder_sent_at": occ.reminder_sent_at,
        "marked_by": occ.marked_by.username if occ.marked_by else None,
        "recurring_payment_active": rp.is_active,
    }


def recurring_payment_to_dict(rp: RecurringPayment, on: date) -> dict:
    next_occ = None
    if rp.is_active:
        upcoming = [o for o in rp.occurrences if o.status == STATUS_UNPAID]
        if upcoming:
            o = min(upcoming, key=lambda x: x.due_date)
            next_occ = {"id": o.id, "due_date": o.due_date, "status": o.status, "state": o.state(on)}
    return {
        "id": rp.id,
        "name": rp.name,
        "amount": rp.amount,
        "currency": rp.currency,
        "period": rp.period,
        "first_due_date": rp.first_due_date,
        "anchor_day": rp.anchor_day,
        "is_active": rp.is_active,
        "ended_at": rp.ended_at,
        "created_at": rp.created_at,
        "next_occurrence": next_occ,
    }
