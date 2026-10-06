"""Слияние веток миграций волны 2 (2a — сессии авторизации, 2b — профили).

Revision ID: 0003_merge_wave2
Revises: 0002_2a, 0002_2b
"""

from collections.abc import Sequence

revision: str = "0003_merge_wave2"
down_revision: str | Sequence[str] | None = ("0002_2a", "0002_2b")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
