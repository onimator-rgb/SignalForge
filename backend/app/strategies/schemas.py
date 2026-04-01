"""Pydantic models for the preset strategies API."""

from __future__ import annotations

from pydantic import BaseModel


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
