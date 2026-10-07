"""Слияние веток миграций волны 3 (3a — тест, 3b — приглашения, 3c — тесты из вакансий).

Revision ID: 0005_merge_wave3
Revises: 0004_3a, 0004_3b, 0004_3c
"""

from collections.abc import Sequence

revision: str = "0005_merge_wave3"
down_revision: str | Sequence[str] | None = ("0004_3a", "0004_3b", "0004_3c")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
