from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.timeutils import utcnow


class TelegramLink(Base):
    """Одноразовый код привязки Telegram-аккаунта к пользователю системы.

    Панель просит код и кладёт его в ссылку ?start=<token>. Бот получает
    /start <token> и по нему понимает, кого привязывать. Код живёт 15 минут
    и работает один раз.
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