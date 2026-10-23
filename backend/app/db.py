"""Подключение к БД: engine, фабрика сессий, Base для моделей, зависимость get_db."""

from collections.abc import Iterator
from pathlib import Path

from sqlalchemy import MetaData, create_engine, event
from sqlalchemy.engine import make_url
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings

# Явные имена constraint'ов — без них Alembic в batch-режиме SQLite
# не сможет удалять/менять ограничения в следующих миграциях.
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


def make_engine(url: str):
    parsed = make_url(url)
    connect_args = {}
    if parsed.get_backend_name() == "sqlite":
        # FastAPI выполняет sync-эндпоинты в пуле потоков
        connect_args["check_same_thread"] = False
        if parsed.database and parsed.database != ":memory:":
            Path(parsed.database).parent.mkdir(parents=True, exist_ok=True)

    engine = create_engine(url, connect_args=connect_args)

    if parsed.get_backend_name() == "sqlite":

        @event.listens_for(engine, "connect")
        def _sqlite_pragmas(dbapi_connection, connection_record):
            """Внешние ключи + WAL: бэкенд и worker пишут в один файл."""
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA busy_timeout=5000")
            cursor.close()

    return engine


engine = make_engine(settings.database_url)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Iterator[Session]:
    """Зависимость FastAPI: одна сессия на запрос."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
