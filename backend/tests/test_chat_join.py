"""Вступление в чат: бот подхватывает Telegram ID вошедшего.

Пользователь приходит с сайта по персональной ссылке-приглашению, вступает
в чат — и бот записывает его Telegram ID в карточку того, кто был на сайте.
"""

from datetime import timedelta

import pytest
from app.models import TelegramLink, User
from app.services.bot import handle_chat_member
from app.timeutils import utcnow


def make_link(db, user: User, token: str = "tok123", minutes_left: int = 15):
    link = TelegramLink(
        token=token,
        user_id=user.id,
        expires_at=utcnow() + timedelta(minutes=minutes_left),
    )
    db.add(link)
    db.commit()
    return link


def join_update(
    token: str = "tok123", telegram_id: int = 555001, status: str = "member"
):
    """Событие chat_member: пользователь вступил в чат по ссылке с именем token."""
    return {
        "update_id": 1,
        "chat_member": {
            "chat": {
                "id": -1001234567890,
                "type": "supergroup",
                "title": "Напоминания",
            },
            "from": {"id": 777, "is_bot": False, "first_name": "Кто-то"},
            "date": 1710000000,
            "old_chat_member": {"status": "left", "user": {"id": telegram_id}},
            "new_chat_member": {
                "status": status,
                "user": {"id": telegram_id, "is_bot": False, "first_name": "Иван"},
            },
            "invite_link": {
                "invite_link": "https://t.me/+abcdef",
                "name": token,
                "creator": {"id": 1, "is_bot": True},
                "creates_join_request": False,
                "is_primary": False,
                "is_revoked": False,
            },
        },
    }


@pytest.fixture
def user(db):
    user = User(username="ivan", email="ivan@mail.ru", password_hash="x")
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


# ---------- Вступление ----------


def test_join_binds_telegram_id_to_site_user(db, user):
    make_link(db, user)

    handle_chat_member(db, join_update())

    db.refresh(user)
    assert user.telegram_id == 555001


def test_join_marks_link_as_used(db, user):
    link = make_link(db, user)

    handle_chat_member(db, join_update())

    db.refresh(link)
    assert link.used_at is not None


def test_second_join_with_same_link_is_ignored(db, user):
    """Код одноразовый: второй вступивший по той же ссылке не привязывается."""
    make_link(db, user)

    handle_chat_member(db, join_update(telegram_id=555001))
    handle_chat_member(db, join_update(telegram_id=555002))

    db.refresh(user)
    assert user.telegram_id == 555001


def test_expired_link_does_not_bind(db, user):
    make_link(db, user, minutes_left=-1)

    handle_chat_member(db, join_update())

    db.refresh(user)
    assert user.telegram_id is None


def test_join_without_invite_link_is_ignored(db, user):
    """Вступил не по нашей ссылке — код неизвестен, ничего не делаем."""
    make_link(db, user)

    update = join_update()
    del update["chat_member"]["invite_link"]

    handle_chat_member(db, update)

    db.refresh(user)
    assert user.telegram_id is None


def test_status_change_is_not_a_join(db, user):
    """Смена роли (member → administrator) — не вступление."""
    make_link(db, user)

    update = join_update(status="administrator")
    update["chat_member"]["old_chat_member"]["status"] = "member"

    handle_chat_member(db, update)

    db.refresh(user)
    assert user.telegram_id is None


def test_leaving_chat_does_not_bind(db, user):
    """Пользователь вышел из чата — тоже не вступление."""
    make_link(db, user)

    update = join_update(status="left")
    update["chat_member"]["old_chat_member"]["status"] = "member"

    handle_chat_member(db, update)

    db.refresh(user)
    assert user.telegram_id is None


def test_telegram_id_is_reassigned_from_another_user(db, user):
    """Если этот Telegram был привязан к другому — ID переезжает к новому."""
    other = User(
        username="anna", email="anna@mail.ru", password_hash="x", telegram_id=555001
    )
    db.add(other)
    db.commit()
    make_link(db, user)

    handle_chat_member(db, join_update(telegram_id=555001))

    db.refresh(user)
    db.refresh(other)
    assert user.telegram_id == 555001
    assert other.telegram_id is None


# ---------- Эндпоинт панели ----------


def test_chat_link_endpoint_returns_invite_link(client, admin, monkeypatch):
    """Панель получает персональную ссылку-приглашение с кодом в имени."""
    from app.config import settings
    from app.routers import auth

    monkeypatch.setattr(
        settings, "telegram_group_chat_id", "-1001234567890", raising=False
    )
    captured = {}

    def fake_create(chat_id, name):
        captured["chat_id"] = chat_id
        captured["name"] = name
        return "https://t.me/+abcdef"

    monkeypatch.setattr(auth.telegram, "create_chat_invite_link", fake_create)

    r = client.post("/api/v1/auth/telegram-chat-link", headers=admin)
    assert r.status_code == 200, r.json()
    body = r.json()

    assert body["url"] == "https://t.me/+abcdef"
    # Код из ссылки кладём в имя приглашения — по нему бот и узнает вошедшего
    assert captured["name"] == body["token"]
    assert captured["chat_id"] == "-1001234567890"


def test_chat_link_endpoint_requires_configured_chat(client, admin, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "telegram_group_chat_id", "", raising=False)

    r = client.post("/api/v1/auth/telegram-chat-link", headers=admin)
    assert r.status_code == 503
