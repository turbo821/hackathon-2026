from datetime import datetime, timezone

from fastapi import APIRouter, Request
from sqlalchemy import select

from app.auth import DB, Auth, CurrentUser, create_access_token, verify_password
from app.errors import ApiError
from app.logging_config import get_logger
from app.models import RevokedToken, User
from app.schemas.common import MessageOut
from app.schemas.users import LoginIn, TokenOut, UserOut
from app.services.audit import audit

logger = get_logger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/login",
    response_model=TokenOut,
    summary="Вход по логину и паролю",
    responses={401: {"description": "Неверный логин или пароль"}},
)
def login(data: LoginIn, db: DB, request: Request):
    """Возвращает JWT. Дальше передавайте его в заголовке `Authorization: Bearer <token>`."""
    username = data.username.strip()
    user = db.scalars(select(User).where(User.username == username)).first()
    if user is None or not verify_password(data.password, user.password_hash):
        audit(db, "auth.login_failed", details={"username": username}, request=request, commit=True)
        logger.warning(f"Неудачная попытка входа: {username}")
        raise ApiError(401, "Неверный логин или пароль")

    token, expires_at = create_access_token(user.id)
    audit(db, "auth.login", user=user, request=request, commit=True)
    return {"access_token": token, "token_type": "Bearer", "expires_at": expires_at, "user": user}


@router.get("/me", response_model=UserOut, summary="Получение текущего пользователя")
def me(user: CurrentUser):
    return user


@router.post("/logout", response_model=MessageOut, summary="Завершение текущей сессии")
def logout(auth: Auth, db: DB, request: Request):
    """Токен попадает в список отозванных и больше не принимается."""
    payload = auth.token_payload
    expires_at = datetime.fromtimestamp(payload["exp"], tz=timezone.utc).replace(tzinfo=None)
    if not db.get(RevokedToken, payload["jti"]):
        db.add(RevokedToken(jti=payload["jti"], expires_at=expires_at))
    audit(db, "auth.logout", user=auth.user, request=request)
    db.commit()
    return {"message": "Сессия завершена"}
