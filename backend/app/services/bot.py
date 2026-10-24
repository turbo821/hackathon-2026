"""Обработка входящих обновлений Telegram: привязка аккаунта и кнопка «Оплачено».

Бот работает в двух режимах:
- напоминания (services/reminders.py) — исходящий поток;
- этот модуль — входящий: читает обновления и реагирует на /start
  и на нажатие inline-кнопки «Оплачено».

Кто нажал кнопку, определяется по Telegram ID: ищем пользователя с таким
telegram_id в базе — в журнале оплат будет имя из системы, а не @username.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.logging_config import get_logger
from app.models import PaymentOccurrence, TelegramLink, User
from app.models.payment_occurrence import PAID_SOURCE_TELEGRAM, STATUS_PAID
from app.services import telegram
from app.timeutils import today, utcnow

logger = get_logger(__name__)


def handle_start(db: Session, from_user_id: int, token: str) -> str:
    """Обрабатывает /start <token> — привязку Telegram-аккаунта к пользователю.

    Код одноразовый и живёт 15 минут: по ссылке, которую кто-то переслал
    в чат, чужой Telegram привязать нельзя.
    """
    link = db.scalars(
        select(TelegramLink).where(
            TelegramLink.token == token,
            TelegramLink.used_at.is_(None),
            TelegramLink.expires_at > utcnow(),
        )
    ).first()
    if link is None:
        return "Ссылка недействительна или уже использована. Создайте новую в панели."

    user = db.get(User, link.user_id)
    if user is None:
        return "Пользователь не найден."

    # Если этот Telegram был привязан к другому — освобождаем ID.
    # Отдельным коммитом: иначе два UPDATE'а в одной транзакции могут
    # столкнуться с UNIQUE-ограничением на users.telegram_id.
    other = db.scalars(select(User).where(User.telegram_id == from_user_id)).first()
    if other is not None and other.id != user.id:
        other.telegram_id = None
        db.commit()
        logger.info(f"telegram {from_user_id}: отвязан от {other.username}")

    user.telegram_id = from_user_id
    link.used_at = utcnow()
    db.commit()
    logger.info(f"telegram {from_user_id}: привязан к {user.username}")
    return f"Готово, вы привязаны как {user.username}."


def handle_pay_button(db: Session, from_user_id: int, occurrence_id: int) -> str:
    """Закрывает период по нажатию inline-кнопки «Оплачено»."""
    user = db.scalars(select(User).where(User.telegram_id == from_user_id)).first()
    if user is None:
        return "Вы не привязаны к системе. Зайдите в панель и привяжите Telegram."

    occ = db.get(PaymentOccurrence, occurrence_id)
    if occ is None:
        return "Платёж не найден."
    if occ.status == STATUS_PAID:
        return f"Уже оплачено: {occ.name}."
    if occ.payment_ended_at is not None:
        return f"Платёж «{occ.name}» прекращён."

    occ.status = STATUS_PAID
    occ.paid_at = today()
    occ.marked_by_id = user.id
    occ.paid_source = PAID_SOURCE_TELEGRAM
    db.commit()
    logger.info(
        f"telegram: {user.username} оплатил «{occ.name}» ({occ.amount} {occ.currency})"
    )
    return f"Записал: {occ.name} — {occ.amount} {occ.currency}."


def handle_update(db: Session, update: dict) -> None:
    """Обрабатывает одно обновление от Telegram."""
    if "callback_query" in update:
        _handle_callback(db, update["callback_query"])
        return

    message = update.get("message")
    if not message:
        return

    chat = message.get("chat") or {}
    chat_id = chat.get("id")
    from_user = message.get("from") or {}
    text = (message.get("text") or "").strip()

    if text.startswith("/start"):
        parts = text.split(maxsplit=1)
        token = parts[1] if len(parts) > 1 else ""
        if token:
            answer = handle_start(db, from_user.get("id"), token)
        else:
            answer = (
                f"Ваш Telegram ID: {from_user.get('id')}.\n"
                "Вставьте его в панели или пришлите /start <код> из панели."
            )
        telegram.send_message(answer, chat_id=chat_id)
        return

    # Обычное сообщение: подсказываем ID для ручной привязки
    user = db.scalars(select(User).where(User.telegram_id == from_user.get("id"))).first()
    if user is not None:
        telegram.send_message(f"Вы в системе как {user.username}.", chat_id=chat_id)
    else:
        telegram.send_message(
            f"Ваш Telegram ID: {from_user.get('id')}.\n"
            "Вставьте его в панели (Настройки → Telegram ID).",
            chat_id=chat_id,
        )


def _handle_callback(db: Session, callback: dict) -> None:
    """Обрабатывает нажатие inline-кнопки."""
    callback_id = callback.get("id", "")
    from_user = callback.get("from") or {}
    data = callback.get("data") or ""
    message = callback.get("message") or {}
    chat_id = (message.get("chat") or {}).get("id")
    message_id = message.get("message_id")

    if not data.startswith("pay:"):
        telegram.answer_callback(callback_id, "Неизвестная кнопка")
        return
    try:
        occurrence_id = int(data.split(":", 1)[1])
    except ValueError:
        telegram.answer_callback(callback_id, "Некорректная кнопка")
        return

    answer = handle_pay_button(db, from_user.get("id"), occurrence_id)
    telegram.answer_callback(callback_id, answer[:190])

    # Убираем кнопку из сообщения и пишем, что оплачено
    if chat_id and message_id and answer.startswith(("Записал", "Уже оплачено")):
        telegram.edit_message_text(chat_id, message_id, f"✅ {answer}")


def poll_once(db: Session, offset: int | None) -> int | None:
    """Читает обновления и обрабатывает их. Возвращает новый offset."""
    updates = telegram.get_updates(offset=offset, timeout=25)
    for update in updates:
        try:
            handle_update(db, update)
        except Exception:
            logger.exception("Ошибка при обработке обновления Telegram")
    if updates:
        return max(u["update_id"] for u in updates) + 1
    return offset