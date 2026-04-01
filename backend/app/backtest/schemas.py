"""Pydantic schemas for the backtest API (marketpulse-task-2026-04-01-0001)."""

import uuid

from pydantic import BaseModel, Field


class BacktestRequest(BaseModel):
    asset_id: uuid.UUID
    interval: str = Field(default="1h")
    lookback_days: int = Field(default=30)
    profile_name: str = Field(default="balanced")


class TradeOut(BaseModel):
    entry_index: int
    exit_index: int
    entry_price: float
    exit_price: float
    side: str
    quantity: float
    pnl: float
    pnl_pct: float
    exit_reason: str


class BacktestResponse(BaseModel):
    total_return: float
    total_return_pct: float
    max_drawdown_pct: float
    sharpe_ratio: float
    win_rate: float
    profit_factor: float
    total_trades: int
    avg_trade_pnl_pct: float
    best_trade_pnl_pct: float
    worst_trade_pnl_pct: float
    trades: list[TradeOut]
