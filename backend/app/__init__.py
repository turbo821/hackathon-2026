import logging

from flask import Flask, jsonify
from flask_smorest import Api

from .config import settings
from .extensions import cors, db, migrate
from .logging_config import get_logger, setup_logging
from . import models  # noqa: F401 — нужен, чтобы миграции видели модели

logger = get_logger("main_init")


def create_app(log_name: str = "backend", config_overrides: dict | None = None):
    setup_logging(name=log_name)
    app = Flask(__name__)

    logger.info("Инициализация backend-приложения")

    # from_object копирует только UPPERCASE-атрибуты, а поля pydantic-settings
    # в нижнем регистре — поэтому прокидываем нужные значения явно.
    app.config.update(
        SQLALCHEMY_DATABASE_URI=settings.database_url,
        SQLALCHEMY_TRACK_MODIFICATIONS=settings.sqlalchemy_track_modifications,
        JSON_SORT_KEYS=False,
        # --- OpenAPI / Swagger (flask-smorest) ---
        API_TITLE="Invoice Keeper API",
        API_VERSION="1.0.0",
        OPENAPI_VERSION="3.0.3",
        OPENAPI_URL_PREFIX="/api/v1",
        OPENAPI_JSON_PATH="openapi.json",
        OPENAPI_SWAGGER_UI_PATH="/docs",
        OPENAPI_SWAGGER_UI_URL="https://cdn.jsdelivr.net/npm/swagger-ui-dist/",
        API_SPEC_OPTIONS={
            "info": {
                "description": (
                    "Напоминания о регулярных платежах. Авторизация: получите токен в "
                    "`POST /api/v1/auth/login` и нажмите **Authorize** (Bearer)."
                )
            },
            "components": {
                "securitySchemes": {
                    "bearerAuth": {"type": "http", "scheme": "bearer", "bearerFormat": "JWT"}
                }
            },
            "security": [{"bearerAuth": []}],
        },
    )
    if config_overrides:
        app.config.update(config_overrides)
    logger.info(f".env-переменные в порядке (часовой пояс {settings.app_timezone})")

    db.init_app(app)
    migrate.init_app(app, db, render_as_batch=True)
    origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()] or "*"
    cors.init_app(app, resources={r"/api/*": {"origins": origins}})
    api = Api(app)
    app.extensions["smorest_api"] = api

    from .routes.audit_logs import router as audit_logs_router
    from .routes.auth import router as auth_router
    from .routes.health import router as health_router
    from .routes.payment_occurrences import router as occurrences_router
    from .routes.recurring_payments import router as recurring_router
    from .routes.summary import router as summary_router
    from .routes.users import router as users_router

    for router in (
        auth_router,
        recurring_router,
        occurrences_router,
        summary_router,
        users_router,
        audit_logs_router,
        health_router,
    ):
        api.register_blueprint(router)

    @app.errorhandler(500)
    def internal_error(err):
        logger.exception("Необработанная ошибка")
        db.session.rollback()
        return jsonify(code=500, status="Internal Server Error", message="Внутренняя ошибка сервера"), 500

    # Flask создаёт свой логгер с дефолтным хендлером в stderr.
    # Если его не убрать — каждая запись уйдёт дважды: в наш файл И в stderr мимо хендлеров.
    app.logger.handlers.clear()
    app.logger.setLevel(logging.INFO)

    # werkzeug в dev-режиме тоже печатает access-логи своим хендлером → дубли.
    logging.getLogger("werkzeug").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)

    logger.info("Приложение готово: API /api/v1, Swagger /api/v1/docs")
    return app
