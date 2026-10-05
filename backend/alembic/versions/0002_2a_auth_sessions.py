"""Трек 2a: refresh-сессии (хеш токена, ротация) и журнал ограничения попыток входа/писем.

Revision ID: 0002_2a
Revises: 0001
Create Date: 2026-10-06 02:39:29.453446
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '0002_2a'
down_revision: str | None = '0001'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table('auth_throttle_events',
    sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
    sa.Column('kind', sa.String(length=32), nullable=False),
    sa.Column('key', sa.String(length=320), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_auth_throttle_events'))
    )
    op.create_index('ix_auth_throttle_events_kind_key', 'auth_throttle_events', ['kind', 'key', 'created_at'], unique=False)
    op.create_table('refresh_sessions',
    sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
    sa.Column('user_id', sa.BigInteger(), nullable=False),
    sa.Column('token_hash', sa.String(length=64), nullable=False),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('user_agent', sa.String(length=300), nullable=True),
    sa.Column('ip', sa.String(length=45), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_refresh_sessions')),
    sa.UniqueConstraint('token_hash', name=op.f('uq_refresh_sessions_token_hash'))
    )
    op.create_index(op.f('ix_refresh_sessions_user_id'), 'refresh_sessions', ['user_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_refresh_sessions_user_id'), table_name='refresh_sessions')
    op.drop_table('refresh_sessions')
    op.drop_index('ix_auth_throttle_events_kind_key', table_name='auth_throttle_events')
    op.drop_table('auth_throttle_events')
