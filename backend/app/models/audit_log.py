from app.extensions import db
from app.timeutils import utcnow


class AuditLog(db.Model):
    """Журнал авторизации и действий пользователей (доп. фича «Логи»)."""

    __tablename__ = "audit_logs"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    # Логин на момент действия — чтобы запись читалась и после удаления пользователя
    username = db.Column(db.String(64), nullable=True)
    action = db.Column(db.String(64), nullable=False, index=True)
    entity_type = db.Column(db.String(64), nullable=True)
    entity_id = db.Column(db.Integer, nullable=True)
    details = db.Column(db.JSON, nullable=True)
    ip = db.Column(db.String(64), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow, index=True)
