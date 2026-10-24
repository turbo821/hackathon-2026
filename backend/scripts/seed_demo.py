"""Тестовые данные: аренда в рублях, сервер в долларах, подписка в евро.

Запуск: python -m scripts.seed_demo (или вместе со всеми — scripts.seed_all)

Идемпотентно: если платежи уже есть, ничего не делает.
Отключить: SEED_DEMO_DATA=false в .env.

На этапе «каркас» создаются только шаблоны платежей и два обычных пользователя.
Периоды (PaymentOccurrence) появятся, когда будет реализована генерация
периодов — см. app/services/periods.py.
"""

from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth import hash_password
from app.config import settings
from app.logging_config import get_logger
from app.models import RecurringPayment, User
from app.timeutils import today

logger = get_logger(__name__)

DEMO_USERS = [
    ("user", "user12345", "user@example.com"),
    ("anna", "anna12345", "anna@example.com"),
]


def run(db: Session):
    if not settings.seed_demo_data:
        logger.info("demo: SEED_DEMO_DATA=false, пропускаю")
        return

    for username, password, email in DEMO_USERS:
        if not db.scalars(select(User).where(User.username == username)).first():
            db.add(User(username=username, email=email, password_hash=hash_password(password)))
            logger.info(f"demo: создан пользователь {username} / {password} ({email})")
    db.commit()

    if db.scalar(select(func.count()).select_from(RecurringPayment)) > 0:
        logger.info("demo: платежи уже есть, пропускаю")
        return

    on = today()
    admin = db.scalars(select(User).where(User.username == settings.admin_username.strip())).first()

    # Аренда — рубли, сервер — доллары, подписка — евро.
    # Даты считаются от «сегодня», поэтому демо актуально в любой день.
    payments = [
        RecurringPayment(
            name="Аренда офиса",
            amount=Decimal("85000.00"),
            currency="RUB",
            period="monthly",
            first_due_date=on,
            anchor_day=on.day,
        ),
        RecurringPayment(
            name="VPS-сервер (Hetzner)",
            amount=Decimal("49.90"),
            currency="USD",
            period="monthly",
            first_due_date=on,
            anchor_day=on.day,
        ),
        RecurringPayment(
            name="Подписка Figma",
            amount=Decimal("15.00"),
            currency="EUR",
            period="monthly",
            first_due_date=on,
            anchor_day=on.day,
        ),
    ]
    for rp in payments:
        rp.created_by_id = admin.id if admin else None
        db.add(rp)
    db.commit()
    logger.info("demo: созданы тестовые платежи (RUB, USD, EUR)")