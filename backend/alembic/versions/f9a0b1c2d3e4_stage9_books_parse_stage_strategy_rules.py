"""stage9_books_parse_stage_strategy_rules

Revision ID: f9a0b1c2d3e4
Revises: f8a9b0c1d2e3
Create Date: 2026-08-14 16:30:00.000000+00:00

Stage 9 新增：
- books 表新增 parse_stage / parse_stage_progress / parse_stage_description /
  parse_error_message / parsed_chapters / parsed_chunks 字段
- strategies 表新增 source_book_id 索引
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "f9a0b1c2d3e4"
down_revision = "f8a9b0c1d2e3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. books 表新增解析阶段字段
    op.add_column(
        "books",
        sa.Column("parse_stage", sa.String(30), nullable=True),
    )
    op.add_column(
        "books",
        sa.Column("parse_stage_progress", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column(
        "books",
        sa.Column("parse_stage_description", sa.String(200), nullable=True),
    )
    op.add_column(
        "books",
        sa.Column("parse_error_message", sa.Text(), nullable=True),
    )
    op.add_column(
        "books",
        sa.Column("parsed_chapters", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column(
        "books",
        sa.Column("parsed_chunks", sa.Integer(), server_default="0", nullable=False),
    )

    # 2. strategies 表新增 source_book_id 索引
    op.create_index(
        op.f("ix_strategies_source_book_id"),
        "strategies",
        ["source_book_id"],
    )


def downgrade() -> None:
    # 1. 删除索引
    op.drop_index(op.f("ix_strategies_source_book_id"), table_name="strategies")

    # 2. 删除 books 表字段
    op.drop_column("books", "parsed_chunks")
    op.drop_column("books", "parsed_chapters")
    op.drop_column("books", "parse_error_message")
    op.drop_column("books", "parse_stage_description")
    op.drop_column("books", "parse_stage_progress")
    op.drop_column("books", "parse_stage")