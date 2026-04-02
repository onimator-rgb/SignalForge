"""Strategy rule data model – condition + action JSON schema (Pydantic v2)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field, computed_field, model_validator


# ---------------------------------------------------------------------------
# Primitives
# ---------------------------------------------------------------------------

IndicatorName = Literal[
    "rsi",
    "macd_histogram",
    "bollinger_pct_b",
    "price_change_pct",
    "volume_change_pct",
]

Operator = Literal["gt", "gte", "lt", "lte", "eq", "between"]

ActionType = Literal["buy", "sell", "hold"]


# ---------------------------------------------------------------------------
# Condition / Action / Rule
# ---------------------------------------------------------------------------


class StrategyCondition(BaseModel):
    """Single indicator condition (e.g. RSI > 70)."""

    indicator: IndicatorName
    operator: Operator
    value: float
    value_upper: float | None = None

    @model_validator(mode="after")
    def _between_needs_upper(self) -> StrategyCondition:
        if self.operator == "between" and self.value_upper is None:
            raise ValueError("value_upper is required when operator is 'between'")
        return self


class StrategyAction(BaseModel):
    """Action to take when a condition fires."""

    action: ActionType
    weight: float = Field(default=1.0, ge=0, le=2)
    params: dict[str, float] = Field(default_factory=dict)


class StrategyRule(BaseModel):
    """One or more conditions → action with weight."""

    conditions: list[StrategyCondition] = Field(min_length=1)
    action: ActionType = "buy"
    weight: float = Field(default=1.0, ge=0, le=2)
    description: str = ""


# ---------------------------------------------------------------------------
# Strategy aggregate
# ---------------------------------------------------------------------------


class Strategy(BaseModel):
    """A named collection of rules linked to a risk profile."""

    id: str = Field(default_factory=lambda: uuid4().hex)
    name: str = Field(min_length=1, max_length=100)
    description: str = ""
    rules: list[StrategyRule] = Field(min_length=1)
    profile_name: str = "balanced"
    is_preset: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @computed_field  # type: ignore[prop-decorator]
    @property
    def signal_actions(self) -> set[ActionType]:
        """Unique action types present in *rules*."""
        return {r.action for r in self.rules}


# ---------------------------------------------------------------------------
# In-memory store (single-process, no thread-safety needed)
# ---------------------------------------------------------------------------


class StrategyStore:
    """Simple dict-backed CRUD store for Strategy objects."""

    def __init__(self) -> None:
        self._store: dict[str, Strategy] = {}

    def add(self, strategy: Strategy) -> Strategy:
        self._store[strategy.id] = strategy
        return strategy

    def get(self, strategy_id: str) -> Strategy | None:
        return self._store.get(strategy_id)

    def list_all(self) -> list[Strategy]:
        return list(self._store.values())

    def delete(self, strategy_id: str) -> bool:
        return self._store.pop(strategy_id, None) is not None

    def clear(self) -> None:
        self._store.clear()
