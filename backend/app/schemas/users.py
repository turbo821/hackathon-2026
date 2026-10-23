from marshmallow import fields, validate

from app.schemas.common import BaseSchema, UtcDateTime

USERNAME = validate.Regexp(
    r"^[A-Za-z0-9_.\-]{3,64}$",
    error="Логин: 3–64 символа, латиница, цифры, точка, дефис, подчёркивание",
)
PASSWORD = validate.Length(min=6, max=72, error="Пароль: от 6 до 72 символов")


class UserSchema(BaseSchema):
    id = fields.Integer(dump_only=True)
    username = fields.String(dump_only=True)
    role = fields.String(dump_only=True, metadata={"enum": ["admin", "user"]})
    is_env_admin = fields.Boolean(
        dump_only=True,
        metadata={"description": "Администратор из .env — через API не изменяется"},
    )
    created_at = UtcDateTime(dump_only=True)


class UserCreateSchema(BaseSchema):
    username = fields.String(required=True, validate=USERNAME)
    password = fields.String(required=True, load_only=True, validate=PASSWORD)


class UserUpdateSchema(BaseSchema):
    username = fields.String(validate=USERNAME)
    password = fields.String(load_only=True, validate=PASSWORD)


class LoginSchema(BaseSchema):
    username = fields.String(required=True)
    password = fields.String(required=True, load_only=True)


class TokenSchema(BaseSchema):
    access_token = fields.String()
    token_type = fields.String(metadata={"example": "Bearer"})
    expires_at = UtcDateTime()
    user = fields.Nested(UserSchema)
