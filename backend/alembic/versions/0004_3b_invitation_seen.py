"""Приглашения (трек 3b): отметка «рекрутер видел ответ» для счётчика уведомлений (T7.8).

- invitations.recruiter_seen_at — когда рекрутер последний раз открыл карточку приглашения;
  ответ кандидата (просмотр, принятие, отказ) позже этой отметки считается новым.
- индекс (company_id, candidate_id) — проверка «одно активное приглашение компании кандидату».

Revision ID: 0004_3b
Revises: 0003_merge_wave2
Create Date: 2026-10-07 12:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004_3b"
down_revision: str | None = "0003_merge_wave2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "invitations",
        sa.Column("recruiter_seen_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_invitations_company_candidate", "invitations", ["company_id", "candidate_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_invitations_company_candidate", table_name="invitations")
    op.drop_column("invitations", "recruiter_seen_at")
