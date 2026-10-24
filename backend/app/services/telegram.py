"""Отправка сообщений в Telegram через Bot API.

Кейсу нужен только исходящий поток: бот сам проверяет сроки и пишет в указанный
чат. Обработка команд не требуется, поэтому ходим прямо в Bot API — без aiogram.

Настройка (.env):
    TELEGRAM_BOT_TOKEN=123456:ABC-DEF...   токен от @BotFather
    TELEGRAM_CHAT_ID=-1001234567890        куда писать
"""

import httpx

from app.config import settings
from app.logging_config import get_logger

logger = get_logger(__name__)

API_URL = "https://api.telegram.org/bot{token}/sendMessage"


class TelegramNotConfigured(RuntimeError):
    """В .env нет токена или chat_id."""


def is_configured() -> bool:
    """Настроен ли бот: есть и токен, и чат."""
    return bool(settings.telegram_bot_token and settings.telegram_chat_id)


def send_message(text: str, chat_id: str | None = None) -> dict:
    """Отправляет HTML-сообщение в чат. Бросает исключение при ошибке.

    chat_id можно передать явно — иначе берётся из .env.
    """
    if not is_configured():
        raise TelegramNotConfigured("TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID не заданы в .env")

    response = httpx.post(
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
    if not data.get("ok"):
        # Токен в лог не пишем: только код и описание ошибки от Telegram
        raise RuntimeError(f"Telegram API {response.status_code}: {data.get('description')}")
    logger.info(f"Сообщение отправлено в чат {chat_id or settings.telegram_chat_id}")
    return data