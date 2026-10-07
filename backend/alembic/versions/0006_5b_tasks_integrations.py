"""Задания и интеграция с ATS (трек 5b).

- task_submissions: у кандидата не больше одного активного задания (частичный уникальный индекс);
- company_api_tokens: API-токены компании для выгрузки в ATS (хранится SHA-256);
- webhook_endpoints: адреса вебхуков компании (секрет подписи HMAC, события);
- webhook_deliveries: очередь и журнал доставок вебхуков (повторы при ошибке).

Revision ID: 0006_5b
Revises: 0005_merge_wave3
Create Date: 2026-10-07 18:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0006_5b"
down_revision: str | None = "0005_merge_wave3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "uq_task_submissions_one_assigned",
        "task_submissions",
        ["candidate_id"],
        unique=True,
        postgresql_where=sa.text("status = 'assigned'"),
    )

    op.create_table(
        "company_api_tokens",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("company_id", sa.BigInteger(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("token_prefix", sa.String(length=16), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("created_by", sa.BigInteger(), nullable=True),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["companies.id"],
            name=op.f("fk_company_api_tokens_company_id_companies"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.id"],
            name=op.f("fk_company_api_tokens_created_by_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_company_api_tokens")),
        sa.UniqueConstraint("token_hash", name=op.f("uq_company_api_tokens_token_hash")),
    )
    op.create_index(op.f("ix_company_api_tokens_company_id"), "company_api_tokens", ["company_id"])

    op.create_table(
        "webhook_endpoints",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("company_id", sa.BigInteger(), nullable=False),
        sa.Column("url", sa.String(length=500), nullable=False),
        sa.Column("secret", sa.String(length=128), nullable=False),
        sa.Column("events", postgresql.ARRAY(sa.String(length=64)), nullable=False),
        sa.Column("active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("created_by", sa.BigInteger(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["companies.id"],
            name=op.f("fk_webhook_endpoints_company_id_companies"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.id"],
            name=op.f("fk_webhook_endpoints_created_by_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_webhook_endpoints")),
    )
    op.create_index(op.f("ix_webhook_endpoints_company_id"), "webhook_endpoints", ["company_id"])

    op.create_table(
        "webhook_deliveries",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("endpoint_id", sa.BigInteger(), nullable=False),
        sa.Column("event", sa.String(length=64), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_status_code", sa.Integer(), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["endpoint_id"],
            ["webhook_endpoints.id"],
            name=op.f("fk_webhook_deliveries_endpoint_id_webhook_endpoints"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_webhook_deliveries")),
    )
    op.create_index(
        op.f("ix_webhook_deliveries_endpoint_id"), "webhook_deliveries", ["endpoint_id"]
    )
    op.create_index(op.f("ix_webhook_deliveries_status"), "webhook_deliveries", ["status"])


def downgrade() -> None:
    op.drop_index(op.f("ix_webhook_deliveries_status"), table_name="webhook_deliveries")
    op.drop_index(op.f("ix_webhook_deliveries_endpoint_id"), table_name="webhook_deliveries")
    op.drop_table("webhook_deliveries")
    op.drop_index(op.f("ix_webhook_endpoints_company_id"), table_name="webhook_endpoints")
    op.drop_table("webhook_endpoints")
    op.drop_index(op.f("ix_company_api_tokens_company_id"), table_name="company_api_tokens")
    op.drop_table("company_api_tokens")
    op.drop_index("uq_task_submissions_one_assigned", table_name="task_submissions")
