from app.extensions import db
from app.timeutils import utcnow

CURRENCIES = ("RUB", "USD", "EUR")

# Периодичность → шаг в месяцах. Обязательная часть — monthly.
PERIOD_MONTHS = {
    "monthly": 1,
    "quarterly": 3,
    "yearly": 12,
}
PERIODS = tuple(PERIOD_MONTHS)


class RecurringPayment(db.Model):
    """Шаблон регулярного платежа. Конкретные периоды — PaymentOccurrence."""

    __tablename__ = "recurring_payments"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    # Деньги — только Numeric/Decimal, никаких float
    amount = db.Column(db.Numeric(14, 2), nullable=False)
    currency = db.Column(db.String(3), nullable=False)
    period = db.Column(db.String(16), nullable=False, default="monthly")
    # Дата первой (ближайшей на момент создания) оплаты
    first_due_date = db.Column(db.Date, nullable=False)
    # Число месяца, от которого считаются все даты (31 → в феврале 28/29)
    anchor_day = db.Column(db.Integer, nullable=False)

    # Мягкое удаление: история периодов сохраняется
    is_active = db.Column(db.Boolean, nullable=False, default=True, index=True)
    ended_at = db.Column(db.DateTime, nullable=True)

    created_by_id = db.Column(
        db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=utcnow, onupdate=utcnow)

    created_by = db.relationship("User", foreign_keys=[created_by_id])
    occurrences = db.relationship(
        "PaymentOccurrence",
        back_populates="recurring_payment",
        order_by="PaymentOccurrence.due_date",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    @property
    def months_step(self) -> int:
        return PERIOD_MONTHS[self.period]

    def __repr__(self) -> str:
        return f"<RecurringPayment {self.id} {self.name} {self.amount} {self.currency}>"
