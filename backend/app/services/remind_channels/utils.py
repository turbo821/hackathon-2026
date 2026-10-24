from datetime import date
from decimal import Decimal


def format_amount(amount: Decimal, currency: str) -> str:
    whole = f"{Decimal(amount):,.2f}".replace(",", " ")
    return f"{whole} {currency}"


def days_word(n: int) -> str:
    if n % 10 == 1 and n % 100 != 11:
        return "день"
    if n % 10 in (2, 3, 4) and n % 100 not in (12, 13, 14):
        return "дня"
    return "дней"


def get_time_until(due_date: date, on: date) -> str:
    left = (due_date - on).days
    if left == 0:
        return "сегодня"
    elif left == 1:
        return "завтра"
    else:
        return f"через {left} {days_word(left)}"
