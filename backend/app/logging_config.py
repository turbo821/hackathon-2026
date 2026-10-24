"""Логирование: только stdout (его видно в `docker compose logs`).

Файловые логи с ротацией для каркаса не нужны — если понадобятся,
добавьте FileHandler в setup_logging.
"""

import logging


def setup_logging(name: str = "backend", level: int = logging.INFO) -> None:
    root = logging.getLogger()
    root.setLevel(level)
    root.handlers.clear()  # чтобы повторный вызов не дублировал записи

    handler = logging.StreamHandler()
    handler.setFormatter(
        logging.Formatter("%(asctime)s | %(levelname)-5s | %(name)s | %(message)s", datefmt="%H:%M:%S")
    )
    root.addHandler(handler)
    root.info(f"Логирование настроено для {name} (stdout)")


def get_logger(name: str) -> logging.Logger:
    """Логгер для модуля: get_logger(__name__)"""
    return logging.getLogger(name)
