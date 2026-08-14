"""add ai backtest tables

Revision ID: f9a0b1c2d3e5
Revises: f9a0b1c2d3e4
Create Date: 2026-08-14 18:00:00.000000+00:00

Stage 10 新增：
- ai_backtests 表：AI 回测主记录
- ai_backtest_trades 表：AI 回测交易明细
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "f9a0b1c2d3e5"
down_revision = "f9a0b1c2d3e4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ai_backtests
    op.create_table(
        "ai_backtests",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("strategy_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("symbol", sa.String(20), nullable=False),
        sa.Column("timeframe", sa.String(10), nullable=False),
        sa.Column("start_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("mode", sa.String(20), nullable=False),
        sa.Column("kline_count", sa.Integer(), nullable=True),
        sa.Column("time_span_value", sa.Integer(), nullable=True),
        sa.Column("time_span_unit", sa.String(10), nullable=True),
        sa.Column("initial_capital", sa.Numeric(precision=20, scale=2), nullable=False),
        sa.Column("fee_rate", sa.Float(), nullable=False, server_default=sa.text("0.001")),
        sa.Column("use_ai", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("total_klines", sa.Integer(), nullable=False),
        sa.Column("completed_klines", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("status", sa.String(20), nullable=False, server_default=sa.text("'pending'")),
        sa.Column("result_summary", postgresql.JSONB(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_ai_backtests_user_id_created_at",
        "ai_backtests", ["user_id", sa.text("created_at DESC")],
    )
    op.create_foreign_key(
        "fk_ai_backtests_strategy_id",
        "ai_backtests", "strategies", ["strategy_id"], ["id"],
    )

    # ai_backtest_trades
    op.create_table(
        "ai_backtest_trades",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("backtest_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("index", sa.Integer(), nullable=False),
        sa.Column("direction", sa.String(10), nullable=False),
        sa.Column("entry_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("entry_price", sa.Numeric(precision=20, scale=4), nullable=False),
        sa.Column("quantity", sa.Numeric(precision=20, scale=8), nullable=False),
        sa.Column("open_ai_analysis", sa.Text(), nullable=True),
        sa.Column("open_reason", sa.Text(), nullable=True),
        sa.Column("open_confidence", sa.Integer(), nullable=True),
        sa.Column("stop_loss", sa.Numeric(precision=20, scale=4), nullable=True),
        sa.Column("take_profit", sa.Numeric(precision=20, scale=4), nullable=True),
        sa.Column("exit_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("exit_price", sa.Numeric(precision=20, scale=4), nullable=True),
        sa.Column("exit_reason", sa.Text(), nullable=True),
        sa.Column("exit_ai_analysis", sa.Text(), nullable=True),
        sa.Column("exit_confidence", sa.Integer(), nullable=True),
        sa.Column("holding_bars", sa.Integer(), nullable=True),
        sa.Column("pnl", sa.Numeric(precision=20, scale=2), nullable=True),
        sa.Column("pnl_pct", sa.Numeric(precision=10, scale=4), nullable=True),
        sa.Column("fee", sa.Numeric(precision=20, scale=4), nullable=True),
        sa.Column("extra", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_ai_backtest_trades_backtest_id_index",
        "ai_backtest_trades", ["backtest_id", "index"],
    )
    op.create_foreign_key(
        "fk_ai_backtest_trades_backtest_id",
        "ai_backtest_trades", "ai_backtests", ["backtest_id"], ["id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    op.drop_index("ix_ai_backtest_trades_backtest_id_index")
    op.drop_table("ai_backtest_trades")
    op.drop_index("ix_ai_backtests_user_id_created_at")
    op.drop_table("ai_backtests")