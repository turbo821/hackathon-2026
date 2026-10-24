"""Подключение к БД: engine, фабрика сессий, Base для моделей, зависимость get_db."""

from collections.abc import Iterator
from pathlib import Path

from sqlalchemy import MetaData, create_engine, event, inspect
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


def schema_drift(target_engine=None) -> tuple[list[str], list[str]]:
    """Сравнивает схему базы с моделями.

    Возвращает (недостающее, лишнее):
    - **недостающее** — в базе нет таблицы или колонки, которая есть в моделях.
      Приложение упадёт на первой же записи (no such column / NOT NULL);
    - **лишнее** — в базе есть то, чего в моделях нет. На работу не влияет,
      но значит, что база осталась от прежней версии схемы.

    Нужно потому, что create_all умеет только СОЗДАВАТЬ таблицы: изменили
    модель — база молча осталась старой, и ошибка всплывает позже и не там,
    где её искали.
    """
    # Модели регистрируются в Base.metadata при импорте пакета app.models.
    # Импорт внутри функции: app.models импортирует app.db — на уровне модуля
    # получился бы цикл, а здесь он безопасен.
    from app import models  # noqa: F401

    inspector = inspect(target_engine or engine)
    db_tables = set(inspector.get_table_names())
    meta_tables = set(Base.metadata.tables)

    missing: list[str] = []
    extra: list[str] = []

    for name in sorted(meta_tables - db_tables):
        missing.append(f"таблица {name}")
    for name in sorted(db_tables - meta_tables - {"alembic_version"}):
        extra.append(f"таблица {name}")

    for name in sorted(meta_tables & db_tables):
        db_columns = {c["name"] for c in inspector.get_columns(name)}
        meta_columns = set(Base.metadata.tables[name].columns.keys())
        missing.extend(f"{name}.{col}" for col in sorted(meta_columns - db_columns))
        extra.extend(f"{name}.{col}" for col in sorted(db_columns - meta_columns))

    return missing, extra
