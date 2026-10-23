"""Работа с датами в едином часовом поясе приложения."""

import calendar
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

from app.config import settings


def app_tz() -> ZoneInfo:
    return ZoneInfo(settings.app_timezone)


# Для тестов: можно «заморозить» сегодняшнюю дату (timeutils.FROZEN_TODAY = date(...))
FROZEN_TODAY: date | None = None


def today() -> date:
    """«Сегодня» в часовом поясе приложения (не сервера!)."""
    if FROZEN_TODAY is not None:
        return FROZEN_TODAY
    return datetime.now(app_tz()).date()


def utcnow() -> datetime:
    """Текущий момент в UTC без tzinfo — так храним метки времени в БД."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def due_date_for(anchor_day: int, year: int, month: int) -> date:
    """Дата оплаты в месяце: если такого числа нет — последний день месяца."""
    last_day = calendar.monthrange(year, month)[1]
    return date(year, month, min(anchor_day, last_day))


def add_months(start: date, months: int, anchor_day: int | None = None) -> date:
    """Сдвиг на N месяцев, всегда от исходного числа (anchor_day).

    Важно: считаем от anchor_day, а не от предыдущей даты, иначе
    31.01 → 28.02 → 28.03 («уползание»). Здесь 31.01 → 28.02 → 31.03.
    """
    anchor = anchor_day or start.day
    total = start.year * 12 + (start.month - 1) + months
    year, month = divmod(total, 12)
    return due_date_for(anchor, year, month + 1)
