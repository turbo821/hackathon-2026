import os
from datetime import date

import pytest

os.environ.setdefault("LOG_DIR", "null")
os.environ["JWT_SECRET_KEY"] = "test-secret-key-that-is-long-enough-123"
os.environ["ADMIN_USERNAME"] = "admin"
os.environ["ADMIN_PASSWORD"] = "admin-pass"
os.environ["TELEGRAM_BOT_TOKEN"] = "test-token"
os.environ["TELEGRAM_CHAT_ID"] = "-100123"

from app import create_app, timeutils  # noqa: E402
from app.extensions import db  # noqa: E402
from app.services import telegram  # noqa: E402

TODAY = date(2026, 10, 23)


@pytest.fixture
def app(tmp_path):
    app = create_app(
        config_overrides={
            "SQLALCHEMY_DATABASE_URI": f"sqlite:///{tmp_path / 'test.db'}",
            "TESTING": True,
        }
    )
    with app.app_context():
        db.create_all()
        from scripts import seed_admin

        seed_admin.run()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture(autouse=True)
def frozen_today():
    timeutils.FROZEN_TODAY = TODAY
    yield
    timeutils.FROZEN_TODAY = None


@pytest.fixture
def sent(monkeypatch):
    """Перехватывает отправку в Telegram и копит тексты сообщений."""
    messages = []
    monkeypatch.setattr(telegram, "send_message", lambda text, chat_id=None: messages.append(text) or {"ok": True})
    return messages


@pytest.fixture
def client(app, sent):
    return app.test_client()


def login(client, username, password):
    r = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert r.status_code == 200, r.json
    return {"Authorization": f"Bearer {r.json['access_token']}"}


@pytest.fixture
def admin(client):
    return login(client, "admin", "admin-pass")


@pytest.fixture
def user(client, admin):
    r = client.post("/api/v1/users", json={"username": "ivan", "password": "ivan12345"}, headers=admin)
    assert r.status_code == 201, r.json
    return login(client, "ivan", "ivan12345")
