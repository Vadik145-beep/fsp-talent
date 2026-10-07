"""Вакансии и отклики на БД (трек 5a, E8).

- vacancies.team_description — описание команды (как у потребности), по умолчанию пусто;
- индекс (status, published_at) — лента опубликованных вакансий для кандидатов;
- индекс applications(candidate_id, created_at) уже покрыт ix_applications_candidate_id.

Revision ID: 0006_5a
Revises: 0005_merge_wave3
Create Date: 2026-10-07 18:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006_5a"
down_revision: str | None = "0005_merge_wave3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "vacancies",
        sa.Column("team_description", sa.Text(), nullable=False, server_default=""),
    )
    op.create_index("ix_vacancies_status_published", "vacancies", ["status", "published_at"])


def downgrade() -> None:
    op.drop_index("ix_vacancies_status_published", table_name="vacancies")
    op.drop_column("vacancies", "team_description")
