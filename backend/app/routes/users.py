from flask import g
from flask.views import MethodView
from flask_smorest import Blueprint, abort

from app.auth import admin_required, hash_password
from app.extensions import db
from app.logging_config import get_logger
from app.models import User
from app.models.user import ROLE_USER
from app.schemas.users import UserCreateSchema, UserSchema, UserUpdateSchema
from app.services.audit import audit

logger = get_logger(__name__)

router = Blueprint(
    "users",
    __name__,
    url_prefix="/api/v1/users",
    description="Обычные пользователи. Только администратор. "
    "Учётные записи администраторов через API не управляются",
)


def _get_manageable_user(user_id: int) -> User:
    user = db.session.get(User, user_id)
    if user is None:
        abort(404, message="Пользователь не найден")
    if user.is_env_admin or user.is_admin:
        abort(403, message="Учётную запись администратора нельзя изменить через панель")
    return user


def _ensure_username_free(username: str, exclude_id: int | None = None):
    query = User.query.filter(db.func.lower(User.username) == username.lower())
    if exclude_id:
        query = query.filter(User.id != exclude_id)
    if query.first():
        abort(409, message="Пользователь с таким логином уже существует")


@router.route("")
class UserList(MethodView):
    @admin_required
    @router.response(200, UserSchema(many=True))
    @router.alt_response(403, description="Только администратор")
    def get(self):
        """Получение списка пользователей"""
        return User.query.order_by(User.role, User.username).all()

    @admin_required
    @router.arguments(UserCreateSchema)
    @router.response(201, UserSchema)
    @router.alt_response(403, description="Только администратор")
    @router.alt_response(409, description="Логин занят")
    def post(self, data):
        """Создание обычного пользователя

        Роль всегда `user`: создать администратора через API нельзя.
        """
        _ensure_username_free(data["username"])
        user = User(
            username=data["username"],
            password_hash=hash_password(data["password"]),
            role=ROLE_USER,
        )
        db.session.add(user)
        db.session.flush()
        audit("user.create", user=g.current_user, entity_type="user", entity_id=user.id,
              details={"username": user.username})
        db.session.commit()
        return user


@router.route("/<int:user_id>")
class UserItem(MethodView):
    @admin_required
    @router.response(200, UserSchema)
    @router.alt_response(403, description="Только администратор / учётная запись администратора")
    @router.alt_response(404, description="Пользователь не найден")
    def get(self, user_id):
        """Получение пользователя"""
        return db.session.get(User, user_id) or abort(404, message="Пользователь не найден")

    @admin_required
    @router.arguments(UserUpdateSchema)
    @router.response(200, UserSchema)
    @router.alt_response(403, description="Только администратор / учётная запись администратора")
    @router.alt_response(404, description="Пользователь не найден")
    @router.alt_response(409, description="Логин занят")
    def patch(self, data, user_id):
        """Изменение пользователя

        Можно сменить логин и/или пароль. Роль не меняется.
        """
        user = _get_manageable_user(user_id)
        changed = []
        if "username" in data and data["username"] != user.username:
            _ensure_username_free(data["username"], exclude_id=user.id)
            user.username = data["username"]
            changed.append("username")
        if "password" in data:
            user.password_hash = hash_password(data["password"])
            changed.append("password")
        if changed:
            audit("user.update", user=g.current_user, entity_type="user", entity_id=user.id,
                  details={"username": user.username, "changed": changed})
        db.session.commit()
        return user

    @admin_required
    @router.response(204)
    @router.alt_response(403, description="Только администратор / учётная запись администратора")
    @router.alt_response(404, description="Пользователь не найден")
    def delete(self, user_id):
        """Удаление пользователя

        История оплат сохраняется (в ней просто пропадает ссылка на пользователя).
        """
        user = _get_manageable_user(user_id)
        audit("user.delete", user=g.current_user, entity_type="user", entity_id=user.id,
              details={"username": user.username})
        db.session.delete(user)
        db.session.commit()
        return ""
