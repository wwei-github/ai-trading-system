"""add ai_backtest optimization fields (08 doc)

Revision ID: f9a0b1c2d3e9
Revises: f9a0b1c2d3e8
Create Date: 2026-08-15 02:00:00.000000+00:00

为 AI 回测添加 K 线分析优化相关字段（08-AI回测K线分析优化后端技术方案）。
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "f9a0b1c2d3e9"
down_revision = "f9a0b1c2d3e8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ========== ai_backtests 表新增字段 ==========

    # 多策略融合
    op.add_column(
        "ai_backtests",
        sa.Column(
            "parent_backtest_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("ai_backtests.id", ondelete="SET NULL"),
            nullable=True,
            comment="父回测 ID（多策略融合时使用）",
        ),
    )
    op.add_column(
        "ai_backtests",
        sa.Column(
            "strategy_ids",
            postgresql.JSONB(),
            nullable=True,
            comment="参与回测的策略 ID 列表",
        ),
    )
    op.create_index(
        "ix_ai_backtests_parent_backtest_id",
        "ai_backtests",
        ["parent_backtest_id"],
    )

    # 两级 AI 过滤统计
    op.add_column(
        "ai_backtests",
        sa.Column(
            "ai_call_count",
            sa.Integer(),
            nullable=True,
            server_default=sa.text("0"),
            comment="AI 调用总次数",
        ),
    )
    op.add_column(
        "ai_backtests",
        sa.Column(
            "precheck_total",
            sa.Integer(),
            nullable=True,
            server_default=sa.text("0"),
            comment="快速预筛总次数",
        ),
    )
    op.add_column(
        "ai_backtests",
        sa.Column(
            "precheck_triggered",
            sa.Integer(),
            nullable=True,
            server_default=sa.text("0"),
            comment="预筛触发 AI 分析次数",
        ),
    )

    # 本地模型预筛配置
    op.add_column(
        "ai_backtests",
        sa.Column(
            "use_local_model",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
            comment="使用本地模型进行预筛",
        ),
    )
    op.add_column(
        "ai_backtests",
        sa.Column(
            "local_model_klines",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("10"),
            comment="本地模型分析的 K 线数量",
        ),
    )

    # 初始化 300 根预热分析
    op.add_column(
        "ai_backtests",
        sa.Column(
            "initial_analysis",
            postgresql.JSONB(),
            nullable=True,
            comment="初始化 AI 分析结果（趋势、关键位、摘要）",
        ),
    )

    # 深度分析日志
    op.add_column(
        "ai_backtests",
        sa.Column(
            "ai_analysis_logs",
            postgresql.JSONB(),
            nullable=True,
            comment="深度分析日志列表（复盘用）",
        ),
    )

    # Prompt 模板 ID 映射
    op.add_column(
        "ai_backtests",
        sa.Column(
            "prompt_template_ids",
            postgresql.JSONB(),
            nullable=True,
            comment="使用的 Prompt 模板 ID 映射 {category: template_id}",
        ),
    )

    # ========== ai_backtest_trades 表新增字段 ==========
    op.add_column(
        "ai_backtest_trades",
        sa.Column(
            "ai_window_start",
            sa.Integer(),
            nullable=True,
            comment="AI 分析时 K 线窗口起始索引",
        ),
    )
    op.add_column(
        "ai_backtest_trades",
        sa.Column(
            "ai_window_end",
            sa.Integer(),
            nullable=True,
            comment="AI 分析时 K 线窗口结束索引",
        ),
    )
    op.add_column(
        "ai_backtest_trades",
        sa.Column(
            "trigger_reason",
            sa.String(100),
            nullable=True,
            comment="触发 AI 分析的原因（预筛命中规则）",
        ),
    )


def downgrade() -> None:
    # ai_backtest_trades 表
    op.drop_column("ai_backtest_trades", "trigger_reason")
    op.drop_column("ai_backtest_trades", "ai_window_end")
    op.drop_column("ai_backtest_trades", "ai_window_start")

    # ai_backtests 表
    op.drop_column("ai_backtests", "prompt_template_ids")
    op.drop_column("ai_backtests", "ai_analysis_logs")
    op.drop_column("ai_backtests", "initial_analysis")
    op.drop_column("ai_backtests", "local_model_klines")
    op.drop_column("ai_backtests", "use_local_model")
    op.drop_column("ai_backtests", "precheck_triggered")
    op.drop_column("ai_backtests", "precheck_total")
    op.drop_column("ai_backtests", "ai_call_count")
    op.drop_index(
        "ix_ai_backtests_parent_backtest_id", table_name="ai_backtests"
    )
    op.drop_column("ai_backtests", "strategy_ids")
    op.drop_column("ai_backtests", "parent_backtest_id")