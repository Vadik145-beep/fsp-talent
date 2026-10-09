"""Заявленный грейд соискателя — «грейд не подтверждён» (трек 8, ответ организаторов FTT.4).

Грейд соискатель может выбрать сам (онбординг), но официально грейд присваивается только
по результату теста: `candidate_profiles.grade` по-прежнему пишет только тест. Заявленный
грейд хранится отдельно и в выдачу работодателю не попадает.

- candidate_profiles.declared_specialization, declared_grade — что выбрал соискатель;
- candidate_profiles.declared_at — когда.

Revision ID: 0008_w8
Revises: 0007_merge_wave5
Create Date: 2026-10-09 12:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0008_w8"
down_revision: str | None = "0007_merge_wave5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "candidate_profiles",
        sa.Column(
            "declared_specialization",
            sa.String(length=32),
            sa.ForeignKey("specializations.code", name="fk_candidate_profiles_declared_spec"),
            nullable=True,
        ),
    )
    op.add_column(
        "candidate_profiles",
        sa.Column(
            "declared_grade",
            sa.String(length=32),
            sa.ForeignKey("grades.code", name="fk_candidate_profiles_declared_grade_grades"),
            nullable=True,
        ),
    )
    op.add_column(
        "candidate_profiles",
        sa.Column("declared_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("candidate_profiles", "declared_at")
    op.drop_column("candidate_profiles", "declared_grade")
    op.drop_column("candidate_profiles", "declared_specialization")
