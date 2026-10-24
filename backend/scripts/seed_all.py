"""Наполнение базы. Запуск из папки backend/: python -m scripts.seed_all"""

from app.db import SessionLocal
from app.logging_config import setup_logging

from . import seed_admin, seed_demo

SEEDS = [
    seed_admin,  # администратор из .env — всегда первым
    seed_demo,
    # сюда добавлять новые скрипты (модуль с функцией run(db))
]


def main():
    setup_logging(name="seed")
    db = SessionLocal()
    try:
        for seed in SEEDS:
            seed.run(db)
    finally:
        db.close()


if __name__ == "__main__":
    main()
