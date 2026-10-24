from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.timeutils import utcnow

STATUS_PAID = "paid"
STATUS_UNPAID = "unpaid"
STATUSES = (STATUS_PAID, STATUS_UNPAID)

# Вычисляемое состояние периода (в БД не хранится)
STATE_PENDING = "pending"  # не оплачено, срок не прошёл
STATE_OVERDUE = "overdue"  # не оплачено, срок прошёл
STATE_PAID = "paid"  # оплачено вовремя (в том числе в день срока)
STATE_PAID_LATE = "paid_late"  # оплачено после срока
STATES = (STATE_PENDING, STATE_OVERDUE, STATE_PAID, STATE_PAID_LATE)


class PaymentOccurrence(Base):
    """Конкретный период регулярного платежа: своя дата и своя отметка оплаты.

    Название, сумма и валюта — копия полей шаблона на момент создания периода.
    Шаблон нельзя изменить через API (в кейсе есть только создать и прекратить),
    поэтому данные не расходятся, а список периодов читается из одной таблицы
    без JOIN.
    """

    __tablename__ = "payment_occurrences"
    __table_args__ = (
        # Один период на дату — защита от дублей при параллельной генерации
        UniqueConstraint("recurring_payment_id", "due_date", name="uq_occurrence_payment_due_date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    recurring_payment_id: Mapped[int] = mapped_column(
        ForeignKey("recurring_payments.id", ondelete="CASCADE"), index=True
    )
    # Слепок шаблона: период читается сам по себе, без JOIN
    name: Mapped[str] = mapped_column(String(200))
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    currency: Mapped[str] = mapped_column(String(3), index=True)
    due_date: Mapped[date] = mapped_column(Date, index=True)
    status: Mapped[str] = mapped_column(String(16), default=STATUS_UNPAID, index=True)
    # Фактическая дата оплаты; при отмене отметки очищается
    paid_at: Mapped[date | None] = mapped_column(Date)
    marked_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    # Когда платёж прекратили: NULL → платёж активен
    payment_ended_at: Mapped[datetime | None] = mapped_column(DateTime)
    # Когда отправлено напоминание: NULL → ещё не напоминали (защита от дублей)
    reminder_sent_at: Mapped[datetime | None] = mapped_column(DateTime)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    marked_by = relationship("User", foreign_keys=[marked_by_id])

    # --- Просрочка вычисляется, а не хранится: исправили paid_at → пересчиталась ---

    def overdue_days(self, on: date) -> int:
        """Сколько дней просрочки. Оплата в день срока — вовремя (0)."""
        if self.status == STATUS_PAID and self.paid_at:
            return max((self.paid_at - self.due_date).days, 0)
        return max((on - self.due_date).days, 0)

    def state(self, on: date) -> str:
        if self.status == STATUS_PAID:
            return STATE_PAID_LATE if self.overdue_days(on) > 0 else STATE_PAID
        return STATE_OVERDUE if on > self.due_date else STATE_PENDING

    def __repr__(self) -> str:
        return f"<PaymentOccurrence {self.id} rp={self.recurring_payment_id} {self.due_date} {self.status}>"
