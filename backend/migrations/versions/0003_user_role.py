"""Роль пользователя: superadmin / admin / user

Revision ID: 0003_user_role
Revises: 0002_user_email
Create Date: 2026-10-24

Раньше админ определялся логином из .env (ADMIN_USERNAME). Теперь роль
хранится в БД. Старая база: все становятся user, прежний админ — admin
(доступ не теряет), аккаунт с логином SUPERADMIN_USERNAME — superadmin.
Дальше роль суперадмина поддерживает сид scripts.seed_superadmin.
"""

import os

import sqlalchemy as sa
from alembic import op

from app.config import settings

# revision identifiers, used by Alembic.
revision = "0003_user_role"
down_revision = "0002_user_email"
branch_labels = None
depends_on = None

OLD_ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin").strip().lower()


def _has_role() -> bool:
    return "role" in {c["name"] for c in sa.inspect(op.get_bind()).get_columns("users")}


def upgrade():
    if _has_role():  # свежая база: 0001 уже создала колонку по моделям
        return

    with op.batch_alter_table("users") as batch_op:
        batch_op.add_column(sa.Column("role", sa.String(16), nullable=True))

    bind = op.get_bind()
    bind.execute(sa.text("UPDATE users SET role = 'user'"))
    bind.execute(
        sa.text("UPDATE users SET role = 'admin' WHERE lower(username) = :username"),
        {"username": OLD_ADMIN_USERNAME},
    )
    bind.execute(
        sa.text("UPDATE users SET role = 'superadmin' WHERE lower(username) = :username"),
        {"username": settings.superadmin_username.strip().lower()},
    )

    with op.batch_alter_table("users") as batch_op:
        batch_op.alter_column("role", existing_type=sa.String(16), nullable=False)


def downgrade():
    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_column("role")