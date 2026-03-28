"""Add portfolios, portfolio_positions, portfolio_transactions tables.

Revision ID: 0008
Revises: 0007
Create Date: 2026-03-28
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0008"
down_revision: Union[str, None] = "0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "portfolios",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("name", sa.String(100), nullable=False, server_default=sa.text("'Demo Portfolio'")),
        sa.Column("initial_capital", sa.Numeric(12, 2), nullable=False, server_default=sa.text("1000.00")),
        sa.Column("current_cash", sa.Numeric(12, 2), nullable=False, server_default=sa.text("1000.00")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "portfolio_positions",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("portfolio_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("portfolios.id"), nullable=False),
        sa.Column("asset_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("assets.id"), nullable=False),
        sa.Column("recommendation_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("recommendations.id"), nullable=True),
        sa.Column("entry_price", sa.Numeric(24, 8), nullable=False),
        sa.Column("quantity", sa.Numeric(24, 8), nullable=False),
        sa.Column("entry_value_usd", sa.Numeric(12, 2), nullable=False),
        sa.Column("opened_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("exit_price", sa.Numeric(24, 8), nullable=True),
        sa.Column("exit_value_usd", sa.Numeric(12, 2), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("close_reason", sa.String(30), nullable=True),
        sa.Column("realized_pnl_usd", sa.Numeric(12, 2), nullable=True),
        sa.Column("realized_pnl_pct", sa.Numeric(8, 4), nullable=True),
        sa.Column("stop_loss_price", sa.Numeric(24, 8), nullable=True),
        sa.Column("take_profit_price", sa.Numeric(24, 8), nullable=True),
        sa.Column("max_hold_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(10), nullable=False, server_default=sa.text("'open'")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_pos_portfolio_open", "portfolio_positions", ["portfolio_id", "status"],
                     postgresql_where=sa.text("status = 'open'"))

    op.create_table(
        "portfolio_transactions",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("portfolio_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("portfolios.id"), nullable=False),
        sa.Column("position_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("portfolio_positions.id"), nullable=True),
        sa.Column("tx_type", sa.String(10), nullable=False),
        sa.Column("asset_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("assets.id"), nullable=False),
        sa.Column("price", sa.Numeric(24, 8), nullable=False),
        sa.Column("quantity", sa.Numeric(24, 8), nullable=False),
        sa.Column("value_usd", sa.Numeric(12, 2), nullable=False),
        sa.Column("executed_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("portfolio_transactions")
    op.drop_table("portfolio_positions")
    op.drop_table("portfolios")
