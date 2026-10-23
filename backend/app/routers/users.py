from fastapi import APIRouter, Request, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth import DB, AdminUser, hash_password
from app.errors import ApiError
from app.models import User
from app.models.user import ROLE_USER
from app.schemas.users import UserCreate, UserOut, UserUpdate
from app.services.audit import audit

router = APIRouter(prefix="/users", tags=["users"])

FORBIDDEN = {403: {"description": "Только администратор / учётная запись администратора"}}
NOT_FOUND = {404: {"description": "Пользователь не найден"}}
CONFLICT = {409: {"description": "Логин занят"}}


def _get_manageable_user(db: Session, user_id: int) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise ApiError(404, "Пользователь не найден")
    if user.is_env_admin or user.is_admin:
        raise ApiError(403, "Учётную запись администратора нельзя изменить через панель")
    return user


def _ensure_username_free(db: Session, username: str, exclude_id: int | None = None):
    query = select(User).where(func.lower(User.username) == username.lower())
    if exclude_id:
        query = query.where(User.id != exclude_id)
    if db.scalars(query).first():
        raise ApiError(409, "Пользователь с таким логином уже существует")


@router.get("", response_model=list[UserOut], summary="Получение списка пользователей", responses=FORBIDDEN)
def list_users(db: DB, admin: AdminUser):
    return db.scalars(select(User).order_by(User.role, User.username)).all()


@router.post(
    "",
    response_model=UserOut,
    status_code=201,
    summary="Создание обычного пользователя",
    responses={**FORBIDDEN, **CONFLICT},
)
def create_user(data: UserCreate, db: DB, admin: AdminUser, request: Request):
    """Роль всегда `user`: создать администратора через API нельзя."""
    _ensure_username_free(db, data.username)
    user = User(username=data.username, password_hash=hash_password(data.password), role=ROLE_USER)
    db.add(user)
    db.flush()
    audit(db, "user.create", user=admin, entity_type="user", entity_id=user.id,
          details={"username": user.username}, request=request)
    db.commit()
    return user


@router.get("/{user_id}", response_model=UserOut, summary="Получение пользователя", responses={**FORBIDDEN, **NOT_FOUND})
def get_user(user_id: int, db: DB, admin: AdminUser):
    user = db.get(User, user_id)
    if user is None:
        raise ApiError(404, "Пользователь не найден")
    return user


@router.patch(
    "/{user_id}",
    response_model=UserOut,
    summary="Изменение пользователя",
    responses={**FORBIDDEN, **NOT_FOUND, **CONFLICT},
)
def update_user(user_id: int, data: UserUpdate, db: DB, admin: AdminUser, request: Request):
    """Можно сменить логин и/или пароль. Роль не меняется."""
    user = _get_manageable_user(db, user_id)
    changed = []
    if data.username and data.username != user.username:
        _ensure_username_free(db, data.username, exclude_id=user.id)
        user.username = data.username
        changed.append("username")
    if data.password:
        user.password_hash = hash_password(data.password)
        changed.append("password")
    if changed:
        audit(db, "user.update", user=admin, entity_type="user", entity_id=user.id,
              details={"username": user.username, "changed": changed}, request=request)
    db.commit()
    return user


@router.delete(
    "/{user_id}",
    status_code=204,
    summary="Удаление пользователя",
    responses={**FORBIDDEN, **NOT_FOUND},
)
def delete_user(user_id: int, db: DB, admin: AdminUser, request: Request):
    """История оплат сохраняется (в ней просто пропадает ссылка на пользователя)."""
    user = _get_manageable_user(db, user_id)
    audit(db, "user.delete", user=admin, entity_type="user", entity_id=user.id,
          details={"username": user.username}, request=request)
    db.delete(user)
    db.commit()
    return Response(status_code=204)
