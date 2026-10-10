"""Приглашение по отклику: способ связи и сообщение рекрутера.

Когда рекрутер ставит отклику статус «Приглашён», он указывает, как с ним связаться,
и может написать пару слов («созвонимся в четверг»). Соискатель видит это в своих откликах
и в письме — так же, как способ связи в приглашении [ТЗ 2.2 п.2].

- applications.contact_type, contact_value — способ связи (email|phone|telegram|other);
- applications.invite_message — сообщение рекрутера (необязательно).

Revision ID: 0009_app_contact
Revises: 0008_w8
Create Date: 2026-10-10 12:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0009_app_contact"
down_revision: str | None = "0008_w8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("applications", sa.Column("contact_type", sa.String(length=16), nullable=True))
    op.add_column("applications", sa.Column("contact_value", sa.String(length=200), nullable=True))
    op.add_column(
        "applications",
        sa.Column("invite_message", sa.Text(), nullable=False, server_default=""),
    )


def downgrade() -> None:
    op.drop_column("applications", "invite_message")
    op.drop_column("applications", "contact_value")
    op.drop_column("applications", "contact_type")
