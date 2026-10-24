from fastapi import APIRouter, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth import DB, AdminUser, hash_password
from app.config import settings
from app.errors import ApiError
from app.models import User
from app.schemas.users import UserCreate, UserOut, UserUpdate

router = APIRouter(prefix="/users", tags=["users"])

FORBIDDEN = {403: {"description": "Только администратор / учётная запись администратора"}}
NOT_FOUND = {404: {"description": "Пользователь не найден"}}
CONFLICT = {409: {"description": "Логин или email занят"}}


def _get_manageable_user(db: Session, user_id: int) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise ApiError(404, "Пользователь не найден")
    if user.is_admin:
        raise ApiError(403, "Учётную запись администратора нельзя изменить через панель")
    return user


def _ensure_username_free(db: Session, username: str, exclude_id: int | None = None):
    # Логин администратора зарезервирован: иначе обычный пользователь занял бы
    # его логин, а сид потом переписал бы ему пароль из .env
    if username.strip().lower() == settings.admin_username.strip().lower():
        raise ApiError(409, "Этот логин зарезервирован под администратора из .env")
    query = select(User).where(func.lower(User.username) == username.lower())
    if exclude_id:
        query = query.where(User.id != exclude_id)
    if db.scalars(query).first():
        raise ApiError(409, "Пользователь с таким логином уже существует")


def _ensure_email_free(db: Session, email: str, exclude_id: int | None = None):
    # Email администратора зарезервирован так же, как логин
    if email == settings.admin_email.strip().lower():
        raise ApiError(409, "Этот email зарезервирован под администратора из .env")
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
    summary="Создание обычного пользователя",
    responses={**FORBIDDEN, **CONFLICT},
)
def create_user(data: UserCreate, db: DB, admin: AdminUser):
    """Создать администратора через API нельзя: он один и прописан в .env."""
    _ensure_username_free(db, data.username)
    _ensure_email_free(db, data.email)
    user = User(username=data.username, email=data.email, password_hash=hash_password(data.password))
    db.add(user)
    db.commit()
    return user


@router.patch(
    "/{user_id}",
    response_model=UserOut,
    summary="Изменение пользователя",
    responses={**FORBIDDEN, **NOT_FOUND, **CONFLICT},
)
def update_user(user_id: int, data: UserUpdate, db: DB, admin: AdminUser):
    """Можно сменить логин, пароль и email. Роль не меняется."""
    user = _get_manageable_user(db, user_id)
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
    user = _get_manageable_user(db, user_id)
    db.delete(user)
    db.commit()
    return Response(status_code=204)