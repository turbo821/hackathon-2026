"""Проверка схемы БД.

create_all умеет только создавать таблицы — существующие он не меняет.
Эти тесты проверяют, что расхождение схемы с моделями находится
до старта приложения (scripts/check_schema.py), а не всплывает позже
на первой записи.
"""

from app import models  # noqa: F401 — регистрирует модели в Base.metadata
from app.db import Base, make_engine, schema_drift


def test_fresh_db_has_no_drift(tmp_path):
    engine = make_engine(f"sqlite:///{tmp_path / 'new.db'}")
    Base.metadata.create_all(engine)

    missing, extra = schema_drift(engine)

    assert missing == []
    assert extra == []


def test_drift_detects_missing_column(tmp_path):
    engine = make_engine(f"sqlite:///{tmp_path / 'old.db'}")
    Base.metadata.create_all(engine)
    with engine.begin() as conn:
        conn.exec_driver_sql("ALTER TABLE users DROP COLUMN updated_at")

    missing, extra = schema_drift(engine)

    assert "users.updated_at" in missing


def test_drift_detects_missing_table(tmp_path):
    engine = make_engine(f"sqlite:///{tmp_path / 'part.db'}")
    Base.metadata.create_all(engine)
    with engine.begin() as conn:
        conn.exec_driver_sql("DROP TABLE revoked_tokens")

    missing, extra = schema_drift(engine)

    assert "таблица revoked_tokens" in missing


def test_extra_column_is_reported_but_not_fatal(tmp_path):
    """Лишняя колонка на работу не влияет — но о ней тоже полезно знать."""
    engine = make_engine(f"sqlite:///{tmp_path / 'extra.db'}")
    Base.metadata.create_all(engine)
    with engine.begin() as conn:
        conn.exec_driver_sql("ALTER TABLE users ADD COLUMN legacy TEXT")

    missing, extra = schema_drift(engine)

    assert missing == []
    assert "users.legacy" in extra
