"""Экспорт OpenAPI-спецификации в файл.

Требование кейса: к решению должна быть приложена спецификация в формате
.yml или .json. FastAPI отдаёт её по /api/v1/openapi.json, но для передачи
решения нужен файл в репозитории.

Запуск из папки backend/:

    python -m scripts.export_openapi

Результат: backend/openapi.json
"""

import json
from pathlib import Path

from app.main import app

OUTPUT = Path(__file__).resolve().parents[1] / "openapi.json"


def main():
    spec = app.openapi()
    OUTPUT.write_text(json.dumps(spec, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"OpenAPI записан: {OUTPUT}")


if __name__ == "__main__":
    main()
