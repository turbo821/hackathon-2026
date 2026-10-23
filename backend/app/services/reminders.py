"""Напоминания об оплате в Telegram — ЗАГЛУШКА этапа «каркас».

Форматирование текста уже готово (его видно в Swagger/логах), а сама отправка
и выборка периодов — следующий этап.

Что здесь должно быть (правила из кейса):

- минимум за REMINDER_DAYS_BEFORE (3) дня до срока;
- только неоплаченные периоды активных платежей;
- без дублей: период «захватывается» атомарным UPDATE ... WHERE reminder_sent_at IS NULL,
  поэтому повторная проверка или параллельный процесс второй раз не отправят;
- добавили платёж позже, чем за 3 дня до срока → напоминание сразу (remind_for_payment);
- оплаченный период напоминания не вызывает;
- удалённый (неактивный) платёж больше не создаёт напоминаний.

Пока реализация не готова, функции ничего не отправляют и возвращают 0.
"""

import html
from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from app.config import settings
from app.logging_config import get_logger
from app.models import PaymentOccurrence, RecurringPayment

logger = get_logger(__name__)


def format_amount(amount: Decimal, currency: str) -> str:
    whole = f"{Decimal(amount):,.2f}".replace(",", " ")
    return f"{whole} {currency}"


def days_word(n: int) -> str:
    if n % 10 == 1 and n % 100 != 11:
        return "день"
    if n % 10 in (2, 3, 4) and n % 100 not in (12, 13, 14):
        return "дня"
    return "дней"


def build_message(occ: PaymentOccurrence, on: date) -> str:
    """Текст напоминания: название, сумма, валюта и дата оплаты."""
    left = (occ.due_date - on).days
    if left == 0:
        when = "сегодня"
    elif left == 1:
        when = "завтра"
    else:
        when = f"через {left} {days_word(left)}"

    return (
        "🔔 <b>Напоминание об оплате</b>\n\n"
        f"<b>{html.escape(occ.name)}</b>\n"
        f"Сумма: <b>{format_amount(occ.amount, occ.currency)}</b>\n"
        f"Валюта: {occ.currency}\n"
        f"Дата оплаты: <b>{occ.due_date.strftime('%d.%m.%Y')}</b> ({when})"
    )


def check_and_send(db: Session, on: date | None = None) -> int:
    """Полная проверка (вызывается worker'ом по расписанию). Возвращает число отправок."""
    # TODO(каркас → реализация): выбрать неоплаченные периоды в окне
    # [сегодня; сегодня + REMINDER_DAYS_BEFORE] и отправить по ним напоминания.
    logger.debug("reminders.check_and_send: заглушка, напоминания не отправляются")
    return 0


def remind_for_payment(db: Session, rp: RecurringPayment, on: date | None = None) -> int:
    """Немедленная проверка одного платежа — сразу после его создания."""
    # TODO(каркас → реализация): если срок ближе, чем через REMINDER_DAYS_BEFORE дней, —
    # отправить напоминание сразу при создании платежа.
    logger.debug(f"reminders.remind_for_payment: заглушка, платёж #{getattr(rp, 'id', None)}")
    return 0
