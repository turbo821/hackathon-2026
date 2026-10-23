"""Синхронизация администратора из .env (ADMIN_USERNAME / ADMIN_PASSWORD).

Запускается при каждом старте контейнера: если пароль в .env поменяли —
он обновится. Если поменяли логин — прежний env-админ становится обычной
учётной записью без прав администратора.
"""

from app.auth import hash_password, verify_password
from app.config import settings
from app.extensions import db
from app.logging_config import get_logger
from app.models import User
from app.models.user import ROLE_ADMIN, ROLE_USER

logger = get_logger(__name__)


def run():
    username = settings.admin_username.strip()
    if not username or not settings.admin_password:
        logger.warning("ADMIN_USERNAME / ADMIN_PASSWORD не заданы — администратор не создан")
        return

    # Прежние env-админы с другим логином теряют права
    for old in User.query.filter(User.is_env_admin.is_(True), User.username != username):
        old.is_env_admin = False
        old.role = ROLE_USER
        logger.warning(f"Учётная запись {old.username} больше не администратор (сменён ADMIN_USERNAME)")

    admin = User.query.filter_by(username=username).first()
    if admin is None:
        admin = User(username=username, password_hash=hash_password(settings.admin_password))
        db.session.add(admin)
        logger.info(f"admin: создан администратор {username}")
    elif not verify_password(settings.admin_password, admin.password_hash):
        admin.password_hash = hash_password(settings.admin_password)
        logger.info(f"admin: пароль администратора {username} обновлён из .env")
    else:
        logger.info(f"admin: администратор {username} актуален")

    admin.role = ROLE_ADMIN
    admin.is_env_admin = True
    db.session.commit()
