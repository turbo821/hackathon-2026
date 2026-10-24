from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.timeutils import utcnow


class TelegramLink(Base):
    """Одноразовый код привязки Telegram-аккаунта к пользователю системы.

    Два способа привязаться, оба по одному и тому же коду:
    - панель кладёт код в ссылку ?start=<token>, бот получает /start <token>;
    - панель просит у бота персональную ссылку-приглашение в чат, код спрятан
      в имени ссылки (invite_link.name), и бот привязывает аккаунт по событию
      «пользователь вступил в чат».

    Код живёт 15 минут и работает один раз.
    """

    __tablename__ = "telegram_links"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    token: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    # Момент использования: код одноразовый
    used_at: Mapped[datetime | None] = mapped_column(DateTime)
    # Созданная ботом ссылка-приглашение в чат (если привязка идёт через вступление)
    chat_invite_link: Mapped[str | None] = mapped_column(String(255))
