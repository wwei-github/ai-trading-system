"""add error_logs table

Revision ID: f9a0b1c2d3e8
Revises: f9a0b1c2d3e7
Create Date: 2026-08-14 19:00:00.000000+00:00

新增 error_logs 表，用于集中存储系统错误日志。
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "f9a0b1c2d3e8"
down_revision = "f9a0b1c2d3e7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "error_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("request_id", sa.String(64), nullable=True),
        sa.Column("level", sa.String(10), nullable=False),
        sa.Column("module", sa.String(50), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("exception_type", sa.String(100), nullable=True),
        sa.Column("traceback", sa.Text(), nullable=True),
        sa.Column("request_path", sa.String(500), nullable=True),
        sa.Column("request_method", sa.String(10), nullable=True),
        sa.Column("request_params", postgresql.JSONB(), nullable=True),
        sa.Column("status_code", sa.Integer(), nullable=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("user_ip", sa.String(50), nullable=True),
        sa.Column("user_agent", sa.String(500), nullable=True),
        sa.Column("duration_ms", sa.Float(), nullable=True),
        sa.Column("detail", postgresql.JSONB(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_error_logs_level_created_at",
        "error_logs",
        ["level", sa.text("created_at DESC")],
    )
    op.create_index(
        "ix_error_logs_module_created_at",
        "error_logs",
        ["module", sa.text("created_at DESC")],
    )
    op.create_index(
        "ix_error_logs_request_id",
        "error_logs",
        ["request_id"],
    )
    op.create_index(
        "ix_error_logs_created_at",
        "error_logs",
        ["created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_error_logs_created_at")
    op.drop_index("ix_error_logs_request_id")
    op.drop_index("ix_error_logs_module_created_at")
    op.drop_index("ix_error_logs_level_created_at")
    op.drop_table("error_logs")