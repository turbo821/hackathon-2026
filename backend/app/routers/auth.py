import uuid
from datetime import datetime, timedelta, timezone

from app.config import settings
from fastapi import APIRouter
from sqlalchemy import delete, select

from app.auth import DB, Auth, CurrentUser, create_access_token, verify_password
from app.errors import ApiError
from app.models import RevokedToken, TelegramLink, User
from app.schemas.common import MessageOut
from app.schemas.users import LoginIn, TelegramLinkOut, TokenOut, UserMeUpdate, UserOut
from app.services import telegram
from app.timeutils import utcnow

router = APIRouter(prefix="/auth", tags=["auth"])

LINK_TTL_MINUTES = 15


@router.post(
    "/login",
    response_model=TokenOut,
    summary="Вход по email и паролю",
    responses={401: {"description": "Неверный email или пароль"}},
)
def login(data: LoginIn, db: DB):
    """Возвращает JWT. Дальше передавайте его в заголовке `Authorization: Bearer <token>`."""
    user = db.scalars(select(User).where(User.email == data.email)).first()
    if user is None or not verify_password(data.password, user.password_hash):
        raise ApiError(401, "Неверный email или пароль")

    token, expires_at = create_access_token(user.id)
    return {
        "access_token": token,
        "token_type": "Bearer",
        "expires_at": expires_at,
        "user": user,
    }


@router.get("/me", response_model=UserOut, summary="Получение текущего пользователя")
def me(user: CurrentUser):
    return user


@router.patch("/me", response_model=UserOut, summary="Привязать свой Telegram ID")
def update_me(data: UserMeUpdate, db: DB, user: CurrentUser):
    """Пользователь сам привязывает свой Telegram ID — чтобы бот понимал,
    кто нажал «Оплачено» в сообщении. Передал null — отвязать."""
    if "telegram_id" in data.model_fields_set:
        if data.telegram_id is not None:
            other = db.scalars(
                select(User).where(
                    User.telegram_id == data.telegram_id, User.id != user.id
                )
            ).first()
            if other:
                raise ApiError(
                    409, "Этот Telegram ID уже привязан к другому пользователю"
                )
        user.telegram_id = data.telegram_id
        db.commit()
    return user


@router.post(
    "/telegram-link",
    response_model=TelegramLinkOut,
    summary="Ссылка для привязки Telegram-аккаунта",
)
def telegram_link(db: DB, user: CurrentUser):
    """Одноразовая ссылка: открыть её в Telegram — и бот привяжет аккаунт.
    Код живёт 15 минут и работает один раз: по ссылке, которую кто-то
    переслал в чат, чужой Telegram привязать нельзя.
    """
    username = telegram.bot_username()
    if not username:
        raise ApiError(
            503, "Не удалось узнать имя бота — укажите TELEGRAM_BOT_USERNAME в .env"
        )
    token = uuid.uuid4().hex
    expires_at = utcnow() + timedelta(minutes=LINK_TTL_MINUTES)
    db.add(TelegramLink(token=token, user_id=user.id, expires_at=expires_at))
    db.commit()
    return {
        "token": token,
        "url": f"https://t.me/{username}?start={token}",
        "expires_at": expires_at,
    }


@router.post("/logout", response_model=MessageOut, summary="Завершение текущей сессии")
def logout(auth: Auth, db: DB):
    """Токен попадает в список отозванных и больше не принимается."""
    payload = auth.token_payload
    expires_at = datetime.fromtimestamp(payload["exp"], tz=timezone.utc).replace(
        tzinfo=None
    )
    if not db.get(RevokedToken, payload["jti"]):
        db.add(RevokedToken(jti=payload["jti"], expires_at=expires_at))
    # Записи, чей токен и так истёк, больше не нужны: вычищаем их попутно
    db.execute(delete(RevokedToken).where(RevokedToken.expires_at < utcnow()))
    db.commit()
    return {"message": "Сессия завершена"}