"""Pydantic schemas for ingestion endpoints."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class TriggerIngestionRequest(BaseModel):
    interval: str = "1h"
    asset_class: str = "crypto"  # 'crypto' or 'stock'
    asset_symbols: list[str] | None = None  # None = all active assets of given class


class TriggerIngestionResponse(BaseModel):
    job_id: UUID
    status: str
    message: str


class IngestionJobOut(BaseModel):
    id: UUID
    provider: str
    job_type: str
    status: str
    assets_total: int
    assets_success: int
    assets_failed: int
    records_inserted: int
    error_summary: str | None
    started_at: datetime
    completed_at: datetime | None
    duration_ms: int | None

    model_config = {"from_attributes": True}


class SyncStateOut(BaseModel):
    id: UUID
    provider: str
    asset_id: UUID
    asset_symbol: str | None = None
    interval: str
    last_bar_time: datetime | None
    sync_status: str
    consecutive_errors: int
    last_error: str | None
    updated_at: datetime

    model_config = {"from_attributes": True}


class IngestionStatusResponse(BaseModel):
    recent_jobs: list[IngestionJobOut]
    sync_states: list[SyncStateOut]


class PriceBarOut(BaseModel):
    time: datetime
    asset_id: UUID
    interval: str
    open: float
    high: float
    low: float
    close: float
    volume: float

    model_config = {"from_attributes": True}
