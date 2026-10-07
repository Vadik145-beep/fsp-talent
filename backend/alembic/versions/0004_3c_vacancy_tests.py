"""Трек 3c: тесты, собранные из текста вакансии (T4.8).

Revision ID: 0004_3c
Revises: 0003_merge_wave2
Create Date: 2026-10-07 10:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004_3c"
down_revision: str | None = "0003_merge_wave2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "vacancy_tests",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("vacancy_title", sa.String(length=200), nullable=False),
        sa.Column("vacancy_text", sa.Text(), nullable=False),
        sa.Column("specialization", sa.String(length=32), nullable=False),
        sa.Column("grade", sa.String(length=16), nullable=False),
        sa.Column("parser", sa.String(length=16), nullable=False),
        sa.Column("result", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_vacancy_tests")),
    )


def downgrade() -> None:
    op.drop_table("vacancy_tests")
