"""Add recommendations table.

Revision ID: 0007
Revises: 0006
Create Date: 2026-03-28
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0007"
down_revision: Union[str, None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "recommendations",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("asset_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("assets.id"), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("recommendation_type", sa.String(30), nullable=False),
        sa.Column("score", sa.Numeric(5, 2), nullable=False),
        sa.Column("confidence", sa.String(10), nullable=False),
        sa.Column("risk_level", sa.String(10), nullable=False),
        sa.Column("rationale_summary", sa.Text(), nullable=False),
        sa.Column("signal_breakdown", postgresql.JSONB(), nullable=False),
        sa.Column("entry_price_snapshot", sa.Numeric(24, 8), nullable=True),
        sa.Column("time_horizon", sa.String(20), nullable=False, server_default=sa.text("'24h-72h'")),
        sa.Column("valid_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("invalidation_note", sa.Text(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default=sa.text("'active'")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_rec_asset_active", "recommendations", ["asset_id", "status"],
                     postgresql_where=sa.text("status = 'active'"))
    op.create_index("idx_rec_type_score", "recommendations", ["recommendation_type", sa.text("score DESC")])
    op.create_index("idx_rec_generated", "recommendations", [sa.text("generated_at DESC")])


def downgrade() -> None:
    op.drop_table("recommendations")
