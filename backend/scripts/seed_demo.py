"""Тестовые данные: аренда в рублях, сервер в долларах, подписка в евро.

Даты считаются от «сегодня», поэтому в любой день демо видно:
- просроченный период (аренда);
- срок через 2 дня → напоминание в Telegram (сервер);
- платёж 31-го числа с откатом на последний день месяца (подписка);
- оплату с опозданием (paid_late) в истории.

Идемпотентно: если платежи уже есть, ничего не делает.
Отключить: SEED_DEMO_DATA=false в .env.
"""

import os
from datetime import timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth import hash_password
from app.logging_config import get_logger
from app.models import PaymentOccurrence, RecurringPayment, User
from app.models.payment_occurrence import STATUS_PAID
from app.models.user import ROLE_USER
from app.services.periods import ensure_occurrences
from app.timeutils import add_months, today

logger = get_logger(__name__)

DEMO_USERS = [("user", "user12345"), ("anna", "anna12345")]


def run(db: Session):
    if os.getenv("SEED_DEMO_DATA", "true").lower() in ("0", "false", "no"):
        logger.info("demo: SEED_DEMO_DATA=false, пропускаю")
        return

    for username, password in DEMO_USERS:
        if not db.scalars(select(User).where(User.username == username)).first():
            db.add(User(username=username, password_hash=hash_password(password), role=ROLE_USER))
            logger.info(f"demo: создан пользователь {username} / {password}")
    db.commit()

    if db.scalar(select(func.count()).select_from(RecurringPayment)) > 0:
        logger.info("demo: платежи уже есть, пропускаю")
        return

    on = today()
    admin = db.scalars(select(User).where(User.is_env_admin.is_(True))).first()
    user = db.scalars(select(User).where(User.username == "user")).first()

    # Аренда: срок был 5 дней назад и не оплачен → просрочка. Раньше — 2 оплаченных месяца.
    rent_due = on - timedelta(days=5)
    rent = RecurringPayment(
        name="Аренда офиса", amount=Decimal("85000.00"), currency="RUB", period="monthly",
        first_due_date=add_months(rent_due, -2), anchor_day=rent_due.day,
    )
    # Сервер: срок через 2 дня → попадает в окно напоминания. Прошлый месяц оплачен.
    server_due = on + timedelta(days=2)
    server = RecurringPayment(
        name="VPS-сервер (Hetzner)", amount=Decimal("49.90"), currency="USD", period="monthly",
        first_due_date=add_months(server_due, -1), anchor_day=server_due.day,
    )
    # Подписка 31-го: в коротких месяцах дата — последний день месяца.
    subscription = RecurringPayment(
        name="Подписка Figma", amount=Decimal("15.00"), currency="EUR", period="monthly",
        first_due_date=add_months(on.replace(day=1), -2, 31), anchor_day=31,
    )

    payments = (rent, server, subscription)
    for rp in payments:
        rp.created_by_id = admin.id if admin else None
        db.add(rp)
    db.flush()
    for rp in payments:
        ensure_occurrences(db, rp, on)
    db.flush()

    def pay(rp, index, delay_days):
        occ = db.scalars(
            select(PaymentOccurrence)
            .where(PaymentOccurrence.recurring_payment_id == rp.id)
            .order_by(PaymentOccurrence.due_date)
        ).all()[index]
        occ.status = STATUS_PAID
        occ.paid_at = min(occ.due_date + timedelta(days=delay_days), on)
        occ.marked_by_id = user.id if user else None

    pay(rent, 0, 0)  # вовремя
    pay(rent, 1, 3)  # с опозданием на 3 дня
    pay(server, 0, -1)  # заранее
    pay(subscription, 0, 0)
    pay(subscription, 1, 1)
    db.commit()

    # После отметок могли понадобиться новые периоды
    for rp in payments:
        ensure_occurrences(db, rp, on)
    db.commit()
    logger.info("demo: созданы тестовые платежи (RUB, USD, EUR)")
