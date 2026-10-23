"""Окружение Alembic: берём URL из настроек приложения и метаданные из моделей."""

from logging.config import fileConfig

from alembic import context

from app import models  # noqa: F401 — регистрирует все модели в Base.metadata
from app.db import Base, engine

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=str(engine.url),
        target_metadata=target_metadata,
        literal_binds=True,
        render_as_batch=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    def skip_empty(context_, revision, directives):
        # Не создаём пустые миграции, если схема не менялась
        if getattr(config.cmd_opts, "autogenerate", False) and directives[0].upgrade_ops.is_empty():
            directives[:] = []
            print("No changes in schema detected.")

    with engine.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            # SQLite не умеет многие ALTER TABLE — batch-режим пересоздаёт таблицу
            render_as_batch=True,
            process_revision_directives=skip_empty,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
