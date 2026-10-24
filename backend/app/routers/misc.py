"""Служебные ручки: проверка живости и приветствие фронта."""

from fastapi import APIRouter
from sqlalchemy import text

from app.auth import DB
from app.config import settings
from app.services import telegram
from app.timeutils import today

router = APIRouter()


@router.get("/hello", tags=["service"], summary="Проверка, что API отвечает")
def hello():
    """Простейшая ручка: фронт здоровается с бекендом."""
    return {"message": "Invoice Keeper API на связи"}


@router.get("/health", tags=["service"], summary="Проверка, что сервис и БД живы")
def health(db: DB):
    db.execute(text("SELECT 1"))
    return {
        "status": "ok",
        "today": today().isoformat(),
        "timezone": settings.app_timezone,
        "telegram_configured": telegram.is_configured(),
    }
