"""stage6_strategies_backtest_paper_live

Revision ID: d6e7f8a9b0c1
Revises: c5d6e7f8a9b0
Create Date: 2026-08-14 11:00:00.000000+00:00

Stage 6 新增：
- strategies 表新增 is_template 字段（内置模板策略标识）
- backtest_trades 表：回测交易明细（开平仓配对）
- paper_accounts 表：模拟交易虚拟账号
- paper_trades 表：模拟交易记录
- live_strategy_instances 表：实盘策略运行实例
- live_orders 表：实盘信号订单（半自动确认）
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "d6e7f8a9b0c1"
down_revision = "c5d6e7f8a9b0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. strategies 表新增 is_template 字段
    op.add_column(
        "strategies",
        sa.Column(
            "is_template",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
    )

    # 2. backtest_trades 表
    op.create_table(
        "backtest_trades",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("backtest_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("strategy_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("side", sa.String(length=10), nullable=False),
        sa.Column("entry_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("entry_price", sa.Float(), nullable=False),
        sa.Column("quantity", sa.Float(), nullable=False),
        sa.Column("exit_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("exit_price", sa.Float(), nullable=True),
        sa.Column("pnl", sa.Float(), nullable=False, server_default="0"),
        sa.Column("pnl_pct", sa.Float(), nullable=False, server_default="0"),
        sa.Column("holding_bars", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("exit_reason", sa.String(length=20), nullable=False, server_default="signal"),
        sa.Column("symbol", sa.String(length=30), nullable=False),
        sa.Column("extra", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["backtest_id"], ["backtests.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["strategy_id"], ["strategies.id"]),
    )
    op.create_index("ix_backtest_trades_backtest_id", "backtest_trades", ["backtest_id"])
    op.create_index("ix_backtest_trades_strategy_id", "backtest_trades", ["strategy_id"])

    # 3. paper_accounts 表
    op.create_table(
        "paper_accounts",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("strategy_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("symbol", sa.String(length=30), nullable=False),
        sa.Column("timeframe", sa.String(length=10), nullable=False, server_default="1h"),
        sa.Column("initial_capital", sa.Numeric(20, 2), nullable=False),
        sa.Column("current_equity", sa.Numeric(20, 2), nullable=False),
        sa.Column("available_cash", sa.Numeric(20, 2), nullable=False),
        sa.Column("position", sa.Float(), nullable=False, server_default="0"),
        sa.Column("avg_entry_price", sa.Float(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="running"),
        sa.Column("strategy_params", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("total_trades", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_pnl", sa.Numeric(20, 2), nullable=False, server_default="0"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("stopped_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["strategy_id"], ["strategies.id"]),
    )
    op.create_index("ix_paper_accounts_user_id", "paper_accounts", ["user_id"])
    op.create_index("ix_paper_accounts_strategy_id", "paper_accounts", ["strategy_id"])
    op.create_index("ix_paper_accounts_status", "paper_accounts", ["status"])

    # 4. paper_trades 表
    op.create_table(
        "paper_trades",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("paper_account_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("strategy_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("symbol", sa.String(length=30), nullable=False),
        sa.Column("side", sa.String(length=10), nullable=False),
        sa.Column("order_type", sa.String(length=20), nullable=False, server_default="market"),
        sa.Column("price", sa.Float(), nullable=False),
        sa.Column("quantity", sa.Float(), nullable=False),
        sa.Column("fee", sa.Float(), nullable=False, server_default="0"),
        sa.Column("executed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("signal_source", sa.String(length=100), nullable=True),
        sa.Column("realized_pnl", sa.Float(), nullable=True),
        sa.Column("extra", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["paper_account_id"], ["paper_accounts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["strategy_id"], ["strategies.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
    )
    op.create_index("ix_paper_trades_paper_account_id", "paper_trades", ["paper_account_id"])
    op.create_index("ix_paper_trades_user_id", "paper_trades", ["user_id"])
    op.create_index("ix_paper_trades_strategy_id", "paper_trades", ["strategy_id"])

    # 5. live_strategy_instances 表
    op.create_table(
        "live_strategy_instances",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("strategy_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("account_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("symbol", sa.String(length=30), nullable=False),
        sa.Column("timeframe", sa.String(length=10), nullable=False, server_default="1h"),
        sa.Column("mode", sa.String(length=20), nullable=False, server_default="semi_auto"),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="running"),
        sa.Column("risk_params", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("strategy_params", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("total_signals", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_executed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_rejected", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_pnl", sa.Numeric(20, 2), nullable=False, server_default="0"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("stopped_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("stop_reason", sa.String(length=200), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["strategy_id"], ["strategies.id"]),
        sa.ForeignKeyConstraint(["account_id"], ["exchange_accounts.id"]),
    )
    op.create_index("ix_live_strategy_instances_user_id", "live_strategy_instances", ["user_id"])
    op.create_index("ix_live_strategy_instances_strategy_id", "live_strategy_instances", ["strategy_id"])
    op.create_index("ix_live_strategy_instances_status", "live_strategy_instances", ["status"])

    # 6. live_orders 表
    op.create_table(
        "live_orders",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("instance_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("strategy_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("account_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("symbol", sa.String(length=30), nullable=False),
        sa.Column("side", sa.String(length=10), nullable=False),
        sa.Column("order_type", sa.String(length=20), nullable=False, server_default="market"),
        sa.Column("suggested_price", sa.Float(), nullable=True),
        sa.Column("suggested_amount", sa.Float(), nullable=False),
        sa.Column("signal_strength", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("signal_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("executed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("exchange_order_id", sa.String(length=100), nullable=True),
        sa.Column("executed_price", sa.Float(), nullable=True),
        sa.Column("executed_amount", sa.Float(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("risk_check_passed", sa.Boolean(), nullable=True),
        sa.Column("risk_reject_reason", sa.String(length=500), nullable=True),
        sa.Column("extra", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["instance_id"], ["live_strategy_instances.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["strategy_id"], ["strategies.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["account_id"], ["exchange_accounts.id"]),
    )
    op.create_index("ix_live_orders_instance_id", "live_orders", ["instance_id"])
    op.create_index("ix_live_orders_user_id", "live_orders", ["user_id"])
    op.create_index("ix_live_orders_status", "live_orders", ["status"])


def downgrade() -> None:
    op.drop_index("ix_live_orders_status", table_name="live_orders")
    op.drop_index("ix_live_orders_user_id", table_name="live_orders")
    op.drop_index("ix_live_orders_instance_id", table_name="live_orders")
    op.drop_table("live_orders")

    op.drop_index("ix_live_strategy_instances_status", table_name="live_strategy_instances")
    op.drop_index("ix_live_strategy_instances_strategy_id", table_name="live_strategy_instances")
    op.drop_index("ix_live_strategy_instances_user_id", table_name="live_strategy_instances")
    op.drop_table("live_strategy_instances")

    op.drop_index("ix_paper_trades_strategy_id", table_name="paper_trades")
    op.drop_index("ix_paper_trades_user_id", table_name="paper_trades")
    op.drop_index("ix_paper_trades_paper_account_id", table_name="paper_trades")
    op.drop_table("paper_trades")

    op.drop_index("ix_paper_accounts_status", table_name="paper_accounts")
    op.drop_index("ix_paper_accounts_strategy_id", table_name="paper_accounts")
    op.drop_index("ix_paper_accounts_user_id", table_name="paper_accounts")
    op.drop_table("paper_accounts")

    op.drop_index("ix_backtest_trades_strategy_id", table_name="backtest_trades")
    op.drop_index("ix_backtest_trades_backtest_id", table_name="backtest_trades")
    op.drop_table("backtest_trades")

    op.drop_column("strategies", "is_template")
