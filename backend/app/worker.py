"""Фоновый процесс напоминаний.

Запуск: python -m app.worker
Раз в REMINDER_CHECK_INTERVAL_SECONDS досоздаёт периоды и отправляет напоминания.
Должен работать ровно в одном экземпляре (отдельный контейнер `worker`).
"""

import signal
import time

from app.config import settings
from app.db import SessionLocal
from app.logging_config import get_logger, setup_logging
from app.services import telegram
from app.services.reminders import check_and_send

logger = get_logger("worker")

_running = True


def _stop(signum, frame):
    global _running
    logger.info(f"Получен сигнал {signum}, останавливаю worker")
    _running = False


def run_once() -> int:
    db = SessionLocal()
    try:
        return check_and_send(db)
    except Exception:
        logger.exception("Ошибка при проверке напоминаний")
        db.rollback()
        return 0
    finally:
        db.close()


def main():
    setup_logging(name="worker")
    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)

    interval = max(settings.reminder_check_interval_seconds, 5)
    logger.info(
        f"Worker запущен: проверка каждые {interval} с, напоминание за "
        f"{settings.reminder_days_before} дн., часовой пояс {settings.app_timezone}"
    )
    if not telegram.is_configured():
        logger.warning("Telegram не настроен — напоминания отправляться не будут")

    while _running:
        sent = run_once()
        if sent:
            logger.info(f"Отправлено напоминаний: {sent}")
        # Спим маленькими шагами, чтобы быстро реагировать на остановку контейнера
        for _ in range(interval):
            if not _running:
                break
            time.sleep(1)

    logger.info("Worker остановлен")


if __name__ == "__main__":
    main()
