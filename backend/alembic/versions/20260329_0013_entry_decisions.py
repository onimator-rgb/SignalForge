"""Add portfolio_entry_decisions table.

Revision ID: 0013
Revises: 0012
Create Date: 2026-03-29
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0013"
down_revision: Union[str, None] = "0012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "portfolio_entry_decisions",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("asset_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("assets.id"), nullable=False),
        sa.Column("recommendation_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("status", sa.String(10), nullable=False),  # allowed, blocked
        sa.Column("stage", sa.String(20), nullable=False),    # protections, confirmations
        sa.Column("reason_codes", postgresql.JSONB(), nullable=True),
        sa.Column("reason_text", sa.Text(), nullable=True),
        sa.Column("context_data", postgresql.JSONB(), nullable=True),
        sa.Column("regime", sa.String(10), nullable=True),
        sa.Column("profile", sa.String(20), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_entry_decisions_created", "portfolio_entry_decisions", [sa.text("created_at DESC")])


def downgrade() -> None:
    op.drop_table("portfolio_entry_decisions")
