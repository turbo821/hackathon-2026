"""Рассылка напоминаний по почте: получатели из базы и отправка каждому."""

import pytest
from app.models import User
from app.services import telegram
from app.services.recipients import email_recipients
from app.services.remind_channels import smtp
from app.timeutils import utcnow


@pytest.fixture
def sent(monkeypatch):
    """Перехватывает отправку в Telegram — реальных сообщений тесты не шлют."""
    messages = []
    monkeypatch.setattr(
        telegram,
        "send_message",
        lambda text, chat_id=None, reply_markup=None: (
            messages.append(text) or {"ok": True}
        ),
    )
    return messages


def make_user(db, username: str, email: str | None) -> User:
    user = User(username=username, email=email, password_hash="x")
    db.add(user)
    db.commit()
    return user


# ---------- Получатели ----------


def test_email_recipients_collects_all_addresses(db):
    make_user(db, "ivan", "ivan@mail.ru")
    make_user(db, "anna", "anna@mail.ru")

    assert email_recipients(db) == ["anna@mail.ru", "ivan@mail.ru"]


def test_email_recipients_skips_empty_and_duplicates(db):
    make_user(db, "ivan", "ivan@mail.ru")
    make_user(db, "anna", "ANNA@mail.ru")
    make_user(db, "empty", "")

    # адрес приводится к нижнему регистру и повторы убираются
    assert email_recipients(db) == ["anna@mail.ru", "ivan@mail.ru"]


def test_email_recipients_skips_demo_domain(db):
    """Демо-пользователи сидят на example.com — письма туда уходят в никуда."""
    make_user(db, "demo", "user@example.com")

    assert email_recipients(db) == []


def test_email_recipients_empty_without_users(db):
    db.query(User).delete()
    db.commit()

    assert email_recipients(db) == []


# ---------- Отправка ----------


def test_send_message_goes_to_every_recipient(monkeypatch):
    sent = []
    monkeypatch.setattr(
        smtp, "_send_message_to", lambda to, text: sent.append((to, text))
    )

    delivered = smtp.send_message("напоминание", recipients=["a@mail.ru", "b@mail.ru"])

    assert delivered == 2
    assert sent == [
        ("a@mail.ru", "напоминание"),
        ("b@mail.ru", "напоминание"),
    ]


def test_send_message_without_recipients_sends_nothing(monkeypatch):
    sent = []
    monkeypatch.setattr(smtp, "_send_message_to", lambda to, text: sent.append(to))

    delivered = smtp.send_message("напоминание", recipients=[])

    # никому не отправили — это не доставка, вызывающий должен узнать об этом
    assert delivered == 0
    assert sent == []


def test_send_message_reports_zero_when_every_send_fails(monkeypatch):
    def broken(to, text):
        raise RuntimeError("сеть недоступна")

    monkeypatch.setattr(smtp, "_send_message_to", broken)

    # ноль доставленных — вызывающий не посчитает период отправленным
    assert smtp.send_message("напоминание", recipients=["a@mail.ru"]) == 0


def test_partial_failure_reports_delivered_count(monkeypatch):
    def flaky(to, text):
        if to.startswith("bad"):
            raise RuntimeError("отказ сервера")

    monkeypatch.setattr(smtp, "_send_message_to", flaky)

    # те, кому письмо дошло, повторно его не получат
    delivered = smtp.send_message(
        "напоминание", recipients=["good@mail.ru", "bad@mail.ru"]
    )
    assert delivered == 1


def test_empty_channel_does_not_mask_failed_telegram(client, admin, db, monkeypatch):
    """Пустой SMTP-канал не должен засчитываться за доставку.

    Раньше «никому не отправили» считалось успехом — и упавший Telegram
    маскировался: период помечался отправленным, повторной попытки не было.
    """
    calls = []

    def flaky(text, chat_id=None, reply_markup=None):
        calls.append(text)
        raise RuntimeError("network down")

    monkeypatch.setattr(telegram, "send_message", flaky)
    # SMTP готов, но отправлять некому: в базе только @example.com
    monkeypatch.setattr(smtp, "ready_to_send", lambda: True)
    monkeypatch.setattr(smtp, "_send_message_to", lambda to, text: None)

    client.post(
        "/api/v1/recurring-payments",
        json={
            "name": "Аренда",
            "amount": "50000",
            "currency": "RUB",
            "first_due_date": utcnow().date().isoformat(),
        },
        headers=admin,
    )

    from app.services.reminders import check_and_send

    check_and_send(db)  # первая попытка — Telegram упал
    check_and_send(db)  # вторая — период не был помечен, пробуем снова

    # создание платежа + две проверки = три попытки. Если бы период пометили
    # отправленным после первого падения, Telegram позвали бы один раз.
    assert len(calls) == 3


# ---------- Связка с напоминаниями ----------


def test_reminder_is_mailed_to_all_users(client, admin, db, sent, monkeypatch):
    """Напоминание уходит письмом каждому пользователю с email."""
    make_user(db, "bob", "bob@mail.ru")
    make_user(db, "vera", "vera@mail.ru")
    monkeypatch.setattr(smtp, "ready_to_send", lambda: True)

    mails = []
    monkeypatch.setattr(
        smtp, "_send_message_to", lambda to, text: mails.append((to, text))
    )

    client.post(
        "/api/v1/recurring-payments",
        json={
            "name": "Аренда",
            "amount": "50000",
            "currency": "RUB",
            "first_due_date": utcnow().date().isoformat(),
        },
        headers=admin,
    )

    addresses = sorted(to for to, _ in mails)
    assert addresses == ["bob@mail.ru", "vera@mail.ru"]
    # в письме есть суть напоминания
    assert all("Аренда" in text for _, text in mails)
