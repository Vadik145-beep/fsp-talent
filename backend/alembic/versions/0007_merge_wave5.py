"""Слияние веток миграций волны 5 (5a — вакансии, 5b — задания и интеграции).

Revision ID: 0007_merge_wave5
Revises: 0006_5a, 0006_5b
"""

from collections.abc import Sequence

revision: str = "0007_merge_wave5"
down_revision: str | Sequence[str] | None = ("0006_5a", "0006_5b")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
