"""Общие типы pydantic: деньги и метки времени в формате, на который рассчитан фронтенд."""

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Annotated

from pydantic import BaseModel, BeforeValidator, ConfigDict, PlainSerializer, WithJsonSchema


def _parse_money(value) -> Decimal:
    if isinstance(value, bool) or value is None:
        raise ValueError("Сумма должна быть числом")
    try:
        amount = Decimal(str(value).strip().replace(" ", "").replace(",", "."))
    except (InvalidOperation, ValueError):
        raise ValueError("Сумма должна быть числом, например 1500.00")
    if not amount.is_finite():
        raise ValueError("Некорректная сумма")
    if amount <= 0:
        raise ValueError("Сумма должна быть больше нуля")
    if amount.as_tuple().exponent < -2:
        raise ValueError("Не больше двух знаков после запятой")
    if amount >= Decimal("1000000000000"):
        raise ValueError("Слишком большая сумма")
    return amount.quantize(Decimal("0.01"))


# Вход: число или строка ("1500", "1 500,50"). Выход: строка "1500.50" без потери точности.
MoneyIn = Annotated[
    Decimal,
    BeforeValidator(_parse_money),
    WithJsonSchema({"type": "string", "example": "50000.00", "description": "Сумма, до 2 знаков после запятой"}),
]
MoneyOut = Annotated[
    Decimal,
    PlainSerializer(lambda v: f"{Decimal(v):.2f}", return_type=str),
    WithJsonSchema({"type": "string", "example": "50000.00"}),
]


def _utc_iso(value: datetime) -> str:
    """Метки времени храним в БД как naive UTC; наружу отдаём с явным +00:00."""
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.isoformat()


UtcDateTime = Annotated[
    datetime,
    PlainSerializer(_utc_iso, return_type=str),
    WithJsonSchema({"type": "string", "format": "date-time"}),
]


class Schema(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class MessageOut(Schema):
    message: str
