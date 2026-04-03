"""Add AI trader arena tables — autonomous traders with independent portfolios.

Revision ID: 0016
Revises: 0015
Create Date: 2026-04-03
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0016"
down_revision: Union[str, None] = "0015"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # AI Traders — each is an autonomous trading personality
    op.create_table(
        "ai_traders",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("name", sa.String(100), nullable=False, unique=True),
        sa.Column("slug", sa.String(50), nullable=False, unique=True),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("personality", sa.Text(), nullable=False),          # system prompt / trading philosophy
        sa.Column("llm_provider", sa.String(50), nullable=False),     # gemini, groq, claude, etc.
        sa.Column("llm_model", sa.String(100), nullable=False),       # gemini-2.0-flash, etc.
        sa.Column("strategy_config", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("risk_params", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("portfolio_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("portfolios.id"), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("total_decisions", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("win_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("loss_count", sa.Integer(), nullable=False, server_default="0"),
        sa.PrimaryKeyConstraint("id"),
    )

    # Trader Decisions — every buy/sell/hold decision with reasoning
    op.create_table(
        "ai_trader_decisions",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("trader_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("ai_traders.id"), nullable=False),
        sa.Column("asset_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("assets.id"), nullable=False),
        sa.Column("action", sa.String(10), nullable=False),           # buy, sell, hold, skip
        sa.Column("confidence", sa.Numeric(4, 2), nullable=False),    # 0.00 - 1.00
        sa.Column("reasoning", sa.Text(), nullable=False),            # LLM-generated explanation
        sa.Column("market_context", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("indicators_snapshot", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("position_size_pct", sa.Numeric(6, 4), nullable=True),
        sa.Column("target_entry_price", sa.Numeric(24, 8), nullable=True),
        sa.Column("stop_loss_price", sa.Numeric(24, 8), nullable=True),
        sa.Column("take_profit_price", sa.Numeric(24, 8), nullable=True),
        sa.Column("executed", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("execution_result", postgresql.JSONB(), nullable=True),
        sa.Column("llm_model_used", sa.String(100), nullable=True),
        sa.Column("llm_cost_usd", sa.Numeric(10, 6), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index("idx_trader_decisions_trader", "ai_trader_decisions", ["trader_id", "created_at"])
    op.create_index("idx_trader_decisions_asset", "ai_trader_decisions", ["asset_id", "created_at"])

    # Trader Performance Snapshots — daily/periodic performance capture
    op.create_table(
        "ai_trader_snapshots",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("trader_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("ai_traders.id"), nullable=False),
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column("portfolio_value_usd", sa.Numeric(12, 2), nullable=False),
        sa.Column("cash_usd", sa.Numeric(12, 2), nullable=False),
        sa.Column("open_positions", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_return_pct", sa.Numeric(8, 4), nullable=False, server_default="0"),
        sa.Column("daily_return_pct", sa.Numeric(8, 4), nullable=True),
        sa.Column("sharpe_ratio", sa.Numeric(8, 4), nullable=True),
        sa.Column("max_drawdown_pct", sa.Numeric(8, 4), nullable=True),
        sa.Column("win_rate", sa.Numeric(6, 4), nullable=True),
        sa.Column("profit_factor", sa.Numeric(8, 4), nullable=True),
        sa.Column("total_trades", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("details", postgresql.JSONB(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("trader_id", "snapshot_date", name="uq_trader_snapshot_date"),
    )

    op.create_index("idx_trader_snapshots_trader", "ai_trader_snapshots", ["trader_id", "snapshot_date"])


def downgrade() -> None:
    op.drop_index("idx_trader_snapshots_trader", table_name="ai_trader_snapshots")
    op.drop_table("ai_trader_snapshots")
    op.drop_index("idx_trader_decisions_asset", table_name="ai_trader_decisions")
    op.drop_index("idx_trader_decisions_trader", table_name="ai_trader_decisions")
    op.drop_table("ai_trader_decisions")
    op.drop_table("ai_traders")
