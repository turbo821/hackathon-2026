import os
from datetime import date

import pytest

os.environ["JWT_SECRET_KEY"] = "test-secret-key-that-is-long-enough-123"
os.environ["ADMIN_USERNAME"] = "admin"
os.environ["ADMIN_PASSWORD"] = "admin-pass"
os.environ["ADMIN_EMAIL"] = "admin@example.com"
# Telegram должен быть «настроен», иначе send_message не вызывается вовсе
os.environ["TELEGRAM_BOT_TOKEN"] = "test-token"
os.environ["TELEGRAM_CHAT_ID"] = "-100123"
# Почту в тестах выключаем: без этого настройки из .env разработчика сделали бы
# канал активным, и тесты слали бы настоящие письма.
os.environ["SMTP_PASSWORD"] = ""

from app import (
    models,  # noqa: E402,F401
    timeutils,  # noqa: E402
)
from app.db import Base, get_db, make_engine  # noqa: E402
from app.main import app  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

TODAY = date(2026, 10, 23)


@pytest.fixture
def session_factory(tmp_path):
    engine = make_engine(f"sqlite:///{tmp_path / 'test.db'}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    def override_get_db():
        db = factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with factory() as db:
        from scripts import seed_admin

        seed_admin.run(db)
    yield factory
    app.dependency_overrides.clear()
    engine.dispose()


@pytest.fixture
def db(session_factory):
    with session_factory() as session:
        yield session


@pytest.fixture(autouse=True)
def frozen_today():
    timeutils.FROZEN_TODAY = TODAY
    yield
    timeutils.FROZEN_TODAY = None


@pytest.fixture
def client(session_factory):
    return TestClient(app)


def login(client, email, password):
    r = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.json()
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture
def admin(client):
    return login(client, "admin@example.com", "admin-pass")


@pytest.fixture
def user(client, admin):
    r = client.post(
        "/api/v1/users",
        json={"username": "ivan", "password": "ivan12345", "email": "ivan@example.com"},
        headers=admin,
    )
    assert r.status_code == 201, r.json()
    return login(client, "ivan@example.com", "ivan12345")
