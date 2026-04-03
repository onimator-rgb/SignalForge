"""ORM models for AI Trader Arena."""

import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.models import UUIDPrimaryKeyMixin
from app.database import Base


class AITrader(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "ai_traders"

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    slug: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    personality: Mapped[str] = mapped_column(Text, nullable=False)
    llm_provider: Mapped[str] = mapped_column(String(50), nullable=False)
    llm_model: Mapped[str] = mapped_column(String(100), nullable=False)
    strategy_config: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    risk_params: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    portfolio_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("portfolios.id"), nullable=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    total_decisions: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    win_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    loss_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")


class AITraderDecision(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "ai_trader_decisions"

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )
    trader_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ai_traders.id"), nullable=False
    )
    asset_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("assets.id"), nullable=False
    )
    action: Mapped[str] = mapped_column(String(10), nullable=False)
    confidence: Mapped[float] = mapped_column(Numeric(4, 2), nullable=False)
    reasoning: Mapped[str] = mapped_column(Text, nullable=False)
    market_context: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    indicators_snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    position_size_pct: Mapped[float | None] = mapped_column(Numeric(6, 4), nullable=True)
    target_entry_price: Mapped[float | None] = mapped_column(Numeric(24, 8), nullable=True)
    stop_loss_price: Mapped[float | None] = mapped_column(Numeric(24, 8), nullable=True)
    take_profit_price: Mapped[float | None] = mapped_column(Numeric(24, 8), nullable=True)
    executed: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    execution_result: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    llm_model_used: Mapped[str | None] = mapped_column(String(100), nullable=True)
    llm_cost_usd: Mapped[float | None] = mapped_column(Numeric(10, 6), nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)


class AITraderSnapshot(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "ai_trader_snapshots"

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )
    trader_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ai_traders.id"), nullable=False
    )
    snapshot_date: Mapped[date] = mapped_column(Date, nullable=False)
    portfolio_value_usd: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    cash_usd: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    open_positions: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    total_return_pct: Mapped[float] = mapped_column(Numeric(8, 4), nullable=False, server_default="0")
    daily_return_pct: Mapped[float | None] = mapped_column(Numeric(8, 4), nullable=True)
    sharpe_ratio: Mapped[float | None] = mapped_column(Numeric(8, 4), nullable=True)
    max_drawdown_pct: Mapped[float | None] = mapped_column(Numeric(8, 4), nullable=True)
    win_rate: Mapped[float | None] = mapped_column(Numeric(6, 4), nullable=True)
    profit_factor: Mapped[float | None] = mapped_column(Numeric(8, 4), nullable=True)
    total_trades: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    details: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
