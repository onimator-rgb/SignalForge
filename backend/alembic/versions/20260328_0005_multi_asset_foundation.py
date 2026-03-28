"""Multi-asset foundation: rename binance_symbol → provider_symbol,
add asset_class, exchange, currency.

Revision ID: 0005
Revises: 0004
Create Date: 2026-03-28
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Rename binance_symbol → provider_symbol
    op.alter_column("assets", "binance_symbol", new_column_name="provider_symbol")

    # Add multi-asset columns with safe defaults
    op.add_column(
        "assets",
        sa.Column("asset_class", sa.String(10), nullable=False, server_default=sa.text("'crypto'")),
    )
    op.add_column(
        "assets",
        sa.Column("exchange", sa.String(20), nullable=True),
    )
    op.add_column(
        "assets",
        sa.Column("currency", sa.String(5), nullable=False, server_default=sa.text("'USD'")),
    )

    # Index for asset_class filtering
    op.create_index("idx_assets_class", "assets", ["asset_class", "is_active"])


def downgrade() -> None:
    op.drop_index("idx_assets_class", table_name="assets")
    op.drop_column("assets", "currency")
    op.drop_column("assets", "exchange")
    op.drop_column("assets", "asset_class")
    op.alter_column("assets", "provider_symbol", new_column_name="binance_symbol")
