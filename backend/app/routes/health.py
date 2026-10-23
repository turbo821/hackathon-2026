from flask.views import MethodView
from flask_smorest import Blueprint
from sqlalchemy import text

from app.config import settings
from app.extensions import db
from app.services import telegram
from app.timeutils import today

router = Blueprint("health", __name__, url_prefix="/api/v1", description="Служебное")


@router.route("/health")
class Health(MethodView):
    @router.doc(security=[])
    @router.response(200)
    def get(self):
        """Проверка, что сервис и БД живы"""
        db.session.execute(text("SELECT 1"))
        return {
            "status": "ok",
            "today": today().isoformat(),
            "timezone": settings.app_timezone,
            "telegram_configured": telegram.is_configured(),
        }
