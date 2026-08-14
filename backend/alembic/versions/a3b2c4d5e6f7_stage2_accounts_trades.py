"""stage2_accounts_is_enabled_trades_source

Revision ID: a3b2c4d5e6f7
Revises: e199c37e0800
Create Date: 2026-08-14 01:10:00.000000+00:00

Stage 2 新增字段：
- exchange_accounts.is_enabled：账号启停（同步任务和策略只读取 enabled=true 的账号）
- trades.source：交易来源标记（manual / exchange_sync / import / paper / live）
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a3b2c4d5e6f7'
down_revision: Union[str, None] = 'e199c37e0800'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. exchange_accounts.is_enabled：默认 true（已有账号视为启用）
    op.add_column(
        'exchange_accounts',
        sa.Column(
            'is_enabled',
            sa.Boolean(),
            nullable=False,
            server_default=sa.text('true'),
        ),
    )

    # 2. trades.source：默认 manual（已有交易记录视为手动录入）
    op.add_column(
        'trades',
        sa.Column(
            'source',
            sa.String(length=20),
            nullable=False,
            server_default='manual',
        ),
    )


def downgrade() -> None:
    op.drop_column('trades', 'source')
    op.drop_column('exchange_accounts', 'is_enabled')
