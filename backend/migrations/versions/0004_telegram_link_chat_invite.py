"""Ссылка-приглашение в чат для привязки Telegram-аккаунта

Revision ID: 0004_telegram_link_chat_invite
Revises: 0003_user_role
Create Date: 2026-10-24

Панель просит у бота персональную ссылку-приглашение в чат: код привязки
спрятан в имени ссылки (invite_link.name). Когда пользователь по ней вступает,
бот получает событие chat_member, достаёт код и привязывает аккаунт.

Колонка chat_invite_link хранит созданную ссылку, чтобы не плодить
приглашения: тот же код переиспользует одну и ту же ссылку.
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0004_telegram_link_chat_invite"
down_revision = "0003_user_role"
branch_labels = None
depends_on = None


def _has_column() -> bool:
    columns = {
        c["name"] for c in sa.inspect(op.get_bind()).get_columns("telegram_links")
    }
    return "chat_invite_link" in columns


def upgrade():
    if _has_column():
        return

    with op.batch_alter_table("telegram_links") as batch_op:
        batch_op.add_column(
            sa.Column("chat_invite_link", sa.String(255), nullable=True)
        )


def downgrade():
    with op.batch_alter_table("telegram_links") as batch_op:
        batch_op.drop_column("chat_invite_link")
