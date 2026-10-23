"""Запись действий в журнал (таблица audit_logs) + дублирование в логгер."""

from fastapi import Request
from sqlalchemy.orm import Session

from app.logging_config import get_logger
from app.models import AuditLog

logger = get_logger(__name__)


def client_ip(request: Request | None) -> str | None:
    if request is None:
        return None
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else None


def audit(
    db: Session,
    action: str,
    user=None,
    entity_type: str | None = None,
    entity_id: int | None = None,
    details: dict | None = None,
    request: Request | None = None,
    commit: bool = False,
) -> AuditLog:
    """Добавляет запись в журнал. По умолчанию коммит делает вызывающий код."""
    entry = AuditLog(
        user_id=user.id if user else None,
        username=user.username if user else (details or {}).get("username"),
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        details=details,
        ip=client_ip(request),
    )
    db.add(entry)
    if commit:
        db.commit()

    who = entry.username or "anonymous"
    target = f" {entity_type}#{entity_id}" if entity_type else ""
    logger.info(f"[audit] {who}: {action}{target} {details or ''}".rstrip())
    return entry
