"""Напоминания об оплате.

Правила из кейса:
- минимум за REMINDER_DAYS_BEFORE (3) дня до срока;
- только неоплаченные периоды действующих платежей;
- без дублей: период «захватывается» атомарным UPDATE ... WHERE reminder_sent_at IS NULL,
  поэтому повторная проверка или параллельный процесс второй раз не отправят;
- добавили платёж позже, чем за 3 дня до срока → напоминание сразу (remind_for_payment).
"""

import logging
from datetime import date, timedelta
from typing import Any, cast

from sqlalchemy import select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.orm import Session

from app.config import settings
from app.logging_config import get_logger, log_event
from app.models import PaymentOccurrence, RecurringPayment
from app.models.payment_occurrence import STATUS_UNPAID
from app.services.periods import ensure_all_occurrences
from app.services.recipients import email_recipients
from app.services.remind_channels import smtp, telegram
from app.services.remind_channels.utils import pay_button
from app.timeutils import today, utcnow

logger = get_logger(__name__)

# Список всех доступных каналов
CHANNELS = [telegram, smtp]

_warned_not_configured = False


def _due_occurrences_query(on: date):
    """Неоплаченные периоды действующих платежей со сроком в окне [сегодня; сегодня + N]."""
    window_end = on + timedelta(days=settings.reminder_days_before)
    return (
        select(PaymentOccurrence)
        .where(
            PaymentOccurrence.payment_ended_at.is_(None),
            PaymentOccurrence.status == STATUS_UNPAID,
            PaymentOccurrence.reminder_sent_at.is_(None),
            PaymentOccurrence.due_date >= on,
            PaymentOccurrence.due_date <= window_end,
        )
        .order_by(PaymentOccurrence.due_date)
    )


def _claim(db: Session, occ_id: int) -> bool:
    # Для UPDATE execute() отдаёт CursorResult — именно у него есть rowcount
    result = cast(
        CursorResult[Any],
        db.execute(
            update(PaymentOccurrence)
            .where(
                PaymentOccurrence.id == occ_id,
                PaymentOccurrence.reminder_sent_at.is_(None),
            )
            .values(reminder_sent_at=utcnow())
        ),
    )
    db.commit()
    return result.rowcount == 1


def _release(db: Session, occ_id: int) -> None:
    db.execute(
        update(PaymentOccurrence)
        .where(PaymentOccurrence.id == occ_id)
        .values(reminder_sent_at=None)
    )
    db.commit()


def _reply_markup(channel: Any, occ_id: int) -> dict | None:
    """Кнопка «Оплачено» — только каналам, которые её умеют (Telegram)."""
    if not getattr(channel, "supports_reply_markup", False):
        return None
    return pay_button(occ_id)


def _send_for(db: Session, occurrences: list[PaymentOccurrence], on: date) -> int:
    global _warned_not_configured

    if not occurrences:
        return 0

    # Отбираем только те каналы, которые настроены и готовы к работе
    active_channels = [ch for ch in CHANNELS if ch.ready_to_send()]

    if not active_channels:
        if not _warned_not_configured:
            logger.warning(
                "Ни один канал уведомлений не настроен (Telegram/SMTP) — "
                "напоминания не отправляются"
            )
            _warned_not_configured = True
        return 0

    sent = 0
    # Получатели писем — все адреса из базы. Собираем один раз на проверку,
    # а не на каждый период.
    recipients = email_recipients(db)
    log_event(
        logger,
        logging.INFO,
        "reminders.batch_start",
        occurrences=len(occurrences),
        channels=[ch.__name__ for ch in active_channels],
        recipients=len(recipients),
        on=on.isoformat(),
    )

    for occ in occurrences:
        occ_id, name, due = occ.id, occ.name, occ.due_date

        # Тексты собираем до захвата периода: после commit объект инвалидируется
        messages: list[tuple[Any, str]] = []
        for channel in active_channels:
            try:
                messages.append((channel, channel.build_message(occ, on)))
            except Exception:
                logger.exception(
                    f"Не удалось собрать текст напоминания по периоду #{occ_id} "
                    f"через {channel.__name__}"
                )
                log_event(
                    logger,
                    logging.ERROR,
                    "reminder.build_failed",
                    occurrence_id=occ_id,
                    channel=channel.__name__,
                    exc_info=True,
                )

        # Захватываем период
        if not _claim(db, occ_id):
            logger.info(f"Напоминание по периоду #{occ_id} уже отправлено, пропускаю")
            continue

        success = False
        # Пытаемся отправить через все доступные каналы
        for channel, text in messages:
            try:
                delivered = channel.send_message(
                    text,
                    reply_markup=_reply_markup(channel, occ_id),
                    recipients=recipients,
                )
                if delivered:
                    success = True
                else:
                    # Канал отработал, но ничего не доставил (например, в почте
                    # нет ни одного получателя). Успехом это считать нельзя:
                    # иначе упавший Telegram-канал замаскируется «пустым» SMTP.
                    logger.warning(
                        f"Канал {channel.__name__} ничего не доставил "
                        f"по периоду #{occ_id}"
                    )
                    log_event(
                        logger,
                        logging.WARNING,
                        "reminder.channel_empty",
                        occurrence_id=occ_id,
                        channel=channel.__name__,
                    )
            except Exception:
                logger.exception(
                    f"Не удалось отправить напоминание по периоду #{occ_id} "
                    f"через {channel.__name__}"
                )
                log_event(
                    logger,
                    logging.ERROR,
                    "reminder.channel_failed",
                    occurrence_id=occ_id,
                    channel=channel.__name__,
                    exc_info=True,
                )

        if success:
            sent += 1
            logger.info(
                f"Напоминание отправлено: «{name}», срок {due} (период #{occ_id})"
            )
            log_event(
                logger,
                logging.INFO,
                "reminder.sent",
                occurrence_id=occ_id,
                name=name,
                due=due.isoformat(),
                channels=[ch.__name__ for ch, _ in messages],
            )
        else:
            # Если все каналы упали с ошибкой — освобождаем период для следующей попытки
            logger.error(
                f"Все каналы не смогли отправить напоминание по периоду #{occ_id}"
            )
            log_event(
                logger,
                logging.ERROR,
                "reminder.all_channels_failed",
                occurrence_id=occ_id,
                name=name,
                due=due.isoformat(),
            )
            _release(db, occ_id)

    return sent


def check_and_send(db: Session, on: date | None = None) -> int:
    on = on or today()
    ensure_all_occurrences(db, on)
    return _send_for(db, list(db.scalars(_due_occurrences_query(on)).all()), on)


def remind_for_payment(
    db: Session, rp: RecurringPayment, on: date | None = None
) -> int:
    on = on or today()
    query = _due_occurrences_query(on).where(
        PaymentOccurrence.recurring_payment_id == rp.id
    )
    return _send_for(db, list(db.scalars(query).all()), on)
