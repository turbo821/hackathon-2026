"""Администратор из .env (ADMIN_USERNAME / ADMIN_PASSWORD).

Запускается при каждом старте контейнера: если пароль в .env поменяли —
он обновится. Логин не меняется: он и есть признак администратора.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import hash_password, verify_password
from app.config import settings
from app.logging_config import get_logger
from app.models import User

logger = get_logger(__name__)


def run(db: Session):
    username = settings.admin_username.strip()
    if not username or not settings.admin_password:
        logger.warning("ADMIN_USERNAME / ADMIN_PASSWORD не заданы — администратор не создан")
        return

    admin = db.scalars(select(User).where(User.username == username)).first()
    if admin is None:
        db.add(User(username=username, password_hash=hash_password(settings.admin_password)))
        logger.info(f"admin: создан администратор {username}")
    elif not verify_password(settings.admin_password, admin.password_hash):
        admin.password_hash = hash_password(settings.admin_password)
        logger.info(f"admin: пароль администратора {username} обновлён из .env")
    else:
        logger.info(f"admin: аккаунт {username} актуален")

    db.commit()
