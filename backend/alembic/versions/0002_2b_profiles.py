"""Профиль кандидата (трек 2b): флаг согласия на публикацию, снимок ФСП-скора и бейджей,
порядок технологий в стеке.

- candidate_profiles.publication_consent — без согласия кандидата нет в выдаче (T2.4);
  история выдачи/отзыва — в таблице consents.
- candidate_profiles.fsp_score / fsp_badges — снимок ФСП-скора и бейджей (T5.3), пересчитывается
  после синхронизации достижений; хранится, чтобы сортировать банк кандидатов по ФСП в SQL.
- candidate_skills.position — порядок технологий, как его ввёл кандидат.

Revision ID: 0002_2b
Revises: 0001
Create Date: 2026-10-06 18:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002_2b"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "candidate_profiles",
        sa.Column("publication_consent", sa.Boolean(), server_default="false", nullable=False),
    )
    op.add_column("candidate_profiles", sa.Column("fsp_score", sa.Float(), nullable=True))
    op.add_column(
        "candidate_profiles",
        sa.Column(
            "fsp_badges",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
    )
    op.add_column(
        "candidate_skills",
        sa.Column("position", sa.Integer(), server_default="0", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("candidate_skills", "position")
    op.drop_column("candidate_profiles", "fsp_badges")
    op.drop_column("candidate_profiles", "fsp_score")
    op.drop_column("candidate_profiles", "publication_consent")
