"""Pydantic models for strategy rules and conditions."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class StrategyCondition(BaseModel):
    """A single condition comparing an indicator value against a threshold."""

    indicator_name: str
    operator: Literal["gt", "gte", "lt", "lte", "eq", "between"]
    value: float
    value_upper: float | None = None


class StrategyRule(BaseModel):
    """A rule that fires when all its conditions are met."""

    conditions: list[StrategyCondition]
    action: Literal["buy", "sell", "hold"]
    weight: float = 1.0
    description: str = ""
