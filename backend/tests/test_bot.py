"""Бот: привязка Telegram-аккаунта и кнопка «Оплачено»."""

from datetime import timedelta

import pytest

from app.models import PaymentOccurrence, RecurringPayment, TelegramLink, User
from app.services import telegram
from app.services.bot import handle_pay_button, handle_start, handle_update
from app.timeutils import utcnow


@pytest.fixture
def sent(monkeypatch):
    """Перехватывает отправку в Telegram — реальных сообщений тесты не шлют."""
    messages = []
    monkeypatch.setattr(
        telegram,
        "send_message",
        lambda text, chat_id=None, reply_markup=None: messages.append(text) or {"ok": True},
    )
    return messages


@pytest.fixture
def tg_user(db):
    """Настоящий пользователь в БД.

    Фикстура user из conftest отдаёт заголовки авторизации, а не объект User.
    """
    user = User(username="ivan", password_hash="x")
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def make_link(db, user, token="tok123", expired=False):
    link = TelegramLink(
        token=token,
        user_id=user.id,
        expires_at=utcnow() - timedelta(minutes=1) if expired else utcnow() + timedelta(minutes=15),
    )
    db.add(link)
    db.commit()
    return link


def make_occurrence(db, user, amount="1000.00"):
    rp = RecurringPayment(
        name="Аренда", amount=amount, currency="RUB", period="monthly",
        first_due_date=utcnow().date(), anchor_day=utcnow().day,
    )
    db.add(rp)
    db.flush()
    occ = PaymentOccurrence(
        recurring_payment_id=rp.id, name=rp.name, amount=rp.amount, currency=rp.currency,
        due_date=rp.first_due_date, status="unpaid",
    )
    db.add(occ)
    db.commit()
    return occ


def test_start_binds_telegram_to_user(db, tg_user):
    make_link(db, tg_user)
    answer = handle_start(db, 555001, "tok123")

    db.refresh(tg_user)
    assert tg_user.telegram_id == 555001
    assert "привязаны" in answer


def test_expired_link_does_not_bind(db, tg_user):
    make_link(db, tg_user, token="old", expired=True)
    answer = handle_start(db, 555002, "old")

    db.refresh(tg_user)
    assert tg_user.telegram_id is None
    assert "недействительна" in answer


def test_pay_button_closes_period_for_bound_user(db, tg_user):
    tg_user.telegram_id = 555003
    db.commit()
    occ = make_occurrence(db, tg_user)

    answer = handle_pay_button(db, 555003, occ.id)

    db.refresh(occ)
    assert occ.status == "paid"
    assert occ.marked_by_id == tg_user.id
    assert occ.paid_source == "telegram"
    assert occ.paid_at is not None
    assert "Записал" in answer


def test_pay_button_rejects_unbound_user(db, tg_user):
    occ = make_occurrence(db, tg_user)
    answer = handle_pay_button(db, 999999, occ.id)

    db.refresh(occ)
    assert occ.status == "unpaid"
    assert "не привязаны" in answer


def test_pay_button_on_already_paid_period(db, tg_user):
    tg_user.telegram_id = 555004
    db.commit()
    occ = make_occurrence(db, tg_user)
    occ.status = "paid"
    db.commit()

    answer = handle_pay_button(db, 555004, occ.id)

    assert "Уже оплачено" in answer


def test_message_without_start_reports_telegram_id(db, sent):
    handle_update(db, {"message": {"chat": {"id": 1}, "from": {"id": 777001}, "text": "привет"}})
    assert sent and "777001" in sent[0]