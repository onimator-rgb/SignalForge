"""Add scoring_version to recommendations for calibration tracking.

Revision ID: 0010
Revises: 0009
Create Date: 2026-03-28
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0010"
down_revision: Union[str, None] = "0009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "recommendations",
        sa.Column("scoring_version", sa.String(10), nullable=True),
    )
    # Backfill existing recs as v1
    op.execute("UPDATE recommendations SET scoring_version = 'v1' WHERE scoring_version IS NULL")


def downgrade() -> None:
    op.drop_column("recommendations", "scoring_version")
