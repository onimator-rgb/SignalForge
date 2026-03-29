"""Add portfolio_protection_events table.

Revision ID: 0012
Revises: 0011
Create Date: 2026-03-29
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0012"
down_revision: Union[str, None] = "0011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "portfolio_protection_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("protection_type", sa.String(30), nullable=False),
        sa.Column("status", sa.String(10), nullable=False, server_default=sa.text("'active'")),
        sa.Column("asset_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("asset_class", sa.String(10), nullable=True),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("context_data", postgresql.JSONB(), nullable=True),
        sa.Column("triggered_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_protection_active", "portfolio_protection_events",
                     ["status", "protection_type"],
                     postgresql_where=sa.text("status = 'active'"))


def downgrade() -> None:
    op.drop_table("portfolio_protection_events")
