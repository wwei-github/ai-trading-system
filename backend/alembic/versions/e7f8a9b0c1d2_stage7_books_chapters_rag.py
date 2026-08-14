"""stage7_books_chapters_rag

Revision ID: e7f8a9b0c1d2
Revises: d6e7f8a9b0c1
Create Date: 2026-08-14 15:00:00.000000+00:00

Stage 7 新增：
- books 表新增 parse_progress / total_chapters / total_chunks 字段
- book_chapters 表：书籍章节（标题/序号/正文/页码/层级）
- book_notes 表新增 chapter_order / note_type 字段
- knowledge_chunks 表新增 chapter_order 字段
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "e7f8a9b0c1d2"
down_revision = "d6e7f8a9b0c1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. books 表新增字段
    op.add_column(
        "books",
        sa.Column(
            "parse_progress",
            sa.Integer(),
            server_default="0",
            nullable=False,
        ),
    )
    op.add_column(
        "books",
        sa.Column(
            "total_chapters",
            sa.Integer(),
            server_default="0",
            nullable=False,
        ),
    )
    op.add_column(
        "books",
        sa.Column(
            "total_chunks",
            sa.Integer(),
            server_default="0",
            nullable=False,
        ),
    )

    # 2. book_chapters 表（章节管理）
    op.create_table(
        "book_chapters",
        sa.Column("book_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("chapter_order", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("page_start", sa.Integer(), nullable=True),
        sa.Column("page_end", sa.Integer(), nullable=True),
        sa.Column("char_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("level", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["book_id"], ["books.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_book_chapters_book_id"),
        "book_chapters",
        ["book_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_book_chapters_chapter_order"),
        "book_chapters",
        ["book_id", "chapter_order"],
        unique=False,
    )

    # 3. book_notes 表新增字段
    op.add_column(
        "book_notes",
        sa.Column("chapter_order", sa.Integer(), nullable=True),
    )
    op.add_column(
        "book_notes",
        sa.Column(
            "note_type",
            sa.String(length=20),
            server_default="note",
            nullable=False,
        ),
    )

    # 4. knowledge_chunks 表新增字段
    op.add_column(
        "knowledge_chunks",
        sa.Column("chapter_order", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    # 4. knowledge_chunks
    op.drop_column("knowledge_chunks", "chapter_order")

    # 3. book_notes
    op.drop_column("book_notes", "note_type")
    op.drop_column("book_notes", "chapter_order")

    # 2. book_chapters
    op.drop_index(op.f("ix_book_chapters_chapter_order"), table_name="book_chapters")
    op.drop_index(op.f("ix_book_chapters_book_id"), table_name="book_chapters")
    op.drop_table("book_chapters")

    # 1. books
    op.drop_column("books", "total_chunks")
    op.drop_column("books", "total_chapters")
    op.drop_column("books", "parse_progress")
