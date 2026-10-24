"""Пользователь панели.

Роли:
- superadmin — ровно один, прописан в .env (SUPERADMIN_*). Может всё,
  что администратор, и вдобавок управляет администраторами;
- admin — создаётся суперадмином через API;
- user — обычный пользователь.

Роль хранится в БД. Роль суперадмина при каждом старте выставляет
сид scripts.seed_superadmin по данным из .env.
"""

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, BigInteger
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.timeutils import utcnow

ROLE_SUPERADMIN = "superadmin"
ROLE_ADMIN = "admin"
ROLE_USER = "user"
ROLES = (ROLE_SUPERADMIN, ROLE_ADMIN, ROLE_USER)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(16), default=ROLE_USER)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, onupdate=utcnow
    )
    telegram_id: Mapped[int | None] = mapped_column(BigInteger, unique=True, index=True)
    
    @property
    def is_superadmin(self) -> bool:
        return self.role == ROLE_SUPERADMIN

    @property
    def is_admin(self) -> bool:
        """Права администратора: у администратора и у суперадмина."""
        return self.role in (ROLE_ADMIN, ROLE_SUPERADMIN)

    def __repr__(self) -> str:
        return f"<User {self.id} {self.username} ({self.role})>"