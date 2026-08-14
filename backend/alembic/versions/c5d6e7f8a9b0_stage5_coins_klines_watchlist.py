"""stage5_coins_klines_watchlist

Revision ID: c5d6e7f8a9b0
Revises: b4c5d6e7f8a9
Create Date: 2026-08-14 10:30:00.000000+00:00

Stage 5 新增：
- klines 表：K 线历史数据（symbol + timeframe + open_time 唯一索引去重）
- watchlist 表：用户自选币种（user_id + symbol 唯一）
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'c5d6e7f8a9b0'
down_revision: Union[str, None] = 'b4c5d6e7f8a9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. klines 表
    op.create_table(
        'klines',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('symbol', sa.String(length=30), nullable=False),
        sa.Column('timeframe', sa.String(length=10), nullable=False),
        sa.Column('open_time', sa.DateTime(timezone=True), nullable=False),
        sa.Column('open', sa.Float(), nullable=False),
        sa.Column('high', sa.Float(), nullable=False),
        sa.Column('low', sa.Float(), nullable=False),
        sa.Column('close', sa.Float(), nullable=False),
        sa.Column('volume', sa.Float(), nullable=False, server_default='0'),
        sa.Column('quote_volume', sa.Float(), nullable=True),
        sa.Column('source', sa.String(length=20), nullable=False, server_default='ccxt'),
        sa.Column('exchange', sa.String(length=30), nullable=False, server_default='binance'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('symbol', 'timeframe', 'open_time', name='uq_klines_symbol_tf_opentime'),
    )
    op.create_index('ix_klines_symbol', 'klines', ['symbol'])
    op.create_index('ix_klines_timeframe', 'klines', ['timeframe'])
    op.create_index('ix_klines_open_time', 'klines', ['open_time'])
    op.create_index(
        'ix_klines_symbol_tf_time', 'klines', ['symbol', 'timeframe', 'open_time']
    )

    # 2. watchlist 表
    op.create_table(
        'watchlist',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            'user_id',
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey('users.id'),
            nullable=False,
        ),
        sa.Column('symbol', sa.String(length=30), nullable=False),
        sa.Column('note', sa.String(length=200), nullable=True),
        sa.Column('sort_order', sa.Integer(), nullable=False, server_default='100'),
        sa.Column('added_price', sa.Float(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.UniqueConstraint('user_id', 'symbol', name='uq_watchlist_user_symbol'),
    )
    op.create_index('ix_watchlist_user_id', 'watchlist', ['user_id'])
    op.create_index('ix_watchlist_user_sort', 'watchlist', ['user_id', 'sort_order'])


def downgrade() -> None:
    op.drop_index('ix_watchlist_user_sort', table_name='watchlist')
    op.drop_index('ix_watchlist_user_id', table_name='watchlist')
    op.drop_table('watchlist')

    op.drop_index('ix_klines_symbol_tf_time', table_name='klines')
    op.drop_index('ix_klines_open_time', table_name='klines')
    op.drop_index('ix_klines_timeframe', table_name='klines')
    op.drop_index('ix_klines_symbol', table_name='klines')
    op.drop_table('klines')
