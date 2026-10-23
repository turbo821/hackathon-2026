#!/bin/sh
set -e
flask --app main db upgrade
python -m scripts.seed_all
exec "$@"