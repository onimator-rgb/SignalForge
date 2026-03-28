"""Pydantic schemas for alerts API."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class CreateAlertRuleRequest(BaseModel):
    asset_id: UUID | None = None
    name: str
    rule_type: str  # price_above, price_below, anomaly_detected, anomaly_severity_min
    condition: dict  # {"threshold": 100000} or {"severity_min": "high"}
    cooldown_minutes: int = 60
    is_active: bool = True


class UpdateAlertRuleRequest(BaseModel):
    name: str | None = None
    condition: dict | None = None
    cooldown_minutes: int | None = None
    is_active: bool | None = None


class AlertRuleOut(BaseModel):
    id: UUID
    asset_id: UUID | None
    asset_symbol: str | None = None
    name: str
    rule_type: str
    condition: dict
    cooldown_minutes: int
    is_active: bool
    last_triggered_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AlertEventOut(BaseModel):
    id: UUID
    alert_rule_id: UUID
    rule_name: str | None = None
    anomaly_event_id: UUID | None
    asset_id: UUID | None
    asset_symbol: str | None = None
    triggered_at: datetime
    message: str
    details: dict
    is_read: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class AlertStatsOut(BaseModel):
    total_events: int
    unread_events: int
    active_rules: int
    total_rules: int
