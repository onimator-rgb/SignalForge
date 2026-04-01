"""Strategy domain models used by the signal mapper and future strategy engine."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class StrategyCondition(BaseModel):
    """A single condition that must be met for a rule to fire."""

    indicator: str = ""
    operator: Literal["gt", "lt", "eq", "gte", "lte"] = "gt"
    value: float = 0.0


class StrategyAction(BaseModel):
    """The action a strategy rule recommends."""

    action: Literal["buy", "sell", "hold"] = "hold"
    weight: float = Field(default=1.0, ge=0.0)


class StrategyRule(BaseModel):
    """A single rule mapping conditions to an action."""

    name: str = ""
    description: str = ""
    conditions: list[StrategyCondition] = Field(default_factory=list)
    action: StrategyAction = Field(default_factory=StrategyAction)
