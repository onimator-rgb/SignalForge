"""Portfolio models — demo/paper trading."""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Numeric, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.models import UUIDPrimaryKeyMixin
from app.database import Base


class Portfolio(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "portfolios"

    name: Mapped[str] = mapped_column(String(100), nullable=False, default="Demo Portfolio")
    initial_capital: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, default=1000.00)
    current_cash: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, default=1000.00)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )


class PortfolioPosition(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "portfolio_positions"

    portfolio_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("portfolios.id"), nullable=False)
    asset_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("assets.id"), nullable=False)
    recommendation_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("recommendations.id"), nullable=True)
    entry_price: Mapped[float] = mapped_column(Numeric(24, 8), nullable=False)
    quantity: Mapped[float] = mapped_column(Numeric(24, 8), nullable=False)
    entry_value_usd: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"), nullable=False)
    exit_price: Mapped[float | None] = mapped_column(Numeric(24, 8), nullable=True)
    exit_value_usd: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    close_reason: Mapped[str | None] = mapped_column(String(30), nullable=True)
    realized_pnl_usd: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    realized_pnl_pct: Mapped[float | None] = mapped_column(Numeric(8, 4), nullable=True)
    stop_loss_price: Mapped[float | None] = mapped_column(Numeric(24, 8), nullable=True)
    take_profit_price: Mapped[float | None] = mapped_column(Numeric(24, 8), nullable=True)
    max_hold_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    peak_price: Mapped[float | None] = mapped_column(Numeric(24, 8), nullable=True)
    peak_pnl_pct: Mapped[float | None] = mapped_column(Numeric(8, 4), nullable=True)
    trailing_stop_price: Mapped[float | None] = mapped_column(Numeric(24, 8), nullable=True)
    break_even_armed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    exit_context: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    status: Mapped[str] = mapped_column(String(10), nullable=False, default="open")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"), nullable=False)


class ProtectionEvent(Base):
    __tablename__ = "portfolio_protection_events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    protection_type: Mapped[str] = mapped_column(String(30), nullable=False)
    status: Mapped[str] = mapped_column(String(10), nullable=False, default="active")
    asset_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    asset_class: Mapped[str | None] = mapped_column(String(10), nullable=True)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    context_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    triggered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"), nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"), nullable=False)


class PortfolioTransaction(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "portfolio_transactions"

    portfolio_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("portfolios.id"), nullable=False)
    position_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("portfolio_positions.id"), nullable=True)
    tx_type: Mapped[str] = mapped_column(String(10), nullable=False)  # buy, sell
    asset_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("assets.id"), nullable=False)
    price: Mapped[float] = mapped_column(Numeric(24, 8), nullable=False)
    quantity: Mapped[float] = mapped_column(Numeric(24, 8), nullable=False)
    value_usd: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    executed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"), nullable=False)
