"""Pydantic schemas for watchlist endpoints."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel


class CreateWatchlistRequest(BaseModel):
    name: str
    description: Optional[str] = None


class UpdateWatchlistRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None


class WatchlistOut(BaseModel):
    id: UUID
    name: str
    description: Optional[str]
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
    image_url: Optional[str] = None
    added_at: datetime
    # Enriched fields (lightweight integrations)
    latest_price: Optional[float] = None
    change_24h_pct: Optional[float] = None
    rec_type: Optional[str] = None
    rec_score: Optional[float] = None
    in_portfolio: bool = False
