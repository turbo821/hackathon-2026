"""Журнал действий и health-check."""

from fastapi import APIRouter, Query
from sqlalchemy import select, text

from app.auth import DB, AdminUser
from app.config import settings
from app.models import AuditLog
from app.schemas.payments import AuditLogOut
from app.services import telegram
from app.timeutils import today

router = APIRouter()


@router.get(
    "/audit-logs",
    response_model=list[AuditLogOut],
    tags=["audit-logs"],
    summary="Журнал действий (последние записи)",
    responses={403: {"description": "Только администратор"}},
)
def audit_logs(
    db: DB,
    admin: AdminUser,
    action: str | None = Query(None, description="Например auth.login, occurrence.mark_paid"),
    user_id: int | None = None,
    limit: int = Query(100, ge=1, le=1000),
):
    query = select(AuditLog)
    if action:
        query = query.where(AuditLog.action == action)
    if user_id:
        query = query.where(AuditLog.user_id == user_id)
    return db.scalars(query.order_by(AuditLog.id.desc()).limit(limit)).all()


@router.get("/health", tags=["service"], summary="Проверка, что сервис и БД живы")
def health(db: DB):
    db.execute(text("SELECT 1"))
    return {
        "status": "ok",
        "today": today().isoformat(),
        "timezone": settings.app_timezone,
        "telegram_configured": telegram.is_configured(),
    }
