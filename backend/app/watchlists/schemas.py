"""Pydantic schemas for watchlist endpoints."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class CreateWatchlistRequest(BaseModel):
    name: str
    description: str | None = None


class UpdateWatchlistRequest(BaseModel):
    name: str | None = None
    description: str | None = None


class WatchlistOut(BaseModel):
    id: UUID
    name: str
    description: str | None
    asset_count: int = 0
    created_at: datetime
    updated_at: datetime


class AddAssetRequest(BaseModel):
    asset_id: UUID


class WatchlistAssetOut(BaseModel):
    asset_id: UUID
    symbol: str
    name: str
    asset_class: str
    image_url: str | None = None
    added_at: datetime
    # Enriched fields (lightweight integrations)
    latest_price: float | None = None
    change_24h_pct: float | None = None
    rec_type: str | None = None
    rec_score: float | None = None
    in_portfolio: bool = False
