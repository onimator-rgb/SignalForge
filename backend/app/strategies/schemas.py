"""Pydantic models for the preset strategies API."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class PresetParamSchema(BaseModel):
    """Describes a single parameter accepted by a preset generator."""

    name: str
    type: str  # "int" | "float"
    description: str
    default: float | None = None


class PresetInfo(BaseModel):
    """Descriptor returned by GET /presets."""

    preset_type: str
    display_name: str
    description: str
    params: list[PresetParamSchema]


class GenerateFromPresetRequest(BaseModel):
    """Body for POST /from-preset."""

    preset_type: str
    params: dict[str, float]


class GenerateFromPresetResponse(BaseModel):
    """Response for POST /from-preset."""

    preset_type: str
    rules: list[dict]  # type: ignore[type-arg]
    num_rules: int


# ---------------------------------------------------------------------------
# CRUD schemas
# ---------------------------------------------------------------------------


class CreateStrategyRequest(BaseModel):
    """Body for POST /api/v1/strategies."""

    name: str = Field(min_length=1, max_length=100)
    description: str = ""
    rules: list[dict] = Field(min_length=1)  # type: ignore[type-arg]
    profile_name: str = "balanced"


class StrategyResponse(BaseModel):
    """Single strategy in API responses."""

    id: str
    name: str
    description: str
    rules: list[dict]  # type: ignore[type-arg]
    profile_name: str
    is_preset: bool
    created_at: datetime
    num_rules: int


class StrategyListResponse(BaseModel):
    """Response for GET /api/v1/strategies."""

    strategies: list[StrategyResponse]
    count: int
