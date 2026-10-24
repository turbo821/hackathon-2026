"""Клиент Telegram Bot API.

Напоминания — исходящий поток (sendMessage). Inline-кнопка «Оплачено»
требует ещё и входящего: бот читает обновления через long polling
(getUpdates) — вебхук не подошёл бы, для него нужен публичный HTTPS-адрес.

Токен и чат — только в .env (он в .gitignore).
"""

import json
from typing import Any

import httpx

from app.config import settings
from app.logging_config import get_logger

logger = get_logger(__name__)

API_BASE = "https://api.telegram.org/bot{token}/{method}"
TIMEOUT = 15

_bot_username: str | None = None


class TelegramNotConfigured(RuntimeError):
    """В .env нет токена или chat_id."""


class TelegramError(RuntimeError):
    """Telegram отклонил запрос."""


def has_token() -> bool:
    """Есть ли токен бота (нужно для чтения обновлений и привязки аккаунта)."""
    return bool(settings.telegram_bot_token)


def is_configured() -> bool:
    """Бот настроен для отправки напоминаний: есть и токен, и чат."""
    return bool(settings.telegram_bot_token and settings.telegram_chat_id)


def _call(method: str, payload: dict | None = None, timeout: int = TIMEOUT) -> Any:
    """Один вызов Bot API. Бросает TelegramError с описанием от Telegram."""
    if not has_token():
        raise TelegramNotConfigured("TELEGRAM_BOT_TOKEN не задан в .env")

    # Читаем URL прокси из переменных окружения Docker
    proxy_url = os.getenv("BOT_PROXY_URL")
    
    # Формируем базовые аргументы для запроса
    request_kwargs = {
        "json": payload or {},
        "timeout": timeout,
    }
    
    # Если прокси настроен, добавляем его в запрос
    if proxy_url:
        request_kwargs["proxies"] = proxy_url
        # Опционально: можно раскомментировать для отладки, чтобы видеть в логах, что прокси применяется
        # logger.debug(f"Запрос к Telegram через прокси: {proxy_url}")

    response = httpx.post(
        API_BASE.format(token=settings.telegram_bot_token, method=method),
        **request_kwargs,
    )
    
    try:
        data = response.json()
    except ValueError:
        raise TelegramError(f"Telegram API {response.status_code}: ответ не JSON")

    if not data.get("ok"):
        raise TelegramError(
            f"Telegram API {response.status_code}: {data.get('description')}"
        )
    return data.get("result")


def get_me() -> dict:
    """Информация о боте: username нужен для ссылки привязки."""
    return _call("getMe") or {}


def bot_username() -> str:
    """Имя бота без @ — для ссылки привязки ?start=<token>.

    Если имя задано в .env — берём его, иначе спрашиваем у Telegram (один раз).
    """
    global _bot_username
    if settings.telegram_bot_username:
        return settings.telegram_bot_username
    if _bot_username is None:
        _bot_username = str((get_me() or {}).get("username") or "")
        logger.info(f"Telegram: имя бота @{_bot_username}")
    return _bot_username


def send_message(
    text: str,
    chat_id: str | None = None,
    reply_markup: dict | None = None,
) -> dict:
    """Отправляет HTML-сообщение в чат. Бросает исключение при ошибке.

    chat_id можно передать явно — иначе берётся из .env.
    reply_markup — например, inline-кнопка:
        {"inline_keyboard": [[{"text": "✅ Оплачено", "callback_data": "pay:12"}]]}
    """
    target = chat_id or settings.telegram_chat_id
    if not target:
        raise TelegramNotConfigured("TELEGRAM_CHAT_ID не задан в .env")

    payload = {
        "chat_id": target,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup
    return _call("sendMessage", payload) or {}


def edit_message_text(
    chat_id: int,
    message_id: int,
    text: str,
    reply_markup: dict | None = None,
) -> dict:
    """Правит уже отправленное сообщение (например, убирает кнопку после оплаты)."""
    payload = {
        "chat_id": chat_id,
        "message_id": message_id,
        "text": text,
        "parse_mode": "HTML",
        # пустая клавиатура — убрать кнопку
        "reply_markup": reply_markup or {"inline_keyboard": []},
    }
    return _call("editMessageText", payload) or {}


def answer_callback(callback_id: str, text: str = "") -> dict:
    """Отвечает на нажатие кнопки (всплывающее уведомление в Telegram)."""
    return (
        _call("answerCallbackQuery", {"callback_query_id": callback_id, "text": text})
        or {}
    )


def get_updates(
    offset: int | None = None,
    timeout: int = 25,
    allowed_updates: list[str] | None = None,
) -> list[dict]:
    """Забирает накопленные обновления (long polling).

    offset — id последнего обработанного обновления: Telegram пришлёт только
    новые, а старые перестанут приходить.

    allowed_updates — какие типы событий присылать. По умолчанию Telegram
    не шлёт chat_member (события «кто вступил в чат»), поэтому список нужно
    задавать явно.
    """
    payload: dict[str, Any] = {"timeout": timeout}
    if offset is not None:
        payload["offset"] = offset
    if allowed_updates is not None:
        payload["allowed_updates"] = json.dumps(allowed_updates)
    # HTTP-таймаут должен быть больше таймаута long polling: иначе Telegram
    # держит запрос дольше, чем httpx готов ждать, и рвёт соединение.
    result = _call("getUpdates", payload, timeout=timeout + 15)
    return result if isinstance(result, list) else []


def create_chat_invite_link(chat_id: str | int, name: str) -> str:
    """Создаёт персональную ссылку-приглашение в чат.

    name (до 32 символов) попадёт в invite_link.name события о вступлении —
    именно туда кладём код привязки, чтобы по событию «пользователь вступил»
    понять, кого привязывать.

    Бот должен быть администратором чата с правом can_invite_users.
    """
    result = _call("createChatInviteLink", {"chat_id": chat_id, "name": name})
    link = result.get("invite_link") if isinstance(result, dict) else None
    if not link:
        raise TelegramError("Telegram не вернул ссылку-приглашение")
    return str(link)
