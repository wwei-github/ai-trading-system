"""add use_precheck column to ai_backtests

Revision ID: f9a0b1c2d3f1
Revises: f9a0b1c2d3f0
Create Date: 2026-08-18 18:00:00.000000+00:00

为 AI 回测增加预筛开关字段，关闭后每根 K 线直接深度分析。
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "f9a0b1c2d3f1"
down_revision: Union[str, None] = "f9a0b1c2d3f0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """添加 use_precheck 列，默认 True"""
    op.add_column(
        "ai_backtests",
        sa.Column(
            "use_precheck",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
            comment="是否启用预筛（关闭后每根 K 线都直接深度分析）",
        ),
    )


def downgrade() -> None:
    """回滚：删除 use_precheck 列"""
    op.drop_column("ai_backtests", "use_precheck")