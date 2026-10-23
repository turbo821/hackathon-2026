"""Отправка сообщений в Telegram через Bot API."""

import requests

from app.config import settings
from app.logging_config import get_logger

logger = get_logger(__name__)

API_URL = "https://api.telegram.org/bot{token}/sendMessage"


class TelegramNotConfigured(RuntimeError):
    pass


def is_configured() -> bool:
    return bool(settings.telegram_bot_token and settings.telegram_chat_id)


def send_message(text: str, chat_id: str | None = None) -> dict:
    """Отправляет HTML-сообщение. Бросает исключение при ошибке."""
    if not is_configured():
        raise TelegramNotConfigured("TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID не заданы в .env")

    response = requests.post(
        API_URL.format(token=settings.telegram_bot_token),
        json={
            "chat_id": chat_id or settings.telegram_chat_id,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        },
        timeout=10,
    )
    data = response.json() if response.content else {}
    if not response.ok or not data.get("ok"):
        # Токен в лог не пишем: только описание ошибки от Telegram
        raise RuntimeError(f"Telegram API {response.status_code}: {data.get('description')}")
    return data
