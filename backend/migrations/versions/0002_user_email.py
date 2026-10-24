"""Обязательный email пользователя

Revision ID: 0002_user_email
Revises: 0001_initial
Create Date: 2026-10-24

Свежая база: 0001 создаёт таблицы по моделям, колонка email уже есть — пропускаем.
Старая база: добавляем колонку, заполняем существующих пользователей
(прежний админ — ADMIN_EMAIL, остальные — <логин>@example.com),
затем делаем её NOT NULL и UNIQUE.
"""

import os

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0002_user_email"
down_revision = "0001_initial"
branch_labels = None
depends_on = None

# Прежние настройки админа из .env (сейчас их в настройках нет)
OLD_ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin").strip().lower()
OLD_ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "admin@example.com").strip().lower()


def _has_email() -> bool:
    return "email" in {c["name"] for c in sa.inspect(op.get_bind()).get_columns("users")}


def upgrade():
    if _has_email():
        return

    with op.batch_alter_table("users") as batch_op:
        batch_op.add_column(sa.Column("email", sa.String(255), nullable=True))

    bind = op.get_bind()
    bind.execute(
        sa.text("UPDATE users SET email = :email WHERE lower(username) = :username"),
        {"email": OLD_ADMIN_EMAIL, "username": OLD_ADMIN_USERNAME},
    )
    bind.execute(
        sa.text("UPDATE users SET email = lower(username) || '@example.com' WHERE email IS NULL")
    )

    with op.batch_alter_table("users") as batch_op:
        batch_op.alter_column("email", existing_type=sa.String(255), nullable=False)
        batch_op.create_unique_constraint("uq_users_email", ["email"])


def downgrade():
    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_constraint("uq_users_email", type_="unique")
        batch_op.drop_column("email")