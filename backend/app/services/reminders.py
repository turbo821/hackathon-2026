"""Напоминания об оплате в Telegram.

Правила из кейса:
- минимум за REMINDER_DAYS_BEFORE (3) дня до срока;
- только неоплаченные периоды действующих платежей;
- без дублей: период «захватывается» атомарным UPDATE ... WHERE reminder_sent_at IS NULL,
  поэтому повторная проверка или параллельный процесс второй раз не отправят;
- добавили платёж позже, чем за 3 дня до срока → напоминание сразу (remind_for_payment).

Период хранит слепок полей платежа, поэтому выборка идёт по одной таблице.
"""

import html
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.config import settings
from app.logging_config import get_logger
from app.models import PaymentOccurrence, RecurringPayment
from app.models.payment_occurrence import STATUS_UNPAID
from app.services import telegram
from app.services.periods import ensure_all_occurrences
from app.timeutils import today, utcnow

logger = get_logger(__name__)

# Флаг, чтобы не сыпать предупреждения каждую минуту, пока бот не настроен
_warned_not_configured = False


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


def _due_occurrences_query(on: date):
    """Неоплаченные периоды действующих платежей со сроком в окне [сегодня; сегодня + N]."""
    window_end = on + timedelta(days=settings.reminder_days_before)
    return (
        select(PaymentOccurrence)
        .where(
            PaymentOccurrence.payment_ended_at.is_(None),   # платёж не прекращён
            PaymentOccurrence.status == STATUS_UNPAID,      # ещё не оплачено
            PaymentOccurrence.reminder_sent_at.is_(None),   # ещё не напоминали
            PaymentOccurrence.due_date >= on,
            PaymentOccurrence.due_date <= window_end,
        )
        .order_by(PaymentOccurrence.due_date)
    )


def _claim(db: Session, occ_id: int) -> bool:
    """Атомарно помечает период как «напоминание отправляется». True — захватили мы."""
    result = db.execute(
        update(PaymentOccurrence)
        .where(PaymentOccurrence.id == occ_id, PaymentOccurrence.reminder_sent_at.is_(None))
        .values(reminder_sent_at=utcnow())
    )
    db.commit()
    return result.rowcount == 1


def _release(db: Session, occ_id: int) -> None:
    """Отправка не удалась — снимаем отметку, чтобы попробовать в следующий раз."""
    db.execute(
        update(PaymentOccurrence)
        .where(PaymentOccurrence.id == occ_id)
        .values(reminder_sent_at=None)
    )
    db.commit()


def _send_for(db: Session, occurrences: list[PaymentOccurrence], on: date) -> int:
    global _warned_not_configured
    if not occurrences:
        return 0
    if not telegram.is_configured():
        if not _warned_not_configured:
            logger.warning(
                "Telegram не настроен (TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID) — "
                "напоминания не отправляются"
            )
            _warned_not_configured = True
        return 0

    sent = 0
    for occ in occurrences:
        # Текст собираем заранее, до захвата: не зависим от состояния объекта после commit
        text = build_message(occ, on)
        occ_id, name, due = occ.id, occ.name, occ.due_date
        if not _claim(db, occ_id):
            logger.info(f"Напоминание по периоду #{occ_id} уже отправлено, пропускаю")
            continue
        try:
            telegram.send_message(text)
            sent += 1
            logger.info(f"Напоминание отправлено: «{name}», срок {due} (период #{occ_id})")
        except Exception:
            logger.exception(f"Не удалось отправить напоминание по периоду #{occ_id}")
            _release(db, occ_id)
    return sent


def check_and_send(db: Session, on: date | None = None) -> int:
    """Полная проверка (вызывается worker'ом по расписанию)."""
    on = on or today()
    # Периоды, которых ещё нет, досоздаём здесь: платёж могли добавить после
    # последнего открытия панели — без этого worker его бы не увидел.
    ensure_all_occurrences(db, on)
    return _send_for(db, list(db.scalars(_due_occurrences_query(on)).all()), on)


def remind_for_payment(db: Session, rp: RecurringPayment, on: date | None = None) -> int:
    """Немедленная проверка одного платежа — сразу после его создания."""
    on = on or today()
    query = _due_occurrences_query(on).where(PaymentOccurrence.recurring_payment_id == rp.id)
    return _send_for(db, list(db.scalars(query).all()), on)