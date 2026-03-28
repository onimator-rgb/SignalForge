"""Pydantic schemas for recommendation endpoints."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class RecommendationOut(BaseModel):
    id: UUID
    asset_id: UUID
    asset_symbol: str | None = None
    asset_class: str | None = None
    generated_at: datetime
    recommendation_type: str
    score: float
    confidence: str
    risk_level: str
    rationale_summary: str
    signal_breakdown: dict
    entry_price_snapshot: float | None
    time_horizon: str
    valid_until: datetime | None
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}
