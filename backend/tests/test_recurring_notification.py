"""Тесты оповещения о новом регулярном платеже.

Проверяем:

* оповещение уходит в общий чат при создании платежа;
* текст содержит название, сумму, периодичность и ближайший срок;
* отдельный TELEGRAM_NOTIFY_CHAT_ID имеет приоритет над общим чатом;
* без настроенного Telegram оповещение не шлётся и не ломает создание;
* ошибка Telegram не ломает создание платежа (201 всё равно возвращается).
"""

import logging

import pytest
from app.config import settings
from app.services import recurring_notifications as notif


@pytest.fixture
def fake_telegram(monkeypatch):
    """Подменяет отправку в Telegram: собирает тексты вместо реальной сети."""
    sent: list[tuple[str, str]] = []

    def fake_send_message(text, chat_id=None, reply_markup=None):
        sent.append((chat_id, text))
        return {"message_id": len(sent)}

    monkeypatch.setattr(notif.telegram_client, "send_message", fake_send_message)
    return sent


@pytest.fixture
def configured_telegram(monkeypatch):
    """Telegram настроен: есть токен и общий чат."""
    monkeypatch.setattr(settings, "telegram_bot_token", "test-token", raising=False)
    monkeypatch.setattr(settings, "telegram_chat_id", "-100123", raising=False)
    monkeypatch.setattr(settings, "telegram_notify_chat_id", "", raising=False)


def _payment(**kwargs):
    """Регулярный платёж без обращения к базе — нужен только текст."""
    from datetime import date
    from decimal import Decimal

    class FakePayment:
        pass

    rp = FakePayment()
    rp.id = 42
    rp.name = kwargs.get("name", "VPS-сервер")
    rp.amount = Decimal(kwargs.get("amount", "49.90"))
    rp.currency = kwargs.get("currency", "USD")
    rp.period = kwargs.get("period", "monthly")
    rp.first_due_date = kwargs.get("first_due_date", date(2026, 10, 30))
    return rp


def test_message_contains_essentials():
    from datetime import date

    text = notif.build_message(_payment(), date(2026, 10, 25))

    assert "Новый регулярный платёж" in text
    assert "VPS-сервер" in text
    assert "49.90" in text
    assert "USD" in text
    assert "ежемесячно" in text
    assert "30.10.2026" in text
    assert "через 5 дней" in text


def test_message_shows_who_added():
    from datetime import date

    text = notif.build_message(_payment(), date(2026, 10, 25), created_by="cheremsha")
    assert "Добавил: cheremsha" in text


def test_period_labels_are_human():
    from datetime import date

    text = notif.build_message(_payment(period="yearly"), date(2026, 10, 25))
    assert "ежегодно" in text


def test_notify_goes_to_general_chat(configured_telegram, fake_telegram):
    from datetime import date

    ok = notif.notify_recurring_created(_payment(), on=date(2026, 10, 25))

    assert ok is True
    assert len(fake_telegram) == 1
    chat_id, text = fake_telegram[0]
    assert chat_id == "-100123"
    assert "Новый регулярный платёж" in text


def test_separate_notify_chat_wins(configured_telegram, fake_telegram, monkeypatch):
    from datetime import date

    monkeypatch.setattr(settings, "telegram_notify_chat_id", "-100999", raising=False)

    notif.notify_recurring_created(_payment(), on=date(2026, 10, 25))

    assert fake_telegram[0][0] == "-100999"


def test_not_configured_sends_nothing(monkeypatch, fake_telegram):
    from datetime import date

    monkeypatch.setattr(settings, "telegram_bot_token", "", raising=False)
    monkeypatch.setattr(settings, "telegram_chat_id", "", raising=False)
    monkeypatch.setattr(settings, "telegram_notify_chat_id", "", raising=False)

    ok = notif.notify_recurring_created(_payment(), on=date(2026, 10, 25))

    assert ok is False
    assert fake_telegram == []


def test_telegram_error_is_swallowed(configured_telegram, monkeypatch):
    """Ошибка Telegram не должна подниматься наружу — вызывающий её ловит."""
    from datetime import date

    def boom(*args, **kwargs):
        raise RuntimeError("Telegram недоступен")

    monkeypatch.setattr(notif.telegram_client, "send_message", boom)

    ok = notif.notify_recurring_created(_payment(), on=date(2026, 10, 25))
    assert ok is False


def test_creating_payment_sends_notification(
    client, admin, monkeypatch, fake_telegram, configured_telegram
):
    """Создание платежа на сайте вызывает оповещение."""
    from app.routers import recurring_payments

    called: list[str] = []

    def fake_notify(rp, created_by=None, on=None):
        called.append(created_by or "")
        return True

    monkeypatch.setattr(recurring_payments, "notify_recurring_created", fake_notify)

    r = client.post(
        "/api/v1/recurring-payments",
        headers=admin,
        json={
            "name": "Аренда офиса",
            "amount": "85000.00",
            "currency": "RUB",
            "period": "monthly",
            "first_due_date": "2026-12-01",
        },
    )

    assert r.status_code == 201
    assert called, "оповещение о новом платеже не отправлено"
    assert called[0], "в оповещении не указан добавивший"


def test_creating_payment_survives_telegram_failure(
    client, admin, monkeypatch, configured_telegram
):
    """Падение Telegram не ломает создание платежа."""
    from app.routers import recurring_payments

    def boom(*args, **kwargs):
        raise RuntimeError("Telegram недоступен")

    monkeypatch.setattr(recurring_payments, "notify_recurring_created", boom)

    r = client.post(
        "/api/v1/recurring-payments",
        headers=admin,
        json={
            "name": "Подписка Figma",
            "amount": "15.00",
            "currency": "EUR",
            "period": "monthly",
            "first_due_date": "2026-12-15",
        },
    )

    assert r.status_code == 201
