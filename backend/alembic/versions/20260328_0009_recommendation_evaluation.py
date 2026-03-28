"""Add forward-return evaluation columns to recommendations.

Revision ID: 0009
Revises: 0008
Create Date: 2026-03-28
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0009"
down_revision: Union[str, None] = "0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("recommendations", sa.Column("price_after_24h", sa.Numeric(24, 8), nullable=True))
    op.add_column("recommendations", sa.Column("price_after_72h", sa.Numeric(24, 8), nullable=True))
    op.add_column("recommendations", sa.Column("return_24h_pct", sa.Numeric(8, 4), nullable=True))
    op.add_column("recommendations", sa.Column("return_72h_pct", sa.Numeric(8, 4), nullable=True))
    op.add_column("recommendations", sa.Column("evaluated_at_24h", sa.DateTime(timezone=True), nullable=True))
    op.add_column("recommendations", sa.Column("evaluated_at_72h", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("recommendations", "evaluated_at_72h")
    op.drop_column("recommendations", "evaluated_at_24h")
    op.drop_column("recommendations", "return_72h_pct")
    op.drop_column("recommendations", "return_24h_pct")
    op.drop_column("recommendations", "price_after_72h")
    op.drop_column("recommendations", "price_after_24h")
