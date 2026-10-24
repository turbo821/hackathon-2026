import os
from datetime import date

import pytest

os.environ["JWT_SECRET_KEY"] = "test-secret-key-that-is-long-enough-123"
os.environ["SUPERADMIN_USERNAME"] = "root"
os.environ["SUPERADMIN_PASSWORD"] = "root-pass"
os.environ["SUPERADMIN_EMAIL"] = "root@example.com"
# Telegram должен быть «настроен», иначе send_message не вызывается вовсе
os.environ["TELEGRAM_BOT_TOKEN"] = "test-token"
os.environ["TELEGRAM_CHAT_ID"] = "-100123"

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

from app import models  # noqa: E402,F401
from app import timeutils  # noqa: E402
from app.db import Base, get_db, make_engine  # noqa: E402
from app.main import app  # noqa: E402

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
        from scripts import seed_superadmin

        seed_superadmin.run(db)
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
def superadmin(client):
    return login(client, "root@example.com", "root-pass")


@pytest.fixture
def admin(client, superadmin):
    """Обычный администратор — его создаёт суперадмин."""
    r = client.post(
        "/api/v1/users",
        json={"username": "boss", "password": "boss12345", "email": "boss@example.com", "role": "admin"},
        headers=superadmin,
    )
    assert r.status_code == 201, r.json()
    return login(client, "boss@example.com", "boss12345")


@pytest.fixture
def user(client, admin):
    r = client.post(
        "/api/v1/users",
        json={"username": "ivan", "password": "ivan12345", "email": "ivan@example.com"},
        headers=admin,
    )
    assert r.status_code == 201, r.json()
    return login(client, "ivan@example.com", "ivan12345")