from datetime import timezone
from decimal import Decimal, InvalidOperation

from marshmallow import Schema, ValidationError, fields


class BaseSchema(Schema):
    class Meta:
        ordered = True


class Money(fields.Field):
    """Сумма: принимаем число или строку, отдаём строкой «1500.00» (без потери точности)."""

    def _serialize(self, value, attr, obj, **kwargs):
        if value is None:
            return None
        return f"{Decimal(value):.2f}"

    def _deserialize(self, value, attr, data, **kwargs):
        if isinstance(value, bool):
            raise ValidationError("Сумма должна быть числом")
        try:
            amount = Decimal(str(value).strip().replace(",", "."))
        except (InvalidOperation, ValueError):
            raise ValidationError("Сумма должна быть числом, например 1500.00")
        if not amount.is_finite():
            raise ValidationError("Некорректная сумма")
        if amount <= 0:
            raise ValidationError("Сумма должна быть больше нуля")
        if amount.as_tuple().exponent < -2:
            raise ValidationError("Не больше двух знаков после запятой")
        if amount >= Decimal("1000000000000"):
            raise ValidationError("Слишком большая сумма")
        return amount.quantize(Decimal("0.01"))


class UtcDateTime(fields.DateTime):
    """Метки времени храним в БД как naive UTC; наружу отдаём с явным +00:00."""

    def _serialize(self, value, attr, obj, **kwargs):
        if value is not None and value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return super()._serialize(value, attr, obj, **kwargs)


class MessageSchema(BaseSchema):
    message = fields.String()
