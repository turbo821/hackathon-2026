"""Тестовые данные: администратор, два пользователя и платежи
(аренда в рублях, сервер в долларах, подписка в евро).

Запуск: python -m scripts.seed_demo (или вместе со всеми — scripts.seed_all)

Идемпотентно: существующие пользователи и платежи не трогаются.
Отключить: SEED_DEMO_DATA=false в .env.
"""

from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth import hash_password
from app.config import settings
from app.logging_config import get_logger
from app.models import RecurringPayment, User
from app.models.user import ROLE_ADMIN, ROLE_USER
from app.timeutils import today

logger = get_logger(__name__)

# (логин, пароль, email, роль)
DEMO_USERS = [
    ("manager", "manager12345", "manager@example.com", ROLE_ADMIN),
    ("user", "user12345", "user@example.com", ROLE_USER),
    ("anna", "anna12345", "anna@example.com", ROLE_USER),
]


def run(db: Session):
    if not settings.seed_demo_data:
        logger.info("demo: SEED_DEMO_DATA=false, пропускаю")
        return

    for username, password, email, role in DEMO_USERS:
        exists = db.scalars(
            select(User).where((User.username == username) | (User.email == email))
        ).first()
        if not exists:
            db.add(User(username=username, email=email, role=role, password_hash=hash_password(password)))
            logger.info(f"demo: создан {role} {email} / {password}")
    db.commit()

    if db.scalar(select(func.count()).select_from(RecurringPayment)) > 0:
        logger.info("demo: платежи уже есть, пропускаю")
        return

    on = today()
    creator = db.scalars(
        select(User).where(func.lower(User.username) == settings.superadmin_username.strip().lower())
    ).first()

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
        rp.created_by_id = creator.id if creator else None
        db.add(rp)
    db.commit()
    logger.info("demo: созданы тестовые платежи (RUB, USD, EUR)")