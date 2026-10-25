"""Пароли, JWT и проверка прав.

Токен передаётся в заголовке `Authorization: Bearer <token>`.
Права проверяются на сервере в каждом эндпоинте через зависимости
CurrentUser / AdminUser, поэтому ограничения действуют и в API, а не только в интерфейсе.
"""

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Annotated

import bcrypt
import jwt
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt.exceptions import ExpiredSignatureError, InvalidTokenError
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.errors import ApiError
from app.logging_config import get_logger, user_var
from app.models import RevokedToken, User

logger = get_logger(__name__)

# auto_error=False: без токена отдаём 401 (а не 403, как по умолчанию в FastAPI)
bearer_scheme = HTTPBearer(
    auto_error=False, description="JWT из POST /api/v1/auth/login"
)


def hash_password(password: str) -> str:
    """Хеш пароля с bcrypt"""
    return bcrypt.hashpw(password.encode()[:72], bcrypt.gensalt()).decode()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Проверяет пароль с хешем"""
    try:
        return bcrypt.checkpw(plain_password.encode()[:72], hashed_password.encode())
    except ValueError:
        return False


def create_access_token(
    user_id: int, expires_delta: timedelta | None = None
) -> tuple[str, datetime]:
    """Создаём JWT-токен. Возвращает (токен, момент истечения в UTC)."""
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.access_token_expire_minutes)
    )
    payload = {
        "sub": str(user_id),  # PyJWT требует строку в sub
        "jti": uuid.uuid4().hex,  # id токена — нужен для logout
        "exp": expire,  # стандартное поле: PyJWT сам проверяет истечение
    }
    return jwt.encode(
        payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm
    ), expire


def decode_access_token(token: str) -> dict:
    """Декодируем JWT токен"""
    try:
        return jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
            options={"require": ["exp", "sub", "jti"]},
        )
    except ExpiredSignatureError:
        raise ApiError(401, "Срок действия токена истёк")
    except InvalidTokenError:
        raise ApiError(401, "Недействительный токен")


@dataclass
class AuthContext:
    user: User
    token_payload: dict


def get_auth(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    db: Annotated[Session, Depends(get_db)],
) -> AuthContext:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise ApiError(401, "Требуется авторизация")

    payload = decode_access_token(credentials.credentials)
    if db.get(RevokedToken, payload["jti"]):
        raise ApiError(401, "Сессия завершена, войдите снова")

    user = db.get(User, int(payload["sub"]))
    if user is None:
        raise ApiError(401, "Пользователь не найден")
    # Кладём пользователя в контекст запроса: дальше любая запись лога
    # внутри обработчика будет показывать, чей это запрос.
    user_var.set(f"{user.username}#{user.id}")
    # Дублируем в request.state: middleware логирует обращение уже после
    # обработчика, и ему нужен пользователь независимо от того, как тот
    # уложился в задачу.
    request.state.user_ref = f"{user.username}#{user.id}"
    return AuthContext(user=user, token_payload=payload)


def get_current_user(auth: Annotated[AuthContext, Depends(get_auth)]) -> User:
    """Любой авторизованный пользователь."""
    return auth.user


def get_admin_user(
    request: Request, user: Annotated[User, Depends(get_current_user)]
) -> User:
    """Только администратор. Обычный пользователь получает 403 — и в панели, и в API."""
    if not user.is_admin:
        logger.warning(
            f"Отказ в доступе: {user.username} -> {request.method} {request.url.path}"
        )
        raise ApiError(403, "Действие доступно только администратору")
    return user


# Короткие алиасы для сигнатур эндпоинтов
DB = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_current_user)]
AdminUser = Annotated[User, Depends(get_admin_user)]
Auth = Annotated[AuthContext, Depends(get_auth)]
