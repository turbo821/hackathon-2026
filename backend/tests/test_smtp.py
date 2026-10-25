"""Рассылка напоминаний по почте: получатели из базы и отправка каждому."""

import email

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


class FakeServer:
    """Подделка SMTP-соединения: пишет вызовы sendmail в self.calls."""

    def __init__(self, refused: dict | None = None, error: Exception | None = None):
        self.calls: list[tuple[list[str], bytes]] = []
        self.refused = refused
        self.error = error

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def sendmail(self, from_addr, to_addrs, msg):
        self.calls.append((list(to_addrs), msg))
        if self.error is not None:
            raise self.error
        if self.refused is not None:
            raise smtp.smtplib.SMTPRecipientsRefused(self.refused)
        return {}


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
    """Вся пачка уходит одним письмом по одному соединению."""
    server = FakeServer()
    monkeypatch.setattr(smtp, "_connect", lambda: server)

    delivered = smtp.send_message("напоминание", recipients=["a@mail.ru", "b@mail.ru"])

    assert delivered == 2
    # одно соединение, один вызов sendmail, оба адреса в одной пачке
    assert len(server.calls) == 1
    to_addrs, _ = server.calls[0]
    assert to_addrs == ["a@mail.ru", "b@mail.ru"]


def test_batch_message_hides_other_recipients(monkeypatch):
    """В заголовке To — undisclosed-recipients: чужие адреса не светятся."""
    server = FakeServer()
    monkeypatch.setattr(smtp, "_connect", lambda: server)

    smtp.send_message("напоминание", recipients=["a@mail.ru", "b@mail.ru"])

    msg = server.calls[0][1].decode("utf-8")
    assert "undisclosed-recipients" in msg
    assert "a@mail.ru" not in msg
    assert "b@mail.ru" not in msg


def test_batch_message_is_utf8_encoded(monkeypatch):
    """sendmail кодирует str как ASCII — поэтому отправляем bytes."""
    server = FakeServer()
    monkeypatch.setattr(smtp, "_connect", lambda: server)

    smtp.send_message("Напоминание об оплате", recipients=["a@mail.ru"])

    assert isinstance(server.calls[0][1], bytes)
    assert "Напоминание об оплате" in server.calls[0][1].decode("utf-8")


def test_send_message_without_recipients_sends_nothing(monkeypatch):
    sent = []
    monkeypatch.setattr(smtp, "_connect", lambda: sent.append("connect"))

    delivered = smtp.send_message("напоминание", recipients=[])

    # никому не отправили — это не доставка, вызывающий должен узнать об этом
    assert delivered == 0
    assert sent == []


def test_send_message_reports_zero_when_every_recipient_refused(monkeypatch):
    """Сервер отказал всем — доставлять нечего."""
    server = FakeServer(refused={"a@mail.ru": (550, b"mailbox unavailable")})
    monkeypatch.setattr(smtp, "_connect", lambda: server)

    # ноль доставленных — вызывающий не посчитает период отправленным
    assert smtp.send_message("напоминание", recipients=["a@mail.ru"]) == 0


def test_partial_refusal_reports_delivered_count(monkeypatch):
    """Часть адресов не принята — остальные письмо получили."""
    server = FakeServer(refused={"bad@mail.ru": (550, b"full")})
    monkeypatch.setattr(smtp, "_connect", lambda: server)

    # те, кому письмо дошло, повторно его не получат
    delivered = smtp.send_message(
        "напоминание", recipients=["good@mail.ru", "bad@mail.ru"]
    )
    assert delivered == 1


def test_send_message_returns_zero_on_smtp_error(monkeypatch):
    """Сбой SMTP — ноль доставленных, а не «успех»."""
    server = FakeServer(error=smtp.smtplib.SMTPDataError(451, b"Ratelimit exceeded"))
    monkeypatch.setattr(smtp, "_connect", lambda: server)

    assert smtp.send_message("напоминание", recipients=["a@mail.ru"]) == 0


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
    monkeypatch.setattr(smtp, "_connect", lambda: FakeServer())

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
    # Оповещение о новом платеже — отдельное сообщение, его не считаем.
    reminder_calls = [c for c in calls if "Новый регулярный платёж" not in c]
    assert len(reminder_calls) == 3


# ---------- Связка с напоминаниями ----------


def test_reminder_is_mailed_to_all_users(client, admin, db, sent, monkeypatch):
    """Напоминание уходит письмом каждому пользователю с email."""
    make_user(db, "bob", "bob@mail.ru")
    make_user(db, "vera", "vera@mail.ru")
    monkeypatch.setattr(smtp, "ready_to_send", lambda: True)

    mails = []

    class Recorder(FakeServer):
        def sendmail(self, from_addr, to_addrs, msg):
            mails.append((list(to_addrs), msg))
            return {}

    monkeypatch.setattr(smtp, "_connect", lambda: Recorder())

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

    addresses = sorted(to_addrs for to_addrs, _ in mails)
    assert addresses == [["bob@mail.ru", "vera@mail.ru"]]
    # в письме есть суть напоминания (тело письма в MIME, разбираем по частям)
    for _, msg in mails:
        parsed = email.message_from_bytes(msg)
        body = "".join(
            part.get_payload(decode=True).decode("utf-8", "replace")
            for part in parsed.walk()
            if part.get_payload(decode=True)
        )
        assert "Аренда" in body
