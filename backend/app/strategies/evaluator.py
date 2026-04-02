"""Strategy rule evaluator — pure-logic functions for evaluating indicator conditions.

Takes a list of StrategyRule objects and an indicator dict, evaluates each rule's
conditions against indicator values, and returns a composite signal with weighted score.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from app.strategies.models import StrategyCondition, StrategyRule


class EvaluationResult(BaseModel):
    """Result of evaluating a set of strategy rules against indicator data."""

    signal: Literal["buy", "sell", "hold"]
    score: float
    matched_rules: list[str]
    total_rules: int
    skipped_rules: int


def extract_indicator_value(indicator_name: str, indicators: dict) -> float | None:
    """Map an indicator name to a value from the indicators dict.

    Returns None if the key is missing or the value is None.
    """
    try:
        if indicator_name == "rsi":
            val = indicators.get("rsi_14")
            return float(val) if val is not None else None

        if indicator_name == "macd_histogram":
            macd = indicators.get("macd")
            if macd is None:
                return None
            val = macd.get("histogram") if isinstance(macd, dict) else None
            return float(val) if val is not None else None

        if indicator_name == "bollinger_pct_b":
            bollinger = indicators.get("bollinger")
            close = indicators.get("close")
            if bollinger is None or close is None:
                return None
            lower = bollinger.get("lower") if isinstance(bollinger, dict) else None
            upper = bollinger.get("upper") if isinstance(bollinger, dict) else None
            if lower is None or upper is None:
                return None
            lower_f = float(lower)
            upper_f = float(upper)
            if upper_f == lower_f:
                return None
            return (float(close) - lower_f) / (upper_f - lower_f)

        if indicator_name == "price_change_pct":
            val = indicators.get("price_change_pct")
            return float(val) if val is not None else None

        if indicator_name == "volume_change_pct":
            val = indicators.get("volume_change_pct")
            return float(val) if val is not None else None

    except (TypeError, ValueError, KeyError):
        return None

    return None


def check_condition(condition: StrategyCondition, indicators: dict) -> bool | None:
    """Check a single condition against indicator data.

    Returns True/False for the comparison, or None if the indicator value
    is unavailable.
    """
    value = extract_indicator_value(condition.indicator_name, indicators)
    if value is None:
        return None

    op = condition.operator
    threshold = condition.value

    if op == "gt":
        return value > threshold
    if op == "gte":
        return value >= threshold
    if op == "lt":
        return value < threshold
    if op == "lte":
        return value <= threshold
    if op == "eq":
        return abs(value - threshold) < 1e-9
    if op == "between":
        upper = condition.value_upper
        if upper is None:
            return None
        return threshold <= value <= upper

    return None


def evaluate_rules(
    rules: list[StrategyRule],
    indicators: dict,
) -> EvaluationResult:
    """Evaluate a list of strategy rules against indicator data.

    For each rule whose conditions all pass, accumulate a weighted score:
    buy → +1 * weight, sell → -1 * weight, hold → 0.

    Returns an EvaluationResult with the composite signal, score, and metadata.
    """
    total_score = 0.0
    matched_rules: list[str] = []
    skipped = 0

    for rule in rules:
        rule_skipped = False
        all_conditions_met = True

        for condition in rule.conditions:
            result = check_condition(condition, indicators)
            if result is None:
                rule_skipped = True
                all_conditions_met = False
                break
            if not result:
                all_conditions_met = False
                break

        if rule_skipped:
            skipped += 1
            continue

        if all_conditions_met:
            matched_rules.append(rule.description)
            if rule.action == "buy":
                total_score += 1.0 * rule.weight
            elif rule.action == "sell":
                total_score += -1.0 * rule.weight
            # hold contributes 0

    # Clamp score to [-1.0, 1.0]
    clamped_score = max(-1.0, min(1.0, total_score))

    if clamped_score > 0:
        signal: Literal["buy", "sell", "hold"] = "buy"
    elif clamped_score < 0:
        signal = "sell"
    else:
        signal = "hold"

    return EvaluationResult(
        signal=signal,
        score=clamped_score,
        matched_rules=matched_rules,
        total_rules=len(rules),
        skipped_rules=skipped,
    )
