"""Запись действий в журнал (таблица audit_logs) + дублирование в логгер."""

from flask import has_request_context, request

from app.extensions import db
from app.logging_config import get_logger
from app.models import AuditLog

logger = get_logger(__name__)


def audit(action: str, user=None, entity_type=None, entity_id=None, details=None, commit=False):
    """Добавляет запись в журнал. По умолчанию коммит делает вызывающий код."""
    ip = None
    if has_request_context():
        ip = request.headers.get("X-Forwarded-For", request.remote_addr)

    entry = AuditLog(
        user_id=user.id if user else None,
        username=user.username if user else (details or {}).get("username"),
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        details=details,
        ip=ip,
    )
    db.session.add(entry)
    if commit:
        db.session.commit()

    who = entry.username or "anonymous"
    target = f" {entity_type}#{entity_id}" if entity_type else ""
    logger.info(f"[audit] {who}: {action}{target} {details or ''}".rstrip())
    return entry
