#!/bin/sh
set -e
# Миграции и сиды (админ из .env + тестовые данные) при каждом старте backend
alembic upgrade head
python -m scripts.seed_all
exec "$@"
