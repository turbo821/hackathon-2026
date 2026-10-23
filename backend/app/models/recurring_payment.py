from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.timeutils import utcnow

CURRENCIES = ("RUB", "USD", "EUR")

# Периодичность → шаг в месяцах. Обязательная часть — monthly.
PERIOD_MONTHS = {
    "monthly": 1,
    "quarterly": 3,
    "yearly": 12,
}
PERIODS = tuple(PERIOD_MONTHS)


class RecurringPayment(Base):
    """Шаблон регулярного платежа. Конкретные периоды — PaymentOccurrence.

    Поля шаблона копируются в каждый период при его создании, поэтому шаблон
    ничего не «подтягивает» при чтении: период — самодостаточная запись.
    """

    __tablename__ = "recurring_payments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    # Деньги — только Numeric/Decimal, никаких float
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    currency: Mapped[str] = mapped_column(String(3))
    period: Mapped[str] = mapped_column(String(16), default="monthly")
    # Дата первой (ближайшей на момент создания) оплаты
    first_due_date: Mapped[date] = mapped_column(Date)
    # Число месяца, от которого считаются все даты (31 → в феврале 28/29)
    anchor_day: Mapped[int] = mapped_column(Integer)

    # Мягкое удаление: история периодов сохраняется
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime)

    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    @property
    def months_step(self) -> int:
        return PERIOD_MONTHS[self.period]

    def __repr__(self) -> str:
        return f"<RecurringPayment {self.id} {self.name} {self.amount} {self.currency}>"
