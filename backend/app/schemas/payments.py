from datetime import date
from typing import Literal

from pydantic import Field, field_validator, model_validator

from app.schemas.common import MoneyIn, MoneyOut, Schema, UtcDateTime
from app.timeutils import today

Currency = Literal["RUB", "USD", "EUR"]
Period = Literal["monthly", "quarterly", "yearly"]
Status = Literal["paid", "unpaid"]
State = Literal["pending", "overdue", "paid", "paid_late"]

# ---------- Регулярные платежи ----------


class RecurringPaymentCreate(Schema):
    name: str = Field(examples=["Аренда офиса"])
    amount: MoneyIn
    currency: Currency = Field(examples=["RUB"])
    first_due_date: date = Field(description="Дата ближайшей оплаты (YYYY-MM-DD)", examples=["2026-10-25"])
    period: Period = Field("monthly", description="Периодичность: monthly (по умолчанию), quarterly, yearly")

    @field_validator("name")
    @classmethod
    def strip_name(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Название не может быть пустым")
        if len(v) > 200:
            raise ValueError("Название: от 1 до 200 символов")
        return v


class NextOccurrence(Schema):
    id: int
    due_date: date
    status: Status
    state: State


class RecurringPaymentOut(Schema):
    id: int
    name: str
    amount: MoneyOut
    currency: Currency
    period: Period
    first_due_date: date
    anchor_day: int = Field(description="Число месяца, от которого считаются даты")
    is_active: bool
    ended_at: UtcDateTime | None
    created_at: UtcDateTime
    next_occurrence: NextOccurrence | None = Field(description="Ближайший неоплаченный период")


# ---------- Периоды (оплаты) ----------


class OccurrenceOut(Schema):
    id: int
    recurring_payment_id: int
    name: str
    amount: MoneyOut
    currency: Currency
    due_date: date = Field(description="Срок оплаты этого периода")
    status: Status
    paid_at: date | None = Field(description="Фактическая дата оплаты")
    state: State = Field(
        description="pending — ждёт оплаты, overdue — просрочен, "
        "paid — оплачен вовремя, paid_late — оплачен с опозданием"
    )
    is_overdue: bool = Field(description="Сейчас просрочен (не оплачен после срока)")
    overdue_days: int = Field(description="Дней просрочки (для оплаченных — на дату оплаты)")
    days_until_due: int = Field(description="Дней до срока (<0 — срок прошёл)")
    reminder_sent_at: UtcDateTime | None
    marked_by: str | None = Field(description="Кто отметил оплату")
    recurring_payment_active: bool


class OccurrenceUpdate(Schema):
    """Передайте status и/или paid_at."""

    status: Status | None = Field(None, description="paid — подтвердить оплату, unpaid — отменить")
    paid_at: date | None = Field(
        None,
        description="Фактическая дата оплаты. При status=paid без даты — сегодня. "
        "Можно передать без status, чтобы исправить дату у оплаченного периода.",
    )

    @model_validator(mode="after")
    def check(self):
        if "status" not in self.model_fields_set and "paid_at" not in self.model_fields_set:
            raise ValueError("Передайте status и/или paid_at")
        if self.status == "unpaid" and self.paid_at:
            raise ValueError("При отмене оплаты дату передавать нельзя")
        if self.paid_at and self.paid_at > today():
            raise ValueError("Дата оплаты не может быть в будущем")
        return self


# ---------- Итоги ----------


class CurrencyTotals(Schema):
    currency: Currency
    total: MoneyOut
    paid: MoneyOut
    unpaid: MoneyOut
    overdue: MoneyOut
    count_total: int
    count_paid: int
    count_unpaid: int
    count_overdue: int


class SummaryOut(Schema):
    date_from: date | None
    date_to: date | None
    on_date: date
    currencies: list[CurrencyTotals]


# ---------- Журнал ----------


class AuditLogOut(Schema):
    id: int
    created_at: UtcDateTime
    user_id: int | None
    username: str | None
    action: str
    entity_type: str | None
    entity_id: int | None
    details: dict | None
    ip: str | None
