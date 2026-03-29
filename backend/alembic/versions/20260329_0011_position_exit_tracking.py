"""Add exit tracking fields to portfolio_positions.

Revision ID: 0011
Revises: 0010
Create Date: 2026-03-29
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0011"
down_revision: Union[str, None] = "0010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("portfolio_positions", sa.Column("peak_price", sa.Numeric(24, 8), nullable=True))
    op.add_column("portfolio_positions", sa.Column("peak_pnl_pct", sa.Numeric(8, 4), nullable=True))
    op.add_column("portfolio_positions", sa.Column("trailing_stop_price", sa.Numeric(24, 8), nullable=True))
    op.add_column("portfolio_positions", sa.Column("break_even_armed", sa.Boolean(), server_default=sa.text("false"), nullable=False))
    op.add_column("portfolio_positions", sa.Column("exit_context", postgresql.JSONB(), nullable=True))


def downgrade() -> None:
    op.drop_column("portfolio_positions", "exit_context")
    op.drop_column("portfolio_positions", "break_even_armed")
    op.drop_column("portfolio_positions", "trailing_stop_price")
    op.drop_column("portfolio_positions", "peak_pnl_pct")
    op.drop_column("portfolio_positions", "peak_price")
