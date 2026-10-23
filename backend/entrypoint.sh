#!/bin/sh
set -e
# Миграции и сиды (админ из .env + тестовые данные) при каждом старте backend
flask --app main db upgrade
python -m scripts.seed_all
exec "$@"
