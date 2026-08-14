"""add ai_backtest_trades.updated_at column

Revision ID: f9a0b1c2d3e7
Revises: f9a0b1c2d3e6
Create Date: 2026-08-14 18:35:00.000000+00:00

修复 ai_backtest_trades 表缺少 updated_at 列的问题。
Base 模型定义了 updated_at 字段，但原迁移脚本未创建该列。
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "f9a0b1c2d3e7"
down_revision = "f9a0b1c2d3e6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "ai_backtest_trades",
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_column("ai_backtest_trades", "updated_at")