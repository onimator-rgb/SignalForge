"""Signal-to-strategy mapper.

Maps external signals to strategy rule actions, producing a scored
action recommendation based on matching rules and signal confidence.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from app.strategies.models import StrategyRule


class SignalInput(BaseModel):
    """Lightweight signal representation compatible with StoredSignal."""

    symbol: str
    action: Literal["buy", "sell"]
    confidence: float = Field(ge=0.0, le=1.0)
    source: str


class MappedAction(BaseModel):
    """Result of mapping a signal through strategy rules."""

    action: Literal["buy", "sell", "hold"]
    score: float
    matched_rules: list[str]
    signal_source: str
    symbol: str
    confidence: float


def filter_rules_by_signal(
    rules: list[StrategyRule], signal_action: str
) -> list[StrategyRule]:
    """Return only rules whose action matches *signal_action*."""
    return [r for r in rules if r.action.action == signal_action]


def map_signal_to_action(
    signal: SignalInput, rules: list[StrategyRule]
) -> MappedAction:
    """Map a signal to an action recommendation using strategy rules.

    1. Filter rules matching the signal's action.
    2. Compute a composite score = mean(rule.weight * signal.confidence), capped at 1.0.
    3. Return the top action with matched-rule descriptions.
    """
    matched = filter_rules_by_signal(rules, signal.action)

    if not matched:
        return MappedAction(
            action="hold",
            score=0.0,
            matched_rules=[],
            signal_source=signal.source,
            symbol=signal.symbol,
            confidence=signal.confidence,
        )

    raw_score = sum(r.action.weight * signal.confidence for r in matched) / len(
        matched
    )
    score = min(raw_score, 1.0)

    descriptions = [
        r.description if r.description else f"Rule {r.name}" for r in matched
    ]

    return MappedAction(
        action=signal.action,
        score=score,
        matched_rules=descriptions,
        signal_source=signal.source,
        symbol=signal.symbol,
        confidence=signal.confidence,
    )
