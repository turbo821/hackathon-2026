"""Пользователь панели.

Администратор — ровно один, и он прописан в .env (ADMIN_USERNAME).
Поэтому в таблице нет колонок role/is_env_admin: роль вычисляется из логина,
и база не может разойтись с настройкой.
"""

from datetime import datetime

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.config import settings
from app.db import Base
from app.timeutils import utcnow

ROLE_ADMIN = "admin"
ROLE_USER = "user"
ROLES = (ROLE_ADMIN, ROLE_USER)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, onupdate=utcnow
    )

    @property
    def is_admin(self) -> bool:
        """Администратор — тот аккаунт, который прописан в .env."""
        return self.username.strip().lower() == settings.admin_username.strip().lower()

    @property
    def role(self) -> str:
        return ROLE_ADMIN if self.is_admin else ROLE_USER

    def __repr__(self) -> str:
        return f"<User {self.id} {self.username} ({self.role})>"