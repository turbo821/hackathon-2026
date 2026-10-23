from flask import g
from flask.views import MethodView
from flask_smorest import Blueprint, abort
from sqlalchemy.orm import selectinload

from app.auth import admin_required, login_required
from app.extensions import db
from app.logging_config import get_logger
from app.models import PaymentOccurrence, RecurringPayment
from app.models.payment_occurrence import STATUS_UNPAID
from app.schemas.payments import (
    RecurringPaymentCreateSchema,
    RecurringPaymentQuerySchema,
    RecurringPaymentSchema,
)
from app.services.audit import audit
from app.services.periods import ensure_all_occurrences, ensure_occurrences
from app.services.reminders import remind_for_payment
from app.services.serializers import recurring_payment_to_dict
from app.timeutils import today, utcnow

logger = get_logger(__name__)

router = Blueprint(
    "recurring_payments",
    __name__,
    url_prefix="/api/v1/recurring-payments",
    description="Регулярные платежи (шаблоны). Создание и удаление — только администратор",
)


@router.route("")
class RecurringPaymentList(MethodView):
    @login_required
    @router.arguments(RecurringPaymentQuerySchema, location="query")
    @router.response(200, RecurringPaymentSchema(many=True))
    def get(self, args):
        """Получение списка регулярных платежей

        По умолчанию только активные. `include_inactive=true` — вместе с прекращёнными.
        """
        on = today()
        ensure_all_occurrences(on)
        query = RecurringPayment.query.options(selectinload(RecurringPayment.occurrences))
        if not args["include_inactive"]:
            query = query.filter(RecurringPayment.is_active.is_(True))
        items = query.order_by(RecurringPayment.is_active.desc(), RecurringPayment.name).all()
        return [recurring_payment_to_dict(rp, on) for rp in items]

    @admin_required
    @router.arguments(RecurringPaymentCreateSchema)
    @router.response(201, RecurringPaymentSchema)
    @router.alt_response(403, description="Только администратор")
    def post(self, data):
        """Создание регулярного платежа

        Сразу создаются периоды. Если срок ближайшей оплаты ближе, чем через 3 дня,
        напоминание в Telegram отправляется сразу.
        """
        on = today()
        rp = RecurringPayment(
            name=data["name"],
            amount=data["amount"],
            currency=data["currency"],
            period=data["period"],
            first_due_date=data["first_due_date"],
            anchor_day=data["first_due_date"].day,
            created_by_id=g.current_user.id,
        )
        db.session.add(rp)
        db.session.flush()
        ensure_occurrences(rp, on)
        audit(
            "recurring_payment.create",
            user=g.current_user,
            entity_type="recurring_payment",
            entity_id=rp.id,
            details={
                "name": rp.name,
                "amount": f"{rp.amount:.2f}",
                "currency": rp.currency,
                "first_due_date": rp.first_due_date.isoformat(),
                "period": rp.period,
            },
        )
        db.session.commit()

        # Напоминание сразу, если срок уже в окне 3 дней. Ошибка Telegram не ломает создание.
        try:
            remind_for_payment(rp, on)
        except Exception:
            logger.exception(f"Не удалось проверить напоминание для платежа #{rp.id}")
            db.session.rollback()

        db.session.refresh(rp)
        return recurring_payment_to_dict(rp, on)


@router.route("/<int:payment_id>")
class RecurringPaymentItem(MethodView):
    @login_required
    @router.response(200, RecurringPaymentSchema)
    @router.alt_response(404, description="Платёж не найден")
    def get(self, payment_id):
        """Получение регулярного платежа"""
        rp = db.session.get(RecurringPayment, payment_id) or abort(404, message="Платёж не найден")
        on = today()
        if ensure_occurrences(rp, on):
            db.session.commit()
        return recurring_payment_to_dict(rp, on)

    @admin_required
    @router.response(204)
    @router.alt_response(403, description="Только администратор")
    @router.alt_response(404, description="Платёж не найден")
    def delete(self, payment_id):
        """Прекращение регулярного платежа и его напоминаний с сохранением истории

        Платёж помечается неактивным: новые периоды и напоминания больше не создаются.
        Оплаченные и уже наступившие периоды остаются в истории;
        будущие неоплаченные периоды удаляются.
        """
        rp = db.session.get(RecurringPayment, payment_id)
        if rp is None or not rp.is_active:
            abort(404, message="Платёж не найден или уже прекращён")

        on = today()
        future_unpaid = PaymentOccurrence.query.filter(
            PaymentOccurrence.recurring_payment_id == rp.id,
            PaymentOccurrence.status == STATUS_UNPAID,
            PaymentOccurrence.due_date > on,
        ).all()
        for occ in future_unpaid:
            db.session.delete(occ)

        rp.is_active = False
        rp.ended_at = utcnow()
        audit(
            "recurring_payment.delete",
            user=g.current_user,
            entity_type="recurring_payment",
            entity_id=rp.id,
            details={"name": rp.name, "removed_future_periods": len(future_unpaid)},
        )
        db.session.commit()
        return ""
