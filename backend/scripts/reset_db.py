"""Пересоздать базу с нуля — нужно после изменения моделей.

    cd backend
    python -m scripts.reset_db          # с подтверждением
    python -m scripts.reset_db -y       # без вопроса

Что делает: удаляет файл SQLite, создаёт схему по актуальным моделям и
заново наполняет базу (администратор из .env + демо-данные).
Все данные пропадают — для разработки это нормально.
"""

import argparse
import sys
from pathlib import Path

from app import models  # noqa: F401 — регистрирует модели в Base.metadata
from app.config import settings
from app.db import Base, engine
from app.logging_config import setup_logging

BACKEND_ROOT = Path(__file__).resolve().parents[1]


def db_path() -> Path | None:
    """Путь к файлу SQLite или None, если база не файловая."""
    if not settings.database_url.startswith("sqlite"):
        return None
    raw = engine.url.database or ""
    if not raw or raw == ":memory:":
        return None
    path = Path(raw)
    return path if path.is_absolute() else BACKEND_ROOT / path


def main() -> int:
    setup_logging(name="reset")
    parser = argparse.ArgumentParser(description="Пересоздать базу по актуальным моделям")
    parser.add_argument("-y", "--yes", action="store_true", help="без подтверждения")
    args = parser.parse_args()

    path = db_path()
    if path is None:
        print(
            f"reset_db работает только с файловой SQLite (сейчас {settings.database_url}). "
            "Для другой БД — миграции Alembic: alembic revision --autogenerate.",
            file=sys.stderr,
        )
        return 1

    if not args.yes:
        answer = input(f"Удалить базу {path} вместе с данными? (yes/no): ").strip().lower()
        if answer not in ("y", "yes", "да"):
            print("Отменено")
            return 1

    # Соединения закрываем — иначе на Windows файл не удалить
    engine.dispose()
    for suffix in ("", "-wal", "-shm"):
        target = Path(str(path) + suffix)
        if target.exists():
            target.unlink()
            print(f"удалён {target.name}")

    Base.metadata.create_all(engine)
    print("схема создана по актуальным моделям")

    from scripts import seed_all

    seed_all.main()
    return 0


if __name__ == "__main__":
    sys.exit(main())
