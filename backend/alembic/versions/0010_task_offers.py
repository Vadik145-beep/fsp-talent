"""Задачи недели на выбор: кандидату предлагается до трёх задач от разных компаний.

Раньше у кандидата было не больше одного активного (assigned) задания — уникальный индекс
по candidate_id. Теперь активных может быть несколько (по одному на компанию), уникальность —
по паре (candidate_id, task_id) среди активных. Новый статус `skipped` (выбрал другую задачу)
хранится в той же строковой колонке, схема статусов не меняется.

Revision ID: 0010_task_offers
Revises: 0009_app_contact
Create Date: 2026-10-10 12:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0010_task_offers"
down_revision: str | None = "0009_app_contact"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_index("uq_task_submissions_one_assigned", table_name="task_submissions")
    op.create_index(
        "uq_task_submissions_offer",
        "task_submissions",
        ["candidate_id", "task_id"],
        unique=True,
        postgresql_where=sa.text("status = 'assigned'"),
    )


def downgrade() -> None:
    # лишние предложения недели снимаем, оставляя самое раннее — иначе старый индекс не создать
    op.execute(
        """
        UPDATE task_submissions s SET status = 'skipped'
        WHERE s.status = 'assigned' AND EXISTS (
            SELECT 1 FROM task_submissions o
            WHERE o.candidate_id = s.candidate_id AND o.status = 'assigned' AND o.id < s.id
        )
        """
    )
    op.drop_index("uq_task_submissions_offer", table_name="task_submissions")
    op.create_index(
        "uq_task_submissions_one_assigned",
        "task_submissions",
        ["candidate_id"],
        unique=True,
        postgresql_where=sa.text("status = 'assigned'"),
    )
