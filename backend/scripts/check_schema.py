"""Проверка схемы БД перед стартом приложения.

create_all умеет только СОЗДАВАТЬ таблицы: существующие он не меняет.
Поэтому после правки модели база молча остаётся со старой схемой, и
приложение падает позже — на первой же записи, с невнятной ошибкой
«no such column» или «NOT NULL constraint failed».

    python -m scripts.check_schema

Код возврата: 0 — схема совпадает с моделями, 1 — есть расхождения.
Скрипт запускается в entrypoint.sh перед стартом uvicorn, поэтому
схема разошлась — контейнер не поднимется и скажет об этом в логе.
"""

import sys

from app.db import schema_drift


def main() -> int:
    missing, extra = schema_drift()

    if missing:
        print("Схема базы не совпадает с моделями. Не хватает:", file=sys.stderr)
        for item in missing:
            print(f"  - {item}", file=sys.stderr)
        print("", file=sys.stderr)
        print(
            "Приложение упадёт на первой записи. Исправить:\n"
            "    cd backend && python -m scripts.reset_db\n"
            "(данные базы удалятся, демо-данные восстановятся)",
            file=sys.stderr,
        )
        return 1

    if extra:
        print("В базе есть лишние объекты (на работу не влияет):")
        for item in extra:
            print(f"  - {item}")
        print("Убрать: cd backend && python -m scripts.reset_db")
    else:
        print("Схема базы совпадает с моделями")
    return 0


if __name__ == "__main__":
    sys.exit(main())
