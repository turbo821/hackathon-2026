"""Пароли, JWT и проверка прав.

Токен передаётся в заголовке `Authorization: Bearer <token>`.
Права проверяются на сервере в каждом эндпоинте (декораторы ниже),
поэтому ограничения действуют и в API, а не только в интерфейсе.
"""

import uuid
from datetime import datetime, timedelta, timezone
from functools import wraps

import bcrypt
import jwt
from flask import g, request
from flask_smorest import abort
from jwt.exceptions import ExpiredSignatureError, InvalidTokenError

from app.config import settings
from app.extensions import db
from app.logging_config import get_logger

logger = get_logger(__name__)

JWT_SECRET = settings.jwt_secret_key
ALGORITHM = settings.jwt_algorithm
ACCESS_TOKEN_EXPIRE_MINUTES = settings.access_token_expire_minutes


def hash_password(password: str) -> str:
    """Хеш пароля с bcrypt"""
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode()[:72], salt).decode()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Проверяет пароль с хешем"""
    try:
        return bcrypt.checkpw(plain_password.encode()[:72], hashed_password.encode())
    except ValueError:
        return False


def create_access_token(user_id: int, expires_delta: timedelta | None = None) -> tuple[str, datetime]:
    """Создаём JWT-токен. Возвращает (токен, момент истечения в UTC)."""
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    payload = {
        "sub": str(user_id),  # PyJWT требует строку в sub
        "jti": uuid.uuid4().hex,  # id токена — нужен для logout
        "exp": expire,  # стандартное поле: PyJWT сам проверяет истечение
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=ALGORITHM), expire


def decode_access_token(token: str) -> dict:
    """Декодируем JWT токен"""
    try:
        return jwt.decode(
            token, JWT_SECRET, algorithms=[ALGORITHM], options={"require": ["exp", "sub", "jti"]}
        )
    except ExpiredSignatureError:
        abort(401, message="Срок действия токена истёк")
    except InvalidTokenError:
        abort(401, message="Недействительный токен")


def _token_from_request() -> str | None:
    header = request.headers.get("Authorization", "")
    if header.lower().startswith("bearer "):
        return header[7:].strip() or None
    return None


def authenticate():
    """Достаёт пользователя из токена и кладёт в g.current_user / g.token_payload."""
    from app.models import RevokedToken, User

    token = _token_from_request()
    if not token:
        abort(401, message="Требуется авторизация")

    payload = decode_access_token(token)
    if db.session.get(RevokedToken, payload["jti"]):
        abort(401, message="Сессия завершена, войдите снова")

    user = db.session.get(User, int(payload["sub"]))
    if user is None:
        abort(401, message="Пользователь не найден")

    g.current_user = user
    g.token_payload = payload
    return user


def login_required(fn):
    """Любой авторизованный пользователь."""

    @wraps(fn)
    def wrapper(*args, **kwargs):
        authenticate()
        return fn(*args, **kwargs)

    return wrapper


def admin_required(fn):
    """Только администратор. Обычный пользователь получает 403 — и в панели, и в API."""

    @wraps(fn)
    def wrapper(*args, **kwargs):
        user = authenticate()
        if not user.is_admin:
            logger.warning(
                f"Отказ в доступе: {user.username} -> {request.method} {request.path}"
            )
            abort(403, message="Действие доступно только администратору")
        return fn(*args, **kwargs)

    return wrapper


def current_user():
    return g.get("current_user")
