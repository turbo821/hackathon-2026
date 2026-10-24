import html
from datetime import date

from app.config import settings
from app.models import PaymentOccurrence
from app.services import telegram as telegram_client
from app.services.remind_channels.utils import format_amount, get_time_until

# Telegram умеет inline-кнопки — ставим «Оплачено» прямо в сообщение
supports_reply_markup = True


def ready_to_send() -> bool:
    return bool(settings.telegram_bot_token and settings.telegram_chat_id)


def build_message(occ: PaymentOccurrence, on: date) -> str:
    when = get_time_until(occ.due_date, on)
    return (
        "🔔 <b>Напоминание об оплате</b>\n\n"
        f"<b>{html.escape(occ.name)}</b>\n"
        f"Сумма: <b>{format_amount(occ.amount, occ.currency)}</b>\n"
        f"Валюта: {occ.currency}\n"
        f"Дата оплаты: <b>{occ.due_date.strftime('%d.%m.%Y')}</b> ({when})\n\n"
        "Оплатили — нажмите кнопку «Оплачено»."
    )


def send_message(
    text: str,
    reply_markup: dict | None = None,
    recipients: list[str] | None = None,
) -> int:
    # Вызываем ваш существующий клиент Telegram.
    # recipients игнорируем: у Telegram один чат из .env, а не список адресов.
    telegram_client.send_message(text, reply_markup=reply_markup)
    return 1
