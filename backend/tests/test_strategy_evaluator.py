"""Tests for strategy rule evaluator — pure function tests."""

import pytest

from app.strategies.evaluator import (
    EvaluationResult,
    check_condition,
    evaluate_rules,
    extract_indicator_value,
)
from app.strategies.models import StrategyCondition, StrategyRule


# ── Fixtures ──────────────────────────────────────────


def _indicators(**overrides: object) -> dict:
    """Return a full indicator snapshot with optional overrides."""
    base: dict = {
        "rsi_14": 50.0,
        "macd": {"histogram": 0.5, "signal": 0.3, "macd": 0.8},
        "bollinger": {"lower": 90.0, "upper": 110.0, "middle": 100.0},
        "close": 100.0,
        "price_change_pct": 1.5,
        "volume_change_pct": 10.0,
    }
    base.update(overrides)
    return base


def _rule(
    indicator: str,
    operator: str,
    value: float,
    action: str = "buy",
    weight: float = 1.0,
    description: str = "",
    value_upper: float | None = None,
) -> StrategyRule:
    return StrategyRule(
        conditions=[
            StrategyCondition(
                indicator_name=indicator,
                operator=operator,  # type: ignore[arg-type]
                value=value,
                value_upper=value_upper,
            )
        ],
        action=action,  # type: ignore[arg-type]
        weight=weight,
        description=description,
    )


# ════════════════════════════════════════════════════════
# extract_indicator_value
# ════════════════════════════════════════════════════════


class TestExtractIndicatorValue:
    def test_rsi(self) -> None:
        assert extract_indicator_value("rsi", _indicators()) == 50.0

    def test_rsi_missing(self) -> None:
        assert extract_indicator_value("rsi", {}) is None

    def test_rsi_none_value(self) -> None:
        assert extract_indicator_value("rsi", {"rsi_14": None}) is None

    def test_macd_histogram(self) -> None:
        assert extract_indicator_value("macd_histogram", _indicators()) == 0.5

    def test_macd_histogram_missing_macd(self) -> None:
        assert extract_indicator_value("macd_histogram", {}) is None

    def test_macd_histogram_missing_key(self) -> None:
        assert extract_indicator_value("macd_histogram", {"macd": {}}) is None

    def test_bollinger_pct_b(self) -> None:
        # close=100, lower=90, upper=110 -> (100-90)/(110-90) = 0.5
        result = extract_indicator_value("bollinger_pct_b", _indicators())
        assert result == pytest.approx(0.5)

    def test_bollinger_pct_b_at_lower(self) -> None:
        ind = _indicators(close=90.0)
        result = extract_indicator_value("bollinger_pct_b", ind)
        assert result == pytest.approx(0.0)

    def test_bollinger_pct_b_at_upper(self) -> None:
        ind = _indicators(close=110.0)
        result = extract_indicator_value("bollinger_pct_b", ind)
        assert result == pytest.approx(1.0)

    def test_bollinger_pct_b_missing_bollinger(self) -> None:
        assert extract_indicator_value("bollinger_pct_b", {"close": 100.0}) is None

    def test_bollinger_pct_b_missing_close(self) -> None:
        ind = {"bollinger": {"lower": 90.0, "upper": 110.0}}
        assert extract_indicator_value("bollinger_pct_b", ind) is None

    def test_bollinger_pct_b_equal_bands(self) -> None:
        ind = _indicators()
        ind["bollinger"] = {"lower": 100.0, "upper": 100.0}
        assert extract_indicator_value("bollinger_pct_b", ind) is None

    def test_price_change_pct(self) -> None:
        assert extract_indicator_value("price_change_pct", _indicators()) == 1.5

    def test_volume_change_pct(self) -> None:
        assert extract_indicator_value("volume_change_pct", _indicators()) == 10.0

    def test_unknown_indicator(self) -> None:
        assert extract_indicator_value("unknown", _indicators()) is None


# ════════════════════════════════════════════════════════
# check_condition
# ════════════════════════════════════════════════════════


