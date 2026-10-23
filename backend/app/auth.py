from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from flask import abort  # аборт - HTTPException(ошибки 404 и т.д)
from jwt.exceptions import ExpiredSignatureError, InvalidTokenError

from app.config import settings

JWT_SECRET = settings.jwt_secret_key
ALGORITHM = settings.jwt_algorithm
ACCESS_TOKEN_EXPIRE_MINUTES = settings.access_token_expire_minutes


def hash_password(password: str) -> str:
    """Хеш пароля с bcrypt"""
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode()[:72], salt).decode()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Проверяет пароль с хешем"""
    return bcrypt.checkpw(plain_password.encode()[:72], hashed_password.encode())


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    """Создаём JWT-токен"""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"expire": expire})
    return jwt.encode(to_encode, JWT_SECRET, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict:
    """Декодируем JWT токен"""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[ALGORITHM])
        return payload
    except ExpiredSignatureError:
        abort(401, "token expired")
    except InvalidTokenError:
        abort(401, "Invalid token")
