"""Преобразование моделей в словари для ответов API.

Всё берётся из самой строки: у периода есть слепок полей шаблона, поэтому
при чтении не нужно подтягивать связанные таблицы.
"""

from datetime import date

from app.models import PaymentOccurrence, RecurringPayment
from app.models.payment_occurrence import STATE_OVERDUE


def occurrence_to_dict(occ: PaymentOccurrence, on: date) -> dict:
    state = occ.state(on)
    return {
        "id": occ.id,
        "recurring_payment_id": occ.recurring_payment_id,
        "name": occ.name,
        "amount": occ.amount,
        "currency": occ.currency,
        "due_date": occ.due_date,
        "status": occ.status,
        "paid_at": occ.paid_at,
        "state": state,
        "is_overdue": state == STATE_OVERDUE,
        "overdue_days": occ.overdue_days(on),
        "days_until_due": (occ.due_date - on).days,
        "reminder_sent_at": occ.reminder_sent_at,
        "marked_by": occ.marked_by.username if occ.marked_by else None,
        "payment_ended_at": occ.payment_ended_at,
    }


def recurring_payment_to_dict(rp: RecurringPayment) -> dict:
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
    }
