"""Оповещения о новых регулярных платежах.

Отдельно от напоминаний (services/reminders.py): напоминание — это «пора
оплатить период», а здесь — «в панели добавили новый платёж». Разные события
и разные тексты, поэтому и разные модули.

Куда слать: в TELEGRAM_NOTIFY_CHAT_ID, если он задан, иначе — в общий чат
TELEGRAM_CHAT_ID (тот же, куда идут напоминания).

Ошибка Telegram не должна ломать создание платежа: вызывающий код оборачивает
вызов в try/except и логирует неудачу.
"""

import html
import logging
from datetime import date
from decimal import Decimal

from app.config import settings
from app.logging_config import get_logger, log_event
from app.models import RecurringPayment
from app.services import telegram as telegram_client
from app.services.remind_channels.utils import format_amount, get_time_until
from app.timeutils import today

logger = get_logger(__name__)

# Периодичность — человеческими словами, а не как в базе.
PERIOD_LABELS = {
    "monthly": "ежемесячно",
    "quarterly": "ежеквартально",
    "yearly": "ежегодно",
}


def notify_chat_id() -> str:
    """Куда слать оповещения: отдельный чат, если задан, иначе общий."""
    return settings.telegram_notify_chat_id or settings.telegram_chat_id


def ready_to_send() -> bool:
    """Настроен ли Telegram и есть ли чат, куда слать."""
    return bool(settings.telegram_bot_token and notify_chat_id())


def build_message(
    rp: RecurringPayment,
    on: date,
    created_by: str | None = None,
) -> str:
    """Текст оповещения о новом регулярном платеже."""
    amount: Decimal = rp.amount
    period = PERIOD_LABELS.get(rp.period, rp.period)
    when = get_time_until(rp.first_due_date, on)

    lines = [
        "📋 <b>Новый регулярный платёж</b>",
        "",
        f"<b>{html.escape(rp.name)}</b>",
        f"Сумма: <b>{format_amount(amount, rp.currency)}</b>",
        f"Периодичность: {period}",
        f"Ближайший срок: <b>{rp.first_due_date.strftime('%d.%m.%Y')}</b> ({when})",
    ]
    if created_by:
        lines += ["", f"Добавил: {html.escape(created_by)}"]

    return "\n".join(lines)


def notify_recurring_created(
    rp: RecurringPayment,
    created_by: str | None = None,
    on: date | None = None,
) -> bool:
    """Отправляет оповещение о новом регулярном платеже. True — отправлено.

    Если Telegram не настроен — молча возвращает False: это не ошибка
    создания платежа.
    """
    if not ready_to_send():
        return False

    on = on or today()
    chat_id = notify_chat_id()
    text = build_message(rp, on, created_by)

    try:
        telegram_client.send_message(text, chat_id=chat_id)
    except Exception:
        logger.exception(
            f"Не удалось отправить оповещение о новом платеже #{rp.id} в чат {chat_id}"
        )
        log_event(
            logger,
            logging.ERROR,
            "recurring.notify_failed",
            payment_id=rp.id,
            chat_id=chat_id,
            exc_info=True,
        )
        return False

    log_event(
        logger,
        logging.INFO,
        "recurring.notified",
        payment_id=rp.id,
        name=rp.name,
        chat_id=chat_id,
        created_by=created_by,
    )
    logger.info(f"Оповещение о новом платеже «{rp.name}» отправлено в чат {chat_id}")
    return True
