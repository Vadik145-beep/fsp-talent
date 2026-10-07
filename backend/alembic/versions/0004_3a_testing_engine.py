"""Тест на бэкенде (трек 3a): банк шаблонов движка в БД, журнал показов и ответов.

- items.code — до 64 символов (id шаблонов движка длиннее 32);
- items.time_limit_s — лимит времени шаблона;
- test_answers.instance_id — непрозрачный id показа для клиента;
- test_answers.timed_out — ответ пришёл после лимита (засчитан неверным);
- test_answers.theta_loo — θ без этой задачи (детектор утечек, калибровка);
- у кандидата не больше одной незавершённой сессии (частичный уникальный индекс).

Revision ID: 0004_3a
Revises: 0003_merge_wave2
Create Date: 2026-10-07 12:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004_3a"
down_revision: str | None = "0003_merge_wave2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "items", "code", type_=sa.String(64), existing_type=sa.String(32), existing_nullable=False
    )
    op.add_column(
        "items",
        sa.Column("time_limit_s", sa.Integer(), nullable=True, comment="Лимит времени, сек"),
    )
    op.add_column("test_answers", sa.Column("instance_id", sa.String(32), nullable=True))
    op.create_unique_constraint(
        op.f("uq_test_answers_instance_id"), "test_answers", ["instance_id"]
    )
    op.add_column(
        "test_answers",
        sa.Column("timed_out", sa.Boolean(), server_default="false", nullable=False),
    )
    op.add_column(
        "test_answers",
        sa.Column(
            "theta_loo",
            sa.Float(),
            nullable=True,
            comment="θ кандидата без этой задачи (для детектора утечек и калибровки)",
        ),
    )
    op.create_index(
        "uq_test_sessions_one_in_progress",
        "test_sessions",
        ["candidate_id"],
        unique=True,
        postgresql_where=sa.text("status = 'in_progress'"),
    )


def downgrade() -> None:
    op.drop_index("uq_test_sessions_one_in_progress", table_name="test_sessions")
    op.drop_column("test_answers", "theta_loo")
    op.drop_column("test_answers", "timed_out")
    op.drop_constraint(op.f("uq_test_answers_instance_id"), "test_answers", type_="unique")
    op.drop_column("test_answers", "instance_id")
    op.drop_column("items", "time_limit_s")
    op.alter_column(
        "items", "code", type_=sa.String(32), existing_type=sa.String(64), existing_nullable=False
    )
