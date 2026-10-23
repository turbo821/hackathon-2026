import logging

from flask import Flask

from .config import settings
from .extensions import cors, db, migrate
from .logging_config import get_logger, setup_logging
from .models import Message

logger = get_logger("main_init")


def create_app():
    setup_logging(name="backend")
    app = Flask(__name__)

    logger.info("Инициализация backend-приложения")

    logger.info("Инициализация .env-переменных")
    # from_object копирует только UPPERCASE-атрибуты, а поля pydantic-settings
    # в нижнем регистре — поэтому прокидываем нужные значения явно.
    app.config["SQLALCHEMY_DATABASE_URI"] = settings.database_url
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = (
        settings.sqlalchemy_track_modifications
    )
    logger.info(".env-переменные в порядке")

    db.init_app(app)
    migrate.init_app(app, db, render_as_batch=True)
    cors.init_app(app)

    from .routes.health import router as health_router
    from .routes.hello import router as hello_router
    
    app.register_blueprint(health_router, url_prefix="/api")
    app.register_blueprint(hello_router, url_prefix="/api")
    
    # Flask создаёт свой логгер с дефолтным хендлером в stderr.
    # Если его не убрать — каждая запись уйдёт дважды: в наш файл И в stderr мимо хендлеров.
    app.logger.handlers.clear()
    app.logger.setLevel(logging.INFO)

    # werkzeug в dev-режиме тоже печатает access-логи своим хендлером → дубли.
    # В боте ровно так же глушили aiogram: logging.getLogger("aiogram").setLevel(WARNING)
    logging.getLogger("werkzeug").setLevel(logging.WARNING)
    
    return app