class TestCheckCondition:
    def test_gt_true(self) -> None:
        cond = StrategyCondition(indicator_name="rsi", operator="gt", value=30.0)
        assert check_condition(cond, _indicators(rsi_14=50.0)) is True

    def test_gt_false(self) -> None:
        cond = StrategyCondition(indicator_name="rsi", operator="gt", value=70.0)
        assert check_condition(cond, _indicators(rsi_14=50.0)) is False

    def test_gt_equal(self) -> None:
        cond = StrategyCondition(indicator_name="rsi", operator="gt", value=50.0)
        assert check_condition(cond, _indicators(rsi_14=50.0)) is False

    def test_gte_true(self) -> None:
        cond = StrategyCondition(indicator_name="rsi", operator="gte", value=50.0)
        assert check_condition(cond, _indicators(rsi_14=50.0)) is True

    def test_lt_true(self) -> None:
        cond = StrategyCondition(indicator_name="rsi", operator="lt", value=70.0)
        assert check_condition(cond, _indicators(rsi_14=50.0)) is True

    def test_lte_true(self) -> None:
        cond = StrategyCondition(indicator_name="rsi", operator="lte", value=50.0)
        assert check_condition(cond, _indicators(rsi_14=50.0)) is True

    def test_eq_exact(self) -> None:
        cond = StrategyCondition(indicator_name="rsi", operator="eq", value=50.0)
        assert check_condition(cond, _indicators(rsi_14=50.0)) is True

    def test_eq_within_tolerance(self) -> None:
        cond = StrategyCondition(indicator_name="rsi", operator="eq", value=50.0)
        assert check_condition(cond, _indicators(rsi_14=50.0 + 1e-10)) is True

    def test_eq_outside_tolerance(self) -> None:
        cond = StrategyCondition(indicator_name="rsi", operator="eq", value=50.0)
        assert check_condition(cond, _indicators(rsi_14=50.1)) is False

    def test_between_inside(self) -> None:
        cond = StrategyCondition(
            indicator_name="rsi", operator="between", value=30.0, value_upper=70.0
        )
        assert check_condition(cond, _indicators(rsi_14=50.0)) is True

    def test_between_at_lower_bound(self) -> None:
        cond = StrategyCondition(
            indicator_name="rsi", operator="between", value=50.0, value_upper=70.0
        )
        assert check_condition(cond, _indicators(rsi_14=50.0)) is True

    def test_between_at_upper_bound(self) -> None:
        cond = StrategyCondition(
            indicator_name="rsi", operator="between", value=30.0, value_upper=50.0
        )
        assert check_condition(cond, _indicators(rsi_14=50.0)) is True

    def test_between_outside(self) -> None:
        cond = StrategyCondition(
            indicator_name="rsi", operator="between", value=60.0, value_upper=70.0
        )
        assert check_condition(cond, _indicators(rsi_14=50.0)) is False

    def test_between_missing_upper(self) -> None:
        cond = StrategyCondition(
            indicator_name="rsi", operator="between", value=30.0
        )
        assert check_condition(cond, _indicators(rsi_14=50.0)) is None

    def test_missing_indicator(self) -> None:
        cond = StrategyCondition(indicator_name="rsi", operator="gt", value=30.0)
        assert check_condition(cond, {}) is None


# ════════════════════════════════════════════════════════
# evaluate_rules — signal generation
# ════════════════════════════════════════════════════════


