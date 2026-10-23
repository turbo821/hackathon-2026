import re
from typing import Literal

from pydantic import Field, field_validator

from app.schemas.common import Schema, UtcDateTime

USERNAME_RE = re.compile(r"^[A-Za-z0-9_.\-]{3,64}$")


def _check_username(value: str) -> str:
    value = value.strip()
    if not USERNAME_RE.match(value):
        raise ValueError("Логин: 3–64 символа, латиница, цифры, точка, дефис, подчёркивание")
    return value


def _check_password(value: str) -> str:
    if not 6 <= len(value) <= 72:
        raise ValueError("Пароль: от 6 до 72 символов")
    return value


class UserOut(Schema):
    id: int
    username: str
    role: Literal["admin", "user"]
    is_env_admin: bool = Field(description="Администратор из .env — через API не изменяется")
    created_at: UtcDateTime


class UserCreate(Schema):
    username: str = Field(examples=["ivan"])
    password: str = Field(examples=["secret123"])

    @field_validator("username")
    @classmethod
    def v_username(cls, v: str) -> str:
        return _check_username(v)

    @field_validator("password")
    @classmethod
    def v_password(cls, v: str) -> str:
        return _check_password(v)


class UserUpdate(Schema):
    username: str | None = None
    password: str | None = None

    @field_validator("username")
    @classmethod
    def v_username(cls, v):
        return None if v is None else _check_username(v)

    @field_validator("password")
    @classmethod
    def v_password(cls, v):
        return None if v is None else _check_password(v)


class LoginIn(Schema):
    username: str = Field(examples=["admin"])
    password: str = Field(examples=["admin"])


class TokenOut(Schema):
    access_token: str
    token_type: str = Field(examples=["Bearer"])
    expires_at: UtcDateTime
    user: UserOut
