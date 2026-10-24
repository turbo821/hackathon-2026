"""Начальная схема Invoice Keeper

Revision ID: 0001_initial
Revises:
Create Date: 2026-10-24

Схема берётся прямо из моделей (app/models), поэтому миграция и модели
не могут разойтись. Дальше изменения идут обычным циклом:

    alembic revision --autogenerate -m "что изменили"
    alembic upgrade head
"""

from alembic import op

from app import models  # noqa: F401 — регистрирует все модели в Base.metadata
from app.db import Base

# revision identifiers, used by Alembic.
revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    Base.metadata.create_all(bind=op.get_bind())


def downgrade():
    Base.metadata.drop_all(bind=op.get_bind())
