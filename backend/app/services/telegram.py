"""Отправка сообщений в Telegram через Bot API — ЗАГЛУШКА этапа «каркас».

Проверка настройки (is_configured) уже рабочая: она нужна, чтобы health-check
и worker понимали, настроен ли бот. Сама отправка — следующий этап.

Что здесь должно быть (правила из кейса):

- минимум за REMINDER_DAYS_BEFORE (3) дня до срока;
- только неоплаченные периоды активных платежей;
- без дублей: период «захватывается» атомарным UPDATE ... WHERE reminder_sent_at IS NULL;
- добавили платёж позже, чем за 3 дня до срока → напоминание сразу.
"""

from app.config import settings
from app.logging_config import get_logger

logger = get_logger(__name__)

API_URL = "https://api.telegram.org/bot{token}/sendMessage"


class TelegramNotConfigured(RuntimeError):
    pass


def is_configured() -> bool:
    """Настроен ли бот: есть и токен, и чат."""
    return bool(settings.telegram_bot_token and settings.telegram_chat_id)


def send_message(text: str, chat_id: str | None = None) -> dict:
    """Отправляет HTML-сообщение в чат. Бросает исключение при ошибке."""
    # TODO(каркас → реализация): POST на Bot API, разобрать ответ, не писать токен в лог.
    if not is_configured():
        raise TelegramNotConfigured("TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID не заданы в .env")
    raise NotImplementedError(
        "Отправка в Telegram ещё не реализована — это этап «каркас». "
        "Реализация: POST api.telegram.org/bot<token>/sendMessage, parse_mode=HTML."
    )
