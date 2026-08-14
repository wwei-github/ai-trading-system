"""fix ai backtest created_at/updated_at defaults

Revision ID: f9a0b1c2d3e6
Revises: f9a0b1c2d3e5
Create Date: 2026-08-14 18:30:00.000000+00:00

修复 Stage 10 迁移中 ai_backtests 和 ai_backtest_trades 表的
created_at/updated_at 字段缺少 server_default 的问题。
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "f9a0b1c2d3e6"
down_revision = "f9a0b1c2d3e5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ai_backtests
    op.alter_column(
        "ai_backtests", "created_at",
        server_default=sa.func.now(),
        existing_type=sa.DateTime(timezone=True),
        existing_nullable=False,
    )
    op.alter_column(
        "ai_backtests", "updated_at",
        server_default=sa.func.now(),
        existing_type=sa.DateTime(timezone=True),
        existing_nullable=False,
    )

    # ai_backtest_trades
    op.alter_column(
        "ai_backtest_trades", "created_at",
        server_default=sa.func.now(),
        existing_type=sa.DateTime(timezone=True),
        existing_nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "ai_backtest_trades", "created_at",
        server_default=None,
        existing_type=sa.DateTime(timezone=True),
        existing_nullable=False,
    )
    op.alter_column(
        "ai_backtests", "updated_at",
        server_default=None,
        existing_type=sa.DateTime(timezone=True),
        existing_nullable=False,
    )
    op.alter_column(
        "ai_backtests", "created_at",
        server_default=None,
        existing_type=sa.DateTime(timezone=True),
        existing_nullable=False,
    )