from datetime import date

from app.timeutils import add_months


def test_31st_falls_back_to_last_day_and_does_not_drift():
    start = date(2026, 1, 31)
    dates = [add_months(start, k, 31) for k in range(5)]
    assert dates == [
        date(2026, 1, 31),
        date(2026, 2, 28),
        date(2026, 3, 31),  # не «уползло» на 28-е
        date(2026, 4, 30),
        date(2026, 5, 31),
    ]


def test_leap_year_february():
    assert add_months(date(2028, 1, 30), 1, 30) == date(2028, 2, 29)


def test_year_boundary():
    assert add_months(date(2026, 12, 15), 1) == date(2027, 1, 15)
    assert add_months(date(2026, 1, 15), -1) == date(2025, 12, 15)


def test_quarterly_and_yearly_steps():
    assert add_months(date(2026, 11, 30), 3, 30) == date(2027, 2, 28)
    assert add_months(date(2028, 2, 29), 12, 29) == date(2029, 2, 28)
