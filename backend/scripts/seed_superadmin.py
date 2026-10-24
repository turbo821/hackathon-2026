"""Суперадмин из .env (SUPERADMIN_USERNAME / SUPERADMIN_PASSWORD / SUPERADMIN_EMAIL).

Запускается при каждом старте контейнера:
- нет аккаунта — создаёт;
- поменяли пароль или email в .env — обновляет;
- роль superadmin всегда у этого аккаунта; если в базе есть другой
  superadmin (например, сменили логин в .env), он становится admin.
"""

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.auth import hash_password, verify_password
from app.config import settings
from app.logging_config import get_logger
from app.models import User
from app.models.user import ROLE_ADMIN, ROLE_SUPERADMIN

logger = get_logger(__name__)


def run(db: Session):
    username = settings.superadmin_username.strip()
    email = settings.superadmin_email.strip().lower()
    password = settings.superadmin_password
    if not username or not email or not password:
        logger.warning(
            "SUPERADMIN_USERNAME / SUPERADMIN_PASSWORD / SUPERADMIN_EMAIL не заданы — суперадмин не создан"
        )
        return

    su = db.scalars(select(User).where(func.lower(User.username) == username.lower())).first()

    # Email суперадмина не должен принадлежать другому пользователю
    owner = db.scalars(select(User).where(User.email == email)).first()
    if owner is not None and (su is None or owner.id != su.id):
        raise RuntimeError(
            f"SUPERADMIN_EMAIL={email} уже занят пользователем {owner.username}. "
            "Укажите в .env другой email или смените email этому пользователю."
        )

    if su is None:
        su = User(username=username, email=email, role=ROLE_SUPERADMIN, password_hash=hash_password(password))
        db.add(su)
        db.flush()
        logger.info(f"superadmin: создан {username} ({email})")
    else:
        if not verify_password(password, su.password_hash):
            su.password_hash = hash_password(password)
            logger.info(f"superadmin: пароль {username} обновлён из .env")
        if su.email != email:
            su.email = email
            logger.info(f"superadmin: email {username} обновлён из .env")
        if su.role != ROLE_SUPERADMIN:
            su.role = ROLE_SUPERADMIN
            logger.info(f"superadmin: {username} получил роль superadmin")

    demoted = db.execute(
        update(User)
        .where(User.role == ROLE_SUPERADMIN, User.id != su.id)
        .values(role=ROLE_ADMIN)
    ).rowcount
    if demoted:
        logger.info(f"superadmin: прежних суперадминов переведено в admin: {demoted}")

    db.commit()