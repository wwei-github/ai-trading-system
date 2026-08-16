"""add prompt_template table and strategy.extra (08 doc)

Revision ID: f9a0b1c2d3f0
Revises: f9a0b1c2d3e9
Create Date: 2026-08-15 03:00:00.000000+00:00

为 08-AI回测K线分析优化 后端技术方案提供：
1. PromptTemplate 表（模板管理）
2. Strategy.extra 字段（融合优化辅助信息）
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "f9a0b1c2d3f0"
down_revision = "f9a0b1c2d3e9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. 创建 PromptTemplate 表
    op.create_table(
        "prompt_templates",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("category", sa.String(50), nullable=False, index=True,
                  comment="模板分类"),
        sa.Column("name", sa.String(200), nullable=False, comment="模板名称"),
        sa.Column("content", sa.Text(), nullable=False, comment="模板内容"),
        sa.Column("is_active", sa.Boolean(), nullable=False,
                  server_default=sa.text("true"), comment="是否启用"),
        sa.Column("version", sa.Integer(), nullable=False,
                  server_default=sa.text("1"), comment="版本号"),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), onupdate=sa.func.now(), nullable=True),
    )

    # 2. 给 Strategy 表添加 extra 字段
    op.add_column(
        "strategies",
        sa.Column(
            "extra",
            postgresql.JSONB(),
            nullable=True,
            comment="额外属性（用于辅助信息，如融合优化来源）",
        ),
    )


def downgrade() -> None:
    # 1. 删除 extra 字段
    op.drop_column("strategies", "extra")

    # 2. 删除 PromptTemplate 表
    op.drop_table("prompt_templates")