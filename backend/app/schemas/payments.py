from marshmallow import ValidationError, fields, validate, validates_schema

from app.models.payment_occurrence import STATES, STATUSES
from app.models.recurring_payment import CURRENCIES, PERIODS
from app.schemas.common import BaseSchema, Money, UtcDateTime
from app.timeutils import today

# ---------- Регулярные платежи ----------


class RecurringPaymentCreateSchema(BaseSchema):
    name = fields.String(
        required=True,
        validate=validate.Length(min=1, max=200, error="Название: от 1 до 200 символов"),
        metadata={"example": "Аренда офиса"},
    )
    amount = Money(required=True, metadata={"type": "string", "example": "50000.00"})
    currency = fields.String(
        required=True,
        validate=validate.OneOf(CURRENCIES, error="Валюта: RUB, USD или EUR"),
        metadata={"example": "RUB"},
    )
    first_due_date = fields.Date(
        required=True,
        metadata={"description": "Дата ближайшей оплаты (YYYY-MM-DD)", "example": "2026-10-25"},
    )
    period = fields.String(
        load_default="monthly",
        validate=validate.OneOf(PERIODS),
        metadata={"description": "Периодичность: monthly (по умолчанию), quarterly, yearly"},
    )

    @validates_schema
    def strip_name(self, data, **kwargs):
        if "name" in data:
            data["name"] = data["name"].strip()
            if not data["name"]:
                raise ValidationError("Название не может быть пустым", "name")


class NextOccurrenceSchema(BaseSchema):
    id = fields.Integer()
    due_date = fields.Date()
    status = fields.String()
    state = fields.String()


class RecurringPaymentSchema(BaseSchema):
    id = fields.Integer()
    name = fields.String()
    amount = Money(metadata={"type": "string", "example": "50000.00"})
    currency = fields.String()
    period = fields.String()
    first_due_date = fields.Date()
    anchor_day = fields.Integer(metadata={"description": "Число месяца, от которого считаются даты"})
    is_active = fields.Boolean()
    ended_at = UtcDateTime(allow_none=True)
    created_at = UtcDateTime()
    next_occurrence = fields.Nested(
        NextOccurrenceSchema,
        allow_none=True,
        metadata={"description": "Ближайший неоплаченный период"},
    )


class RecurringPaymentQuerySchema(BaseSchema):
    include_inactive = fields.Boolean(
        load_default=False, metadata={"description": "Показывать прекращённые платежи"}
    )


# ---------- Периоды (оплаты) ----------


class OccurrenceSchema(BaseSchema):
    id = fields.Integer()
    recurring_payment_id = fields.Integer()
    name = fields.String()
    amount = Money(metadata={"type": "string", "example": "50000.00"})
    currency = fields.String()
    due_date = fields.Date(metadata={"description": "Срок оплаты этого периода"})
    status = fields.String(metadata={"enum": list(STATUSES)})
    paid_at = fields.Date(allow_none=True, metadata={"description": "Фактическая дата оплаты"})
    state = fields.String(
        metadata={
            "enum": list(STATES),
            "description": "pending — ждёт оплаты, overdue — просрочен, "
            "paid — оплачен вовремя, paid_late — оплачен с опозданием",
        }
    )
    is_overdue = fields.Boolean(metadata={"description": "Сейчас просрочен (не оплачен после срока)"})
    overdue_days = fields.Integer(
        metadata={"description": "Дней просрочки (для оплаченных — на дату оплаты)"}
    )
    days_until_due = fields.Integer(metadata={"description": "Дней до срока (<0 — срок прошёл)"})
    reminder_sent_at = UtcDateTime(allow_none=True)
    marked_by = fields.String(allow_none=True, metadata={"description": "Кто отметил оплату"})
    recurring_payment_active = fields.Boolean()


class OccurrenceQuerySchema(BaseSchema):
    state = fields.String(validate=validate.OneOf(STATES + ("unpaid_all",)), metadata={
        "description": "Фильтр по состоянию. unpaid_all = pending + overdue",
    })
    status = fields.String(validate=validate.OneOf(STATUSES))
    currency = fields.String(validate=validate.OneOf(CURRENCIES))
    recurring_payment_id = fields.Integer()
    date_from = fields.Date(metadata={"description": "Срок оплаты с (включительно)"})
    date_to = fields.Date(metadata={"description": "Срок оплаты по (включительно)"})
    include_inactive = fields.Boolean(
        load_default=True, metadata={"description": "Включать периоды прекращённых платежей"}
    )
    include_future = fields.Boolean(
        load_default=True, metadata={"description": "Включать ещё не наступившие периоды"}
    )
    order = fields.String(load_default="asc", validate=validate.OneOf(("asc", "desc")))


class OccurrenceUpdateSchema(BaseSchema):
    status = fields.String(
        validate=validate.OneOf(STATUSES, error="status: paid или unpaid"),
        metadata={"description": "paid — подтвердить оплату, unpaid — отменить"},
    )
    paid_at = fields.Date(
        allow_none=True,
        metadata={
            "description": "Фактическая дата оплаты. При status=paid без даты — сегодня. "
            "Можно передать без status, чтобы исправить дату у оплаченного периода."
        },
    )

    @validates_schema
    def check(self, data, **kwargs):
        if "status" not in data and "paid_at" not in data:
            raise ValidationError("Передайте status и/или paid_at")
        if data.get("status") == "unpaid" and data.get("paid_at"):
            raise ValidationError("При отмене оплаты дату передавать нельзя", "paid_at")
        if data.get("paid_at") and data["paid_at"] > today():
            raise ValidationError("Дата оплаты не может быть в будущем", "paid_at")


# ---------- Итоги ----------


class SummaryQuerySchema(BaseSchema):
    date_from = fields.Date(metadata={"description": "Срок оплаты с (включительно)"})
    date_to = fields.Date(metadata={"description": "Срок оплаты по (включительно)"})
    on_date = fields.Date(
        metadata={"description": "Дата, на которую считаются статусы и просрочка (по умолчанию сегодня)"}
    )


class CurrencyTotalsSchema(BaseSchema):
    currency = fields.String()
    total = Money(metadata={"type": "string"})
    paid = Money(metadata={"type": "string"})
    unpaid = Money(metadata={"type": "string"})
    overdue = Money(metadata={"type": "string"})
    count_total = fields.Integer()
    count_paid = fields.Integer()
    count_unpaid = fields.Integer()
    count_overdue = fields.Integer()


class SummarySchema(BaseSchema):
    date_from = fields.Date(allow_none=True)
    date_to = fields.Date(allow_none=True)
    on_date = fields.Date()
    currencies = fields.List(fields.Nested(CurrencyTotalsSchema))
