from datetime import datetime, timezone

from flask import g
from flask.views import MethodView
from flask_smorest import Blueprint, abort

from app.auth import create_access_token, login_required, verify_password
from app.extensions import db
from app.logging_config import get_logger
from app.models import RevokedToken, User
from app.schemas.common import MessageSchema
from app.schemas.users import LoginSchema, TokenSchema, UserSchema
from app.services.audit import audit

logger = get_logger(__name__)

router = Blueprint(
    "auth", __name__, url_prefix="/api/v1/auth", description="Вход, текущий пользователь, выход"
)


@router.route("/login")
class Login(MethodView):
    @router.doc(security=[])
    @router.arguments(LoginSchema)
    @router.response(200, TokenSchema)
    @router.alt_response(401, description="Неверный логин или пароль")
    def post(self, data):
        """Вход по логину и паролю

        Возвращает JWT. Дальше передавайте его в заголовке `Authorization: Bearer <token>`.
        """
        username = data["username"].strip()
        user = User.query.filter_by(username=username).first()
        if user is None or not verify_password(data["password"], user.password_hash):
            audit("auth.login_failed", details={"username": username}, commit=True)
            logger.warning(f"Неудачная попытка входа: {username}")
            abort(401, message="Неверный логин или пароль")

        token, expires_at = create_access_token(user.id)
        audit("auth.login", user=user, commit=True)
        return {
            "access_token": token,
            "token_type": "Bearer",
            "expires_at": expires_at,
            "user": user,
        }


@router.route("/me")
class Me(MethodView):
    @login_required
    @router.response(200, UserSchema)
    @router.alt_response(401, description="Не авторизован")
    def get(self):
        """Получение текущего пользователя"""
        return g.current_user


@router.route("/logout")
class Logout(MethodView):
    @login_required
    @router.response(200, MessageSchema)
    @router.alt_response(401, description="Не авторизован")
    def post(self):
        """Завершение текущей сессии

        Токен попадает в список отозванных и больше не принимается.
        """
        payload = g.token_payload
        expires_at = datetime.fromtimestamp(payload["exp"], tz=timezone.utc).replace(tzinfo=None)
        if not db.session.get(RevokedToken, payload["jti"]):
            db.session.add(RevokedToken(jti=payload["jti"], expires_at=expires_at))
        audit("auth.logout", user=g.current_user)
        db.session.commit()
        return {"message": "Сессия завершена"}
