"""Кому отправляем напоминания по почте.

Отдельный модуль, чтобы правило «кто получатель» жило в одном месте:
каналы (Telegram/SMTP) только отправляют, а список адресов собирается здесь.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import User

# example.com — зарезервированный домен, на нём сидят демо-пользователи.
# Письма туда уходят в никуда, поэтому в рассылку они не попадают.
DEMO_DOMAIN = "example.com"


def email_recipients(db: Session) -> list[str]:
    """Все адреса из базы — по ним и рассылаем письма.

    Пустые адреса пропускаем (у пользователя email обязателен, но старые
    записи могли остаться без него), повторы убираем: письмо отправляется
    один раз на адрес, а не на каждую запись с таким адресом.
    """
    emails = db.scalars(
        select(User.email).where(User.email.is_not(None), User.email != "")
    ).all()

    unique: list[str] = []
    for email in emails:
        address = email.strip().lower()
        if not address or address.endswith("@" + DEMO_DOMAIN):
            continue
        if address not in unique:
            unique.append(address)
    return sorted(unique)
