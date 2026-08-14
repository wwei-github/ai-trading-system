"""stage8_ai_system_reports_signals

Revision ID: f8a9b0c1d2e3
Revises: e7f8a9b0c1d2
Create Date: 2026-08-14 16:00:00.000000+00:00

Stage 8 新增：
- signals 表新增 source / status / context 字段
- ai_messages 表新增 feedback 字段
- reports 表：分析报告（日/周/月报）
- system_configs 表：系统配置 K/V 持久化
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "f8a9b0c1d2e3"
down_revision = "e7f8a9b0c1d2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. signals 表新增字段
    op.add_column(
        "signals",
        sa.Column(
            "source",
            sa.String(length=10),
            server_default="ai",
            nullable=False,
        ),
    )
    op.add_column(
        "signals",
        sa.Column(
            "status",
            sa.String(length=20),
            server_default="pending",
            nullable=False,
        ),
    )
    op.add_column(
        "signals",
        sa.Column("context", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )

    # 2. ai_messages 表新增 feedback 字段
    op.add_column(
        "ai_messages",
        sa.Column(
            "feedback",
            sa.String(length=10),
            server_default="none",
            nullable=False,
        ),
    )

    # 3. reports 表
    op.create_table(
        "reports",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("report_type", sa.String(length=20), nullable=False),
        sa.Column("period", sa.String(length=20), server_default="custom", nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("period_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("period_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("context", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_reports_user_id"),
        "reports",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_reports_report_type"),
        "reports",
        ["report_type", "period"],
        unique=False,
    )

    # 4. system_configs 表
    op.create_table(
        "system_configs",
        sa.Column("category", sa.String(length=50), nullable=False),
        sa.Column("key", sa.String(length=100), nullable=False),
        sa.Column("value", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("category", "key", name="uq_system_configs_category_key"),
    )
    op.create_index(
        op.f("ix_system_configs_category"),
        "system_configs",
        ["category"],
        unique=False,
    )


def downgrade() -> None:
    # 4. system_configs
    op.drop_index(op.f("ix_system_configs_category"), table_name="system_configs")
    op.drop_table("system_configs")

    # 3. reports
    op.drop_index(op.f("ix_reports_report_type"), table_name="reports")
    op.drop_index(op.f("ix_reports_user_id"), table_name="reports")
    op.drop_table("reports")

    # 2. ai_messages
    op.drop_column("ai_messages", "feedback")

    # 1. signals
    op.drop_column("signals", "context")
    op.drop_column("signals", "status")
    op.drop_column("signals", "source")
