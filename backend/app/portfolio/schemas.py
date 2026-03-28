"""Pydantic schemas for portfolio endpoints."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class PositionOut(BaseModel):
    id: UUID
    asset_id: UUID
    asset_symbol: str | None = None
    asset_class: str | None = None
    recommendation_id: UUID | None
    entry_price: float
    quantity: float
    entry_value_usd: float
    opened_at: datetime
    exit_price: float | None
    exit_value_usd: float | None
    closed_at: datetime | None
    close_reason: str | None
    realized_pnl_usd: float | None
    realized_pnl_pct: float | None
    stop_loss_price: float | None
    take_profit_price: float | None
    max_hold_until: datetime | None
    status: str
    # Live fields (computed for open positions)
    current_price: float | None = None
    current_value_usd: float | None = None
    unrealized_pnl_usd: float | None = None
    unrealized_pnl_pct: float | None = None


class TransactionOut(BaseModel):
    id: UUID
    tx_type: str
    asset_id: UUID
    asset_symbol: str | None = None
    price: float
    quantity: float
    value_usd: float
    executed_at: datetime


class PortfolioStatsOut(BaseModel):
    initial_capital: float
    current_cash: float
    equity: float
    total_return_pct: float
    open_positions: int
    closed_positions: int
    total_trades: int
    win_rate: float | None
    avg_return_pct: float | None
    best_trade_pct: float | None
    worst_trade_pct: float | None
    total_realized_pnl: float


class PortfolioSummaryOut(BaseModel):
    stats: PortfolioStatsOut
    open_positions: list[PositionOut]
    recent_closed: list[PositionOut]
    recent_transactions: list[TransactionOut]
