"""Напоминания об оплате в Telegram.

- минимум за REMINDER_DAYS_BEFORE (3) дня до срока;
- только неоплаченные периоды активных платежей;
- без дублей: период «захватывается» атомарным UPDATE ... WHERE reminder_sent_at IS NULL,
  поэтому повторная проверка или параллельный процесс второй раз не отправят;
- добавили платёж позже, чем за 3 дня до срока → напоминание сразу (remind_for_payment).
"""

import html
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import update

from app.config import settings
from app.extensions import db
from app.logging_config import get_logger
from app.models import PaymentOccurrence, RecurringPayment
from app.models.payment_occurrence import STATUS_UNPAID
from app.services import telegram
from app.services.periods import ensure_all_occurrences, ensure_occurrences
from app.timeutils import today, utcnow

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
    rp = occ.recurring_payment
    left = (occ.due_date - on).days
    if left == 0:
        when = "сегодня"
    elif left == 1:
        when = "завтра"
    else:
        when = f"через {left} {days_word(left)}"

    return (
        "🔔 <b>Напоминание об оплате</b>\n\n"
        f"<b>{html.escape(rp.name)}</b>\n"
        f"Сумма: <b>{format_amount(rp.amount, rp.currency)}</b>\n"
        f"Валюта: {rp.currency}\n"
        f"Дата оплаты: <b>{occ.due_date.strftime('%d.%m.%Y')}</b> ({when})"
    )


_last_unconfigured_count = None


def _due_occurrences_query(on: date):
    """Неоплаченные периоды активных платежей со сроком в окне [сегодня; сегодня + N]."""
    window_end = on + timedelta(days=settings.reminder_days_before)
    return (
        PaymentOccurrence.query.join(RecurringPayment)
        .filter(
            RecurringPayment.is_active.is_(True),
            PaymentOccurrence.status == STATUS_UNPAID,
            PaymentOccurrence.reminder_sent_at.is_(None),
            PaymentOccurrence.due_date >= on,
            PaymentOccurrence.due_date <= window_end,
        )
        .order_by(PaymentOccurrence.due_date)
    )


def _claim(occ_id: int) -> bool:
    """Атомарно помечает период как «напоминание отправляется». True — захватили мы."""
    result = db.session.execute(
        update(PaymentOccurrence)
        .where(PaymentOccurrence.id == occ_id, PaymentOccurrence.reminder_sent_at.is_(None))
        .values(reminder_sent_at=utcnow())
    )
    db.session.commit()
    return result.rowcount == 1


def _release(occ_id: int) -> None:
    """Отправка не удалась — снимаем отметку, чтобы попробовать в следующий раз."""
    db.session.execute(
        update(PaymentOccurrence)
        .where(PaymentOccurrence.id == occ_id)
        .values(reminder_sent_at=None)
    )
    db.session.commit()


def _send_for(occurrences: list[PaymentOccurrence], on: date) -> int:
    if not occurrences:
        return 0
    if not telegram.is_configured():
        global _last_unconfigured_count
        if _last_unconfigured_count == len(occurrences):
            return 0  # уже предупреждали — не засоряем лог каждые N секунд
        _last_unconfigured_count = len(occurrences)
        logger.warning(
            f"Есть {len(occurrences)} напоминаний к отправке, но Telegram не настроен "
            "(TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID)"
        )
        return 0

    sent = 0
    for occ in occurrences:
        # Текст собираем до захвата: после commit объекты перечитываются
        text = build_message(occ, on)
        occ_id, name, due = occ.id, occ.recurring_payment.name, occ.due_date
        if not _claim(occ_id):
            logger.info(f"Напоминание по периоду #{occ_id} уже отправлено, пропускаю")
            continue
        try:
            telegram.send_message(text)
            sent += 1
            logger.info(f"Напоминание отправлено: «{name}», срок {due} (период #{occ_id})")
        except Exception:
            logger.exception(f"Не удалось отправить напоминание по периоду #{occ_id}")
            _release(occ_id)
    return sent


def check_and_send(on: date | None = None) -> int:
    """Полная проверка (вызывается worker'ом по расписанию)."""
    on = on or today()
    ensure_all_occurrences(on)
    return _send_for(_due_occurrences_query(on).all(), on)


def remind_for_payment(rp: RecurringPayment, on: date | None = None) -> int:
    """Немедленная проверка одного платежа — сразу после его создания."""
    on = on or today()
    if ensure_occurrences(rp, on):
        db.session.commit()
    occurrences = (
        _due_occurrences_query(on).filter(PaymentOccurrence.recurring_payment_id == rp.id).all()
    )
    return _send_for(occurrences, on)
