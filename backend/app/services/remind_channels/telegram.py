import html
from datetime import date

from app.config import settings
from app.models import PaymentOccurrence
from app.services import telegram as telegram_client
from app.services.remind_channels.utils import format_amount, get_time_until

def ready_to_send() -> bool:
    return bool(settings.telegram_bot_token.get_secret_value() and settings.telegram_chat_id)

def build_message(occ: PaymentOccurrence, on: date) -> str:
    when = get_time_until(occ.due_date, on)
    return (
        "🔔 <b>Напоминание об оплате</b>\n\n"
        f"<b>{html.escape(occ.name)}</b>\n"
        f"Сумма: <b>{format_amount(occ.amount, occ.currency)}</b>\n"
        f"Валюта: {occ.currency}\n"
        f"Дата оплаты: <b>{occ.due_date.strftime('%d.%m.%Y')}</b> ({when})"
    )

def send_message(text: str) -> None:
    # Вызываем ваш существующий клиент Telegram
    telegram_client.send_message(text)