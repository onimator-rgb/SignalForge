"""Tests for the signal-to-strategy mapper."""

from app.signals.mapper import (
    MappedAction,
    SignalInput,
    filter_rules_by_signal,
    map_signal_to_action,
)
from app.strategies.models import StrategyAction, StrategyRule


def _make_rule(
    action: str = "buy", weight: float = 1.0, description: str = "", name: str = ""
) -> StrategyRule:
    return StrategyRule(
        name=name,
        description=description,
        action=StrategyAction(action=action, weight=weight),
    )


# --- filter_rules_by_signal tests ---


def test_filter_rules_by_signal_buy() -> None:
    rules = [_make_rule("buy"), _make_rule("buy"), _make_rule("sell")]
    result = filter_rules_by_signal(rules, "buy")
    assert len(result) == 2
    assert all(r.action.action == "buy" for r in result)


def test_filter_rules_by_signal_sell() -> None:
    rules = [_make_rule("buy"), _make_rule("buy"), _make_rule("sell")]
    result = filter_rules_by_signal(rules, "sell")
    assert len(result) == 1
    assert result[0].action.action == "sell"


def test_filter_rules_no_match() -> None:
    rules = [_make_rule("hold"), _make_rule("hold")]
    result = filter_rules_by_signal(rules, "buy")
    assert result == []


# --- map_signal_to_action tests ---


def test_map_signal_matching_rules() -> None:
    signal = SignalInput(symbol="AAPL", action="buy", confidence=0.8, source="webhook")
    rules = [_make_rule("buy", weight=1.0), _make_rule("buy", weight=0.5)]
    result = map_signal_to_action(signal, rules)

    assert result.action == "buy"
    # score = mean(1.0*0.8, 0.5*0.8) = mean(0.8, 0.4) = 0.6
    assert abs(result.score - 0.6) < 1e-9
    assert result.symbol == "AAPL"
    assert result.signal_source == "webhook"
    assert result.confidence == 0.8


def test_map_signal_no_matching_rules() -> None:
    signal = SignalInput(symbol="TSLA", action="sell", confidence=0.9, source="alert")
    rules = [_make_rule("buy"), _make_rule("buy")]
    result = map_signal_to_action(signal, rules)

    assert result.action == "hold"
    assert result.score == 0.0
    assert result.matched_rules == []
    assert result.symbol == "TSLA"
    assert result.signal_source == "alert"


def test_map_signal_confidence_weighting() -> None:
    rules = [_make_rule("buy", weight=1.0)]

    high = SignalInput(symbol="BTC", action="buy", confidence=0.9, source="s")
    low = SignalInput(symbol="BTC", action="buy", confidence=0.2, source="s")

    high_result = map_signal_to_action(high, rules)
    low_result = map_signal_to_action(low, rules)

    assert high_result.score > low_result.score
    assert high_result.score == 0.9
    assert low_result.score == 0.2


def test_map_signal_score_capped_at_one() -> None:
    signal = SignalInput(symbol="ETH", action="buy", confidence=1.0, source="s")
    rules = [_make_rule("buy", weight=2.0), _make_rule("buy", weight=3.0)]
    result = map_signal_to_action(signal, rules)

    # raw = mean(2.0*1.0, 3.0*1.0) = 2.5, capped at 1.0
    assert result.score == 1.0


def test_map_signal_rule_descriptions() -> None:
    signal = SignalInput(symbol="AAPL", action="buy", confidence=0.7, source="s")
    rules = [
        _make_rule("buy", description="Buy on momentum", name="r1"),
        _make_rule("buy", description="", name="r2"),
    ]
    result = map_signal_to_action(signal, rules)

    assert result.matched_rules == ["Buy on momentum", "Rule r2"]
