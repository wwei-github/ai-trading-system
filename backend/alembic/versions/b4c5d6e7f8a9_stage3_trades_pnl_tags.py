"""stage3_trades_pnl_and_trade_tags

Revision ID: b4c5d6e7f8a9
Revises: a3b2c4d5e6f7
Create Date: 2026-08-14 02:30:00.000000+00:00

Stage 3 新增：
- trades 表盈亏计算字段（pnl / pnl_ratio / matched_trade_id / holding_seconds）
- trade_tags 新表（标签 CRUD + 颜色 + 使用计数）
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'b4c5d6e7f8a9'
down_revision: Union[str, None] = 'a3b2c4d5e6f7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. trades 表新增盈亏字段
    op.add_column(
        'trades',
        sa.Column('pnl', sa.Numeric(precision=20, scale=8), nullable=True),
    )
    op.add_column(
        'trades',
        sa.Column('pnl_ratio', sa.Numeric(precision=10, scale=4), nullable=True),
    )
    op.add_column(
        'trades',
        sa.Column('matched_trade_id', postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        'trades',
        sa.Column('holding_seconds', sa.Integer(), nullable=True),
    )

    # 2. 创建 trade_tags 表
    op.create_table(
        'trade_tags',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            'user_id',
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey('users.id'),
            nullable=False,
        ),
        sa.Column('name', sa.String(length=50), nullable=False),
        sa.Column('color', sa.String(length=20), nullable=False, server_default='#1890ff'),
        sa.Column('usage_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.UniqueConstraint('user_id', 'name', name='uq_trade_tags_user_name'),
    )
    op.create_index(
        'ix_trade_tags_user_id', 'trade_tags', ['user_id']
    )


def downgrade() -> None:
    op.drop_index('ix_trade_tags_user_id', table_name='trade_tags')
    op.drop_table('trade_tags')
    op.drop_column('trades', 'holding_seconds')
    op.drop_column('trades', 'matched_trade_id')
    op.drop_column('trades', 'pnl_ratio')
    op.drop_column('trades', 'pnl')
