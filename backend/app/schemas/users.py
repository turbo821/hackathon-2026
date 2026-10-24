import re
from typing import Literal

from pydantic import Field, field_validator

from app.schemas.common import Schema, UtcDateTime

USERNAME_RE = re.compile(r"^[A-Za-z0-9_.\-]{3,64}$")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _check_username(value: str) -> str:
    value = value.strip()
    if not USERNAME_RE.match(value):
        raise ValueError(
            "Логин: 3–64 символа, латиница, цифры, точка, дефис, подчёркивание"
        )
    return value


def _check_password(value: str) -> str:
    if not 6 <= len(value) <= 72:
        raise ValueError("Пароль: от 6 до 72 символов")
    return value


def _check_email(value: str) -> str:
    value = value.strip().lower()
    if len(value) > 255 or not EMAIL_RE.match(value):
        raise ValueError("Некорректный email, пример: ivan@example.com")
    return value


class UserOut(Schema):
    id: int
    username: str
    email: str
    role: Literal["admin", "user"] = Field(
        description="Админ - из .env, нельзя изменить через панель"
    )
    telegram_id: int | None = Field(
        None, description="Telegram ID: привязан ли аккаунт к боту"
    )
    created_at: UtcDateTime


class UserCreate(Schema):
    username: str = Field(examples=["ivan"])
    password: str = Field(examples=["secret123"])
    email: str = Field(examples=["ivan@example.com"])

    @field_validator("username")
    @classmethod
    def v_username(cls, v: str) -> str:
        return _check_username(v)

    @field_validator("password")
    @classmethod
    def v_password(cls, v: str) -> str:
        return _check_password(v)

    @field_validator("email")
    @classmethod
    def v_email(cls, v: str) -> str:
        return _check_email(v)


class UserUpdate(Schema):
    username: str | None = None
    password: str | None = None
    email: str | None = None

    @field_validator("username")
    @classmethod
    def v_username(cls, v):
        return None if v is None else _check_username(v)

    @field_validator("password")
    @classmethod
    def v_password(cls, v):
        return None if v is None else _check_password(v)

    @field_validator("email")
    @classmethod
    def v_email(cls, v):
        return None if v is None else _check_email(v)


class UserMeUpdate(Schema):
    """Пользователь меняет только свой Telegram ID."""

    telegram_id: int | None = Field(
        None, description="Ваш Telegram ID: напишите боту — он ответит"
    )


class LoginIn(Schema):
    email: str = Field(examples=["admin@example.com"])
    password: str = Field(examples=["admin"])

    @field_validator("email")
    @classmethod
    def v_email(cls, v: str) -> str:
        # Без проверки формата: неверный email — это просто «неверный логин или пароль»
        return v.strip().lower()


class TokenOut(Schema):
    access_token: str
    token_type: str = Field(examples=["Bearer"])
    expires_at: UtcDateTime
    user: UserOut


class TelegramLinkOut(Schema):
    """Ссылка для привязки Telegram-аккаунта."""

    token: str
    url: str = Field(description="Открыть в Telegram — бот привяжет аккаунт")
    expires_at: UtcDateTime


class TelegramChatLinkOut(Schema):
    """Ссылка-приглашение в чат: по ней бот узнаёт Telegram ID вошедшего."""

    token: str
    url: str = Field(description="Ссылка-приглашение в чат Telegram")
    expires_at: UtcDateTime
