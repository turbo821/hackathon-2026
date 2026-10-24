from fastapi import APIRouter, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth import DB, AdminUser, hash_password
from app.config import settings
from app.errors import ApiError
from app.logging_config import get_logger
from app.models import User
from app.models.user import ROLE_ADMIN
from app.schemas.users import UserCreate, UserOut, UserUpdate

logger = get_logger(__name__)

router = APIRouter(prefix="/users", tags=["users"])

FORBIDDEN = {403: {"description": "Нет прав: администраторами управляет только суперадмин, суперадмин не меняется"}}
NOT_FOUND = {404: {"description": "Пользователь не найден"}}
CONFLICT = {409: {"description": "Логин или email занят"}}


def _get_manageable_user(db: Session, user_id: int, actor: User) -> User:
    """Пользователь, которым actor вправе управлять."""
    user = db.get(User, user_id)
    if user is None:
        raise ApiError(404, "Пользователь не найден")
    if user.is_superadmin:
        raise ApiError(403, "Учётную запись суперадмина нельзя изменить через панель")
    if user.role == ROLE_ADMIN and not actor.is_superadmin:
        raise ApiError(403, "Администраторами управляет только суперадмин")
    return user


def _ensure_can_assign(actor: User, role: str) -> None:
    if role == ROLE_ADMIN and not actor.is_superadmin:
        raise ApiError(403, "Назначать администраторов может только суперадмин")


def _ensure_username_free(db: Session, username: str, exclude_id: int | None = None):
    # Логин суперадмина зарезервирован: иначе сид переписал бы чужой аккаунт
    if username.strip().lower() == settings.superadmin_username.strip().lower():
        raise ApiError(409, "Этот логин зарезервирован под суперадмина из .env")
    query = select(User).where(func.lower(User.username) == username.lower())
    if exclude_id:
        query = query.where(User.id != exclude_id)
    if db.scalars(query).first():
        raise ApiError(409, "Пользователь с таким логином уже существует")


def _ensure_email_free(db: Session, email: str, exclude_id: int | None = None):
    if email == settings.superadmin_email.strip().lower():
        raise ApiError(409, "Этот email зарезервирован под суперадмина из .env")
    query = select(User).where(User.email == email)  # email уже в нижнем регистре
    if exclude_id:
        query = query.where(User.id != exclude_id)
    if db.scalars(query).first():
        raise ApiError(409, "Пользователь с таким email уже существует")


@router.get("", response_model=list[UserOut], summary="Получение списка пользователей", responses=FORBIDDEN)
def list_users(db: DB, admin: AdminUser):
    return db.scalars(select(User).order_by(User.username)).all()


@router.post(
    "",
    response_model=UserOut,
    status_code=201,
    summary="Создание пользователя или администратора",
    responses={**FORBIDDEN, **CONFLICT},
)
def create_user(data: UserCreate, db: DB, admin: AdminUser):
    """Администратор создаёт обычных пользователей, суперадмин — ещё и администраторов
    (`"role": "admin"`). Суперадмина через API создать нельзя: он один и прописан в .env."""
    _ensure_can_assign(admin, data.role)
    _ensure_username_free(db, data.username)
    _ensure_email_free(db, data.email)
    user = User(
        username=data.username,
        email=data.email,
        role=data.role,
        password_hash=hash_password(data.password),
    )
    db.add(user)
    db.commit()
    logger.info(f"{admin.username} создал пользователя {user.username} ({user.role})")
    return user


@router.patch(
    "/{user_id}",
    response_model=UserOut,
    summary="Изменение пользователя",
    responses={**FORBIDDEN, **NOT_FOUND, **CONFLICT},
)
def update_user(user_id: int, data: UserUpdate, db: DB, admin: AdminUser):
    """Можно сменить логин, пароль, email. Роль (admin/user) меняет только суперадмин."""
    user = _get_manageable_user(db, user_id, admin)
    if data.role and data.role != user.role:
        if not admin.is_superadmin:
            raise ApiError(403, "Менять роль может только суперадмин")
        logger.info(f"{admin.username}: роль {user.username} {user.role} -> {data.role}")
        user.role = data.role
    if data.username and data.username != user.username:
        _ensure_username_free(db, data.username, exclude_id=user.id)
        user.username = data.username
    if data.password:
        user.password_hash = hash_password(data.password)
    if data.email and data.email != user.email:
        _ensure_email_free(db, data.email, exclude_id=user.id)
        user.email = data.email
    db.commit()
    return user


@router.delete(
    "/{user_id}",
    status_code=204,
    summary="Удаление пользователя",
    responses={**FORBIDDEN, **NOT_FOUND},
)
def delete_user(user_id: int, db: DB, admin: AdminUser):
    """История оплат сохраняется (в ней просто пропадает ссылка на пользователя)."""
    user = _get_manageable_user(db, user_id, admin)
    db.delete(user)
    db.commit()
    logger.info(f"{admin.username} удалил пользователя {user.username}")
    return Response(status_code=204)