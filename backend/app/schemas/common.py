"""Общие типы pydantic: деньги и метки времени."""

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Annotated

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, PlainSerializer, WithJsonSchema


def _money_in(value) -> Decimal:
    """Принимаем число или строку ("1500", "1 500,50") — на вход."""
    if value is None:
        raise ValueError("Сумма обязательна")
    try:
        amount = Decimal(str(value).strip().replace(" ", "").replace(",", "."))
    except (InvalidOperation, ValueError):
        raise ValueError("Сумма должна быть числом, например 1500.00")
    if amount <= 0:
        raise ValueError("Сумма должна быть больше нуля")
    return amount


# Вход: платёж нулём не бывает — сумма обязательна и больше нуля.
MoneyIn = Annotated[
    Decimal,
    BeforeValidator(_money_in),
    Field(max_digits=14, decimal_places=2),
]

# Выход: в ответе сумма — любое неотрицательное число (в итогах бывает 0.00),
# поэтому проверку «больше нуля» применяем только ко входным данным.
MoneyOut = Annotated[
    Decimal,
    Field(max_digits=14, decimal_places=2),
    PlainSerializer(lambda v: f"{Decimal(v):.2f}", return_type=str),
    WithJsonSchema({"type": "string", "example": "50000.00", "description": "Сумма, до 2 знаков после запятой"}),
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
