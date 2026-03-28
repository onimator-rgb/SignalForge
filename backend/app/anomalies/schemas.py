"""Pydantic schemas for anomaly endpoints."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class AnomalyEventOut(BaseModel):
    id: UUID
    asset_id: UUID
    asset_symbol: str | None = None
    detected_at: datetime
    anomaly_type: str
    severity: str
    score: float
    details: dict
    timeframe: str
    is_resolved: bool
    resolved_at: datetime | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class AnomalyStatsOut(BaseModel):
    total: int
    unresolved: int
    by_severity: dict[str, int]
    by_type: dict[str, int]
