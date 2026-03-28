"""Pydantic schemas for report endpoints."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class GenerateReportRequest(BaseModel):
    report_type: str  # 'asset_brief', 'anomaly_explanation', 'market_summary'
    asset_id: UUID | None = None
    anomaly_event_id: UUID | None = None


class ReportOut(BaseModel):
    id: UUID
    report_type: str
    status: str
    asset_id: UUID | None
    anomaly_event_id: UUID | None
    title: str | None
    content_md: str | None
    llm_provider: str | None
    llm_model: str | None
    prompt_version: str | None
    token_usage: dict | None
    error_message: str | None
    created_at: datetime
    completed_at: datetime | None

    model_config = {"from_attributes": True}


class ReportStatusOut(BaseModel):
    id: UUID
    status: str
    report_type: str
    created_at: datetime
    completed_at: datetime | None
