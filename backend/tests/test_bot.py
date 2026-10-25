"""Бот: привязка Telegram-аккаунта и кнопка «Оплачено»."""

from datetime import timedelta

import pytest
from app.models import PaymentOccurrence, RecurringPayment, TelegramLink, User
from app.services import telegram
from app.services.bot import (
    handle_chat_member,
    handle_pay_button,
    handle_start,
    handle_update,
)
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


@pytest.fixture
def tg_user(db):
    """Настоящий пользователь в БД.

    Фикстура user из conftest отдаёт заголовки авторизации, а не объект User.
    """
    user = User(username="ivan", email="ivan@example.com", password_hash="x")
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def make_link(db, user, token="tok123", expired=False):
    link = TelegramLink(
        token=token,
        user_id=user.id,
        expires_at=utcnow() - timedelta(minutes=1)
        if expired
        else utcnow() + timedelta(minutes=15),
    )
    db.add(link)
    db.commit()
    return link


def make_occurrence(db, user, amount="1000.00"):
    rp = RecurringPayment(
        name="Аренда",
        amount=amount,
        currency="RUB",
        period="monthly",
        first_due_date=utcnow().date(),
        anchor_day=utcnow().day,
    )
    db.add(rp)
    db.flush()
    occ = PaymentOccurrence(
        recurring_payment_id=rp.id,
        name=rp.name,
        amount=rp.amount,
        currency=rp.currency,
        due_date=rp.first_due_date,
        status="unpaid",
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


def test_binding_is_logged_explicitly(db, tg_user, caplog):
    """Привязка отмечается в логе: видно, какой Telegram ID какому аккаунту."""
    import logging

    caplog.set_level(logging.INFO)
    make_link(db, tg_user)

    handle_start(db, 555777, "tok123")

    # структурированное событие
    bound = [r for r in caplog.records if getattr(r, "event", None) == "telegram.bound"]
    assert bound, "нет записи telegram.bound в логах"
    record = bound[0]
    assert record.telegram_id == 555777
    assert record.username == tg_user.username
    assert record.user_id == tg_user.id
    assert record.email == tg_user.email
    assert record.source == "start_link"

    # и понятная строка для человека
    messages = " ".join(r.getMessage() for r in caplog.records)
    assert "555777" in messages
    assert tg_user.username in messages
    assert tg_user.email in messages


def test_binding_via_chat_join_logged_with_source(db, tg_user, caplog):
    """Вступление в чат — тоже привязка, но со своим source."""
    import logging

    caplog.set_level(logging.INFO)
    make_link(db, tg_user, token="join-tok")

    handle_chat_member(
        db,
        {
            "chat_member": {
                "new_chat_member": {"status": "member", "user": {"id": 888222}},
                "old_chat_member": {"status": "left"},
                "invite_link": {"name": "join-tok"},
            }
        },
    )

    bound = [r for r in caplog.records if getattr(r, "event", None) == "telegram.bound"]
    assert bound, "нет записи telegram.bound в логах"
    assert bound[0].source == "chat_join"
    assert bound[0].telegram_id == 888222


def test_join_without_invite_link_is_logged(db, caplog):
    """Вступление без ссылки-приглашения — видно в логах."""
    import logging

    caplog.set_level(logging.INFO)

    handle_chat_member(
        db,
        {
            "chat_member": {
                "new_chat_member": {"status": "member", "user": {"id": 555123}},
                "old_chat_member": {"status": "left"},
            }
        },
    )

    messages = " ".join(r.getMessage() for r in caplog.records)
    assert "без ссылки-приглашения" in messages


def test_join_with_unknown_code_is_logged(db, caplog):
    """Вступление с чужим/использованным кодом — видно в логах."""
    import logging

    caplog.set_level(logging.INFO)

    handle_chat_member(
        db,
        {
            "chat_member": {
                "new_chat_member": {"status": "member", "user": {"id": 555124}},
                "old_chat_member": {"status": "left"},
                "invite_link": {"name": "чу��ой-код"},
            }
        },
    )

    unresolved = [
        r
        for r in caplog.records
        if getattr(r, "event", None) == "telegram.join_unresolved"
    ]
    assert unresolved, "нет записи telegram.join_unresolved в логах"
    assert unresolved[0].reason == "неизвестный код"


def test_join_event_is_logged(db, tg_user, caplog):
    """Само событие вступления попадает в лог — видно, что бот его получает."""
    import logging

    caplog.set_level(logging.INFO)
    make_link(db, tg_user, token="join-visible")

    handle_update(
        db,
        {
            "chat_member": {
                "new_chat_member": {
                    "status": "member",
                    "user": {"id": 555125, "username": "petr"},
                },
                "old_chat_member": {"status": "left"},
                "invite_link": {"name": "join-visible"},
            }
        },
    )

    messages = " ".join(r.getMessage() for r in caplog.records)
    assert "событие вступления в чат" in messages
    assert "555125" in messages


def test_rebinding_logs_unbind_of_previous_owner(db, tg_user, caplog):
    """Если Telegram был привязан к другому аккаунту — это тоже попадает в лог."""
    import logging

    caplog.set_level(logging.INFO)

    # Telegram ID принадлежит другому пользователю
    other = User(username="petr", email="petr@example.com", password_hash="x")
    db.add(other)
    db.commit()
    other.telegram_id = 555999
    db.commit()

    # А привязка приходит к нашему пользователю
    make_link(db, tg_user, token="tok-rebind")
    handle_start(db, 555999, "tok-rebind")

    unbound = [
        r for r in caplog.records if getattr(r, "event", None) == "telegram.unbound"
    ]
    assert unbound, "нет записи telegram.unbound в логах"
    assert unbound[0].previous_username == "petr"
    assert unbound[0].telegram_id == 555999

    # прежний владелец освобождён, новый — привязан
    db.refresh(other)
    db.refresh(tg_user)
    assert other.telegram_id is None
    assert tg_user.telegram_id == 555999


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


def test_regular_message_is_ignored(db, sent):
    """Бот не отвечает на обычные сообщения — только на события и команды.

    Раньше бот отвечал «вы в системе как …» на каждое сообщение и подсказывал
    Telegram ID. В общем чате это засвечивало чужие ID и засоряло переписку.
    """
    handle_update(
        db, {"message": {"chat": {"id": 1}, "from": {"id": 777001}, "text": "привет"}}
    )
    assert sent == []


def test_regular_message_from_bound_user_is_ignored(db, tg_user, sent):
    """Привязанный пользователь тоже не получает ответа на обычное сообщение."""
    tg_user.telegram_id = 777002
    db.commit()

    handle_update(
        db, {"message": {"chat": {"id": 1}, "from": {"id": 777002}, "text": "привет"}}
    )
    assert sent == []


def test_start_without_token_gives_instructions(db, sent):
    """/start без кода — подсказка, как привязаться (без Telegram ID)."""
    handle_update(
        db, {"message": {"chat": {"id": 1}, "from": {"id": 777003}, "text": "/start"}}
    )

    assert sent, "на /start бот должен ответить"
    text = sent[0]
    assert "Invoice Keeper" in text
    # ID пользователя больше не светится — привязка только через код
    assert "777003" not in text


def test_start_with_token_still_binds(db, tg_user, sent):
    """Команда /start с кодом по-прежнему привязывает аккаунт."""
    make_link(db, tg_user)

    handle_update(
        db,
        {
            "message": {
                "chat": {"id": 1},
                "from": {"id": 555005},
                "text": "/start tok123",
            }
        },
    )

    db.refresh(tg_user)
    assert tg_user.telegram_id == 555005
    assert sent and "привязаны" in sent[0]
