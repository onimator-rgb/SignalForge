"""Add analysis_reports table.

Revision ID: 0002
Revises: 0001
Create Date: 2026-03-28
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "analysis_reports",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("report_type", sa.String(30), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default=sa.text("'pending'")),
        sa.Column(
            "asset_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("assets.id"), nullable=True,
        ),
        sa.Column(
            "anomaly_event_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("anomaly_events.id"), nullable=True,
        ),
        sa.Column("title", sa.String(300), nullable=True),
        sa.Column("content_md", sa.Text(), nullable=True),
        sa.Column("llm_provider", sa.String(30), nullable=True),
        sa.Column("llm_model", sa.String(50), nullable=True),
        sa.Column("prompt_version", sa.String(20), nullable=True),
        sa.Column("token_usage", postgresql.JSONB(), nullable=True),
        sa.Column("context_data", postgresql.JSONB(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.text("now()"), nullable=False,
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True),
            server_default=sa.text("now()"), nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_report_type_created", "analysis_reports", ["report_type", "created_at"])
    op.create_index("idx_report_status", "analysis_reports", ["status"])


def downgrade() -> None:
    op.drop_table("analysis_reports")
