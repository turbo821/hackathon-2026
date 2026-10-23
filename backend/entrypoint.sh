#!/bin/sh
set -e

# Схема БД приводится к актуальной версии при каждом старте.
alembic upgrade head

# Администратор из .env + тестовые данные (идемпотентно, дубли не создаются).
python -m scripts.seed_all

exec "$@"
