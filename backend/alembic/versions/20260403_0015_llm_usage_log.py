"""Add llm_usage_log table for multi-provider cost tracking.

Revision ID: 0015
Revises: 0014
Create Date: 2026-04-03
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0015"
down_revision: Union[str, None] = "0014"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "llm_usage_log",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("provider", sa.String(50), nullable=False),
        sa.Column("model", sa.String(100), nullable=False),
        sa.Column("agent_name", sa.String(50), nullable=True),
        sa.Column("task_type", sa.String(50), nullable=True),
        sa.Column("input_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("output_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cost_usd", sa.Numeric(10, 6), nullable=False, server_default="0"),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("success", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index("idx_llm_usage_created", "llm_usage_log", ["created_at"])
    op.create_index("idx_llm_usage_agent", "llm_usage_log", ["agent_name"])
    op.create_index("idx_llm_usage_provider", "llm_usage_log", ["provider", "model"])


def downgrade() -> None:
    op.drop_index("idx_llm_usage_provider", table_name="llm_usage_log")
    op.drop_index("idx_llm_usage_agent", table_name="llm_usage_log")
    op.drop_index("idx_llm_usage_created", table_name="llm_usage_log")
    op.drop_table("llm_usage_log")
