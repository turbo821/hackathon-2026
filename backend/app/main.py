"""Сборка FastAPI-приложения.

Единая точка входа: backend/main.py → `uvicorn main:app`.
Документация: /api/v1/docs (Swagger) и /api/v1/redoc.
"""

import logging

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.errors import register_error_handlers
from app.logging_config import get_logger, setup_logging
from app.middleware import RequestContextMiddleware
from app.routers import (
    auth,
    misc,
    payment_occurrences,
    payments,
    recurring_payments,
    summary,
    users,
)

logger = get_logger("main_init")

API_PREFIX = "/api/v1"

TAGS = [
    {"name": "auth", "description": "Вход, текущий пользователь, выход"},
    {
        "name": "recurring-payments",
        "description": "Регулярные платежи (шаблоны). Создание и удаление — только администратор",
    },
    {
        "name": "payment-occurrences",
        "description": "Периоды платежей: что и когда оплатить, что оплачено и что просрочено",
    },
    {"name": "summary", "description": "Итоги по валютам (без конвертации)"},
    {"name": "users", "description": "Обычные пользователи. Только администратор"},
    {"name": "service", "description": "Служебное"},
]


def create_app(log_name: str = "backend") -> FastAPI:
    setup_logging(name=log_name)
    logger.info("Инициализация backend-приложения")

    app = FastAPI(
        title="Invoice Keeper API",
        version="1.0.0",
        description=(
            "Напоминания о регулярных платежах. Все эндпоинты — под префиксом "
            f"`{API_PREFIX}`. Авторизация: получите токен в `POST {API_PREFIX}/auth/login` "
            "и нажмите **Authorize** (вставьте access_token)."
        ),
        openapi_tags=TAGS,
        docs_url=f"{API_PREFIX}/docs",
        redoc_url=f"{API_PREFIX}/redoc",
        openapi_url=f"{API_PREFIX}/openapi.json",
    )

    origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()] or [
        "*"
    ]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    # Контекст запроса (request id, пользователь) и журнал обращений.
    # Ставится последним, чтобы оборачивать в том числе CORS-ответы.
    app.add_middleware(RequestContextMiddleware)
    register_error_handlers(app)

    api = APIRouter(prefix=API_PREFIX)
    for module in (
        auth,
        recurring_payments,
        payment_occurrences,
        payments,
        summary,
        users,
        misc,
    ):
        api.include_router(module.router)
    app.include_router(api)

    # Совместимость с фронтендом: у него базовый адрес по умолчанию
    # http://localhost:5000/api, поэтому /api/hello должен отвечать и без версии.
    @app.get("/api/hello", include_in_schema=False)
    async def hello_compat():
        return {"message": "Invoice Keeper API на связи"}

    # uvicorn печатает каждый запрос — оставляем только предупреждения
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)

    logger.info(
        f"Приложение готово: API {API_PREFIX}, Swagger {API_PREFIX}/docs, "
        f"часовой пояс {settings.app_timezone}"
    )
    return app


app = create_app()