class TestEvaluateRulesSignals:
    def test_rsi_above_70_triggers_sell(self) -> None:
        rules = [_rule("rsi", "gt", 70.0, action="sell", description="RSI overbought")]
        result = evaluate_rules(rules, _indicators(rsi_14=75.0))
        assert result.signal == "sell"
        assert result.score < 0
        assert "RSI overbought" in result.matched_rules

    def test_rsi_below_30_triggers_buy(self) -> None:
        rules = [_rule("rsi", "lt", 30.0, action="buy", description="RSI oversold")]
        result = evaluate_rules(rules, _indicators(rsi_14=25.0))
        assert result.signal == "buy"
        assert result.score > 0
        assert "RSI oversold" in result.matched_rules

    def test_macd_histogram_positive_buy(self) -> None:
        rules = [_rule("macd_histogram", "gt", 0.0, action="buy", description="MACD bullish")]
        ind = _indicators()
        ind["macd"]["histogram"] = 0.5
        result = evaluate_rules(rules, ind)
        assert result.signal == "buy"
        assert "MACD bullish" in result.matched_rules

    def test_macd_histogram_negative_sell(self) -> None:
        rules = [_rule("macd_histogram", "lt", 0.0, action="sell", description="MACD bearish")]
        ind = _indicators()
        ind["macd"]["histogram"] = -0.3
        result = evaluate_rules(rules, ind)
        assert result.signal == "sell"
        assert "MACD bearish" in result.matched_rules

    def test_bollinger_pct_b_below_threshold(self) -> None:
        rules = [_rule("bollinger_pct_b", "lt", 0.2, action="buy", description="Bollinger oversold")]
        # close=92 -> pct_b = (92-90)/(110-90) = 0.1
        result = evaluate_rules(rules, _indicators(close=92.0))
        assert result.signal == "buy"
        assert "Bollinger oversold" in result.matched_rules

    def test_bollinger_pct_b_above_threshold(self) -> None:
        rules = [_rule("bollinger_pct_b", "gt", 0.8, action="sell", description="Bollinger overbought")]
        # close=108 -> pct_b = (108-90)/(110-90) = 0.9
        result = evaluate_rules(rules, _indicators(close=108.0))
        assert result.signal == "sell"
        assert "Bollinger overbought" in result.matched_rules


class TestEvaluateRulesEdgeCases:
    def test_empty_rules_returns_hold(self) -> None:
        result = evaluate_rules([], _indicators())
        assert result.signal == "hold"
        assert result.score == 0.0
        assert result.matched_rules == []
        assert result.total_rules == 0
        assert result.skipped_rules == 0

    def test_all_rules_skipped_returns_hold(self) -> None:
        rules = [
            _rule("rsi", "gt", 70.0, action="sell", description="RSI overbought"),
            _rule("macd_histogram", "gt", 0.0, action="buy", description="MACD bullish"),
        ]
        result = evaluate_rules(rules, {})  # empty indicators
        assert result.signal == "hold"
        assert result.score == 0.0
        assert result.skipped_rules == 2
        assert result.total_rules == 2
        assert result.matched_rules == []

    def test_missing_indicator_skips_rule_no_crash(self) -> None:
        rules = [
            _rule("rsi", "gt", 70.0, action="sell", description="RSI overbought"),
            _rule("price_change_pct", "gt", 1.0, action="buy", description="Price up"),
        ]
        # Only price_change_pct available, rsi missing
        result = evaluate_rules(rules, {"price_change_pct": 2.0})
        assert result.signal == "buy"
        assert result.skipped_rules == 1
        assert result.total_rules == 2
        assert "Price up" in result.matched_rules

    def test_condition_not_met_does_not_match(self) -> None:
        rules = [_rule("rsi", "gt", 70.0, action="sell", description="RSI overbought")]
        result = evaluate_rules(rules, _indicators(rsi_14=50.0))
        assert result.signal == "hold"
        assert result.score == 0.0
        assert result.matched_rules == []

    def test_hold_action_contributes_zero(self) -> None:
        rules = [_rule("rsi", "gt", 30.0, action="hold", weight=5.0, description="Neutral")]
        result = evaluate_rules(rules, _indicators(rsi_14=50.0))
        assert result.signal == "hold"
        assert result.score == 0.0
        assert "Neutral" in result.matched_rules


