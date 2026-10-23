"""
Настройка логирования для бэкенда (FastAPI, worker, сиды).

Самодостаточный модуль: только stdlib logging, никаких импортов извне.
Двойной вывод: stdout (для `docker compose logs backend`) + файл (для истории).
"""

import logging
import os
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

# Куда писать логи. LOG_DIR=null в .env — отключить файловый лог (только stdout).
LOG_DIR = Path(os.getenv("LOG_DIR", "./logs"))


def setup_logging(
    name: str = "backend",
    log_dir: Path | None = None,
    level: int = logging.INFO,
    stream_level: int = logging.INFO,
) -> None:
    target_dir = log_dir if log_dir is not None else LOG_DIR

    root = logging.getLogger()
    root.setLevel(logging.DEBUG)
    root.handlers.clear()  # чтобы повторный вызов не дублировал записи

    fmt = logging.Formatter(
        "%(asctime)s | %(levelname)-5s | %(name)s | %(message)s",
        datefmt="%H:%M:%S",
    )
    err_fmt = logging.Formatter(
        "%(asctime)s | %(levelname)-5s | %(name)s | %(funcName)s | %(message)s\n%(exc_info)s",
        datefmt="%H:%M:%S",
    )

    console = logging.StreamHandler()
    console.setLevel(stream_level)
    console.setFormatter(fmt)
    root.addHandler(console)

    if str(target_dir) != "null":
        target_dir.mkdir(parents=True, exist_ok=True)

        main_handler = TimedRotatingFileHandler(
            filename=target_dir / f"{name}.log",
            when="midnight",
            interval=1,
            backupCount=7,
            encoding="utf-8",
        )
        main_handler.setLevel(logging.INFO)
        main_handler.setFormatter(fmt)
        root.addHandler(main_handler)

        error_handler = TimedRotatingFileHandler(
            filename=target_dir / "errors.log",
            when="midnight",
            interval=1,
            backupCount=14,
            encoding="utf-8",
        )
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(err_fmt)
        root.addHandler(error_handler)

    for h in root.handlers:
        h.flush()

    root.info(f"Логирование настроено для {name} -> {target_dir}")


def get_logger(name: str) -> logging.Logger:
    """Логгер для модуля: get_logger(__name__)"""
    return logging.getLogger(name)