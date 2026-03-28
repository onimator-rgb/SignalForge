"""Pydantic schemas for asset endpoints."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from app.indicators.schemas import BollingerOut, MACDOut


class LatestPrice(BaseModel):
    close: float
    bar_time: datetime
    change_24h_pct: float | None = None  # None if insufficient history


class AssetIndicatorsSummary(BaseModel):
    interval: str
    bar_time: datetime
    rsi_14: float | None = None
    macd: MACDOut | None = None
    bollinger: BollingerOut | None = None


class AssetListItem(BaseModel):
    id: UUID
    symbol: str
    name: str
    market_cap_rank: int | None
    is_active: bool
    image_url: str | None = None
    latest_price: LatestPrice | None = None
    unresolved_anomalies: int = 0


class AssetDetail(BaseModel):
    id: UUID
    symbol: str
    name: str
    binance_symbol: str
    coingecko_id: str | None
    market_cap_rank: int | None
    is_active: bool
    image_url: str | None = None
    metadata: dict
    latest_price: LatestPrice | None = None
    indicators: AssetIndicatorsSummary | None = None
    unresolved_anomalies: int = 0
    created_at: datetime
    updated_at: datetime


class AssetSearchResult(BaseModel):
    id: UUID
    symbol: str
    name: str
    market_cap_rank: int | None
    image_url: str | None = None