class TestEvaluateRulesWeighting:
    def test_multiple_rules_weighted_buy(self) -> None:
        rules = [
            _rule("rsi", "lt", 30.0, action="buy", weight=0.6, description="RSI oversold"),
            _rule("macd_histogram", "gt", 0.0, action="buy", weight=0.3, description="MACD bullish"),
        ]
        ind = _indicators(rsi_14=25.0)
        ind["macd"]["histogram"] = 0.5
        result = evaluate_rules(rules, ind)
        assert result.signal == "buy"
        assert result.score == pytest.approx(0.9)
        assert len(result.matched_rules) == 2

    def test_mixed_signals_net_sell(self) -> None:
        rules = [
            _rule("rsi", "lt", 30.0, action="buy", weight=0.3, description="RSI oversold"),
            _rule("macd_histogram", "lt", 0.0, action="sell", weight=0.5, description="MACD bearish"),
        ]
        ind = _indicators(rsi_14=25.0)
        ind["macd"]["histogram"] = -0.3
        result = evaluate_rules(rules, ind)
        assert result.signal == "sell"
        assert result.score == pytest.approx(-0.2)

    def test_score_clamped_to_positive_one(self) -> None:
        rules = [
            _rule("rsi", "lt", 30.0, action="buy", weight=5.0, description="Heavy buy"),
            _rule("price_change_pct", "gt", 0.0, action="buy", weight=5.0, description="Price up"),
        ]
        result = evaluate_rules(rules, _indicators(rsi_14=25.0))
        assert result.score == 1.0

    def test_score_clamped_to_negative_one(self) -> None:
        rules = [
            _rule("rsi", "gt", 70.0, action="sell", weight=5.0, description="Heavy sell 1"),
            _rule("price_change_pct", "lt", 2.0, action="sell", weight=5.0, description="Heavy sell 2"),
        ]
        result = evaluate_rules(rules, _indicators(rsi_14=80.0))
        assert result.score == -1.0

    def test_opposing_rules_cancel_out(self) -> None:
        rules = [
            _rule("rsi", "lt", 60.0, action="buy", weight=1.0, description="Buy signal"),
            _rule("price_change_pct", "gt", 0.0, action="sell", weight=1.0, description="Sell signal"),
        ]
        result = evaluate_rules(rules, _indicators(rsi_14=50.0))
        assert result.signal == "hold"
        assert result.score == pytest.approx(0.0)
        assert len(result.matched_rules) == 2


class TestEvaluateRulesMultiCondition:
    def test_rule_with_multiple_conditions_all_met(self) -> None:
        rule = StrategyRule(
            conditions=[
                StrategyCondition(indicator_name="rsi", operator="lt", value=30.0),
                StrategyCondition(indicator_name="macd_histogram", operator="gt", value=0.0),
            ],
            action="buy",
            weight=1.0,
            description="RSI oversold + MACD bullish",
        )
        ind = _indicators(rsi_14=25.0)
        ind["macd"]["histogram"] = 0.5
        result = evaluate_rules([rule], ind)
        assert result.signal == "buy"
        assert "RSI oversold + MACD bullish" in result.matched_rules

    def test_rule_with_multiple_conditions_one_fails(self) -> None:
        rule = StrategyRule(
            conditions=[
                StrategyCondition(indicator_name="rsi", operator="lt", value=30.0),
                StrategyCondition(indicator_name="macd_histogram", operator="gt", value=0.0),
            ],
            action="buy",
            weight=1.0,
            description="RSI oversold + MACD bullish",
        )
        ind = _indicators(rsi_14=25.0)
        ind["macd"]["histogram"] = -0.3  # MACD condition fails
        result = evaluate_rules([rule], ind)
        assert result.signal == "hold"
        assert result.matched_rules == []

    def test_rule_with_missing_condition_skipped(self) -> None:
        rule = StrategyRule(
            conditions=[
                StrategyCondition(indicator_name="rsi", operator="lt", value=30.0),
                StrategyCondition(indicator_name="unknown_indicator", operator="gt", value=0.0),
            ],
            action="buy",
            weight=1.0,
            description="Partial data rule",
        )
        result = evaluate_rules([rule], _indicators(rsi_14=25.0))
        assert result.skipped_rules == 1
        assert result.matched_rules == []


class TestEvaluationResultModel:
    def test_result_fields(self) -> None:
        result = EvaluationResult(
            signal="buy",
            score=0.75,
            matched_rules=["Rule A", "Rule B"],
            total_rules=3,
            skipped_rules=1,
        )
        assert result.signal == "buy"
        assert result.score == 0.75
        assert result.matched_rules == ["Rule A", "Rule B"]
        assert result.total_rules == 3
        assert result.skipped_rules == 1
