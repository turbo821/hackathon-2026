from flask.views import MethodView
from flask_smorest import Blueprint
from marshmallow import fields, validate

from app.auth import admin_required
from app.models import AuditLog
from app.schemas.common import BaseSchema, UtcDateTime

router = Blueprint(
    "audit_logs",
    __name__,
    url_prefix="/api/v1/audit-logs",
    description="Журнал авторизации и действий (доп. фича). Только администратор",
)


class AuditLogSchema(BaseSchema):
    id = fields.Integer()
    created_at = UtcDateTime()
    user_id = fields.Integer(allow_none=True)
    username = fields.String(allow_none=True)
    action = fields.String()
    entity_type = fields.String(allow_none=True)
    entity_id = fields.Integer(allow_none=True)
    details = fields.Dict(allow_none=True)
    ip = fields.String(allow_none=True)


class AuditLogQuerySchema(BaseSchema):
    action = fields.String(metadata={"description": "Например auth.login, occurrence.mark_paid"})
    user_id = fields.Integer()
    limit = fields.Integer(load_default=100, validate=validate.Range(min=1, max=1000))


@router.route("")
class AuditLogList(MethodView):
    @admin_required
    @router.arguments(AuditLogQuerySchema, location="query")
    @router.response(200, AuditLogSchema(many=True))
    @router.alt_response(403, description="Только администратор")
    def get(self, args):
        """Журнал действий (последние записи)"""
        query = AuditLog.query
        if args.get("action"):
            query = query.filter(AuditLog.action == args["action"])
        if args.get("user_id"):
            query = query.filter(AuditLog.user_id == args["user_id"])
        return query.order_by(AuditLog.id.desc()).limit(args["limit"]).all()
