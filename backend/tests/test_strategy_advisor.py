"""Tests for app.ai_assistant.strategy_advisor — suggest_improvements()."""

from __future__ import annotations

from app.ai_assistant.strategy_advisor import StrategyRule, suggest_improvements
from app.backtest.engine import BacktestResult


def _make_result(**overrides: object) -> BacktestResult:
    """Helper: create a BacktestResult with sensible defaults, overriding as needed."""
    defaults: dict[str, object] = dict(
        total_return=100.0,
        total_return_pct=0.10,
        max_drawdown_pct=-0.05,
        sharpe_ratio=1.5,
        win_rate=0.60,
        profit_factor=2.0,
        total_trades=20,
        avg_trade_pnl_pct=0.005,
        best_trade_pnl_pct=0.08,
        worst_trade_pnl_pct=-0.03,
    )
    defaults.update(overrides)
    return BacktestResult(**defaults)  # type: ignore[arg-type]


_BUY_RULE = StrategyRule(name="sma_cross", action="buy", condition="SMA20 > SMA50")
_SELL_RULE = StrategyRule(name="take_profit", action="sell", condition="pnl > 5%")


# ------------------------------------------------------------------
# Edge cases
# ------------------------------------------------------------------

class TestEdgeCases:
    def test_empty_result_and_no_rules(self) -> None:
        result = _make_result(total_trades=0)
        assert suggest_improvements([], result) == []

    def test_good_metrics_few_suggestions(self) -> None:
        result = _make_result()
        suggestions = suggest_improvements([_BUY_RULE, _SELL_RULE], result)
        assert len(suggestions) == 0

    def test_zero_trades_with_rules(self) -> None:
        result = _make_result(total_trades=0)
        suggestions = suggest_improvements([_BUY_RULE, _SELL_RULE], result)
        # No metric-based suggestions (0 trades), but rules exist so no rule suggestions either
        assert len(suggestions) == 0


# ------------------------------------------------------------------
# Individual metric triggers
# ------------------------------------------------------------------

class TestMetricTriggers:
    def test_low_win_rate(self) -> None:
        result = _make_result(win_rate=0.30)
        suggestions = suggest_improvements([_BUY_RULE, _SELL_RULE], result)
        assert any("win rate" in s.lower() for s in suggestions)

    def test_high_drawdown(self) -> None:
        result = _make_result(max_drawdown_pct=-0.25)
        suggestions = suggest_improvements([_BUY_RULE, _SELL_RULE], result)
        assert any("drawdown" in s.lower() for s in suggestions)

    def test_low_sharpe(self) -> None:
        result = _make_result(sharpe_ratio=0.3)
        suggestions = suggest_improvements([_BUY_RULE, _SELL_RULE], result)
        assert any("sharpe" in s.lower() for s in suggestions)

    def test_negative_profit_factor(self) -> None:
        result = _make_result(profit_factor=0.7)
        suggestions = suggest_improvements([_BUY_RULE, _SELL_RULE], result)
        assert any("profit factor" in s.lower() for s in suggestions)

    def test_too_few_trades(self) -> None:
        result = _make_result(total_trades=3)
        suggestions = suggest_improvements([_BUY_RULE, _SELL_RULE], result)
        assert any("fewer than 5" in s.lower() for s in suggestions)

    def test_too_many_trades(self) -> None:
        result = _make_result(total_trades=60)
        suggestions = suggest_improvements([_BUY_RULE, _SELL_RULE], result)
        assert any("overtrading" in s.lower() for s in suggestions)

    def test_large_worst_trade(self) -> None:
        result = _make_result(worst_trade_pnl_pct=-0.15)
        suggestions = suggest_improvements([_BUY_RULE, _SELL_RULE], result)
        assert any("losing trade" in s.lower() for s in suggestions)


# ------------------------------------------------------------------
# Rule-structure triggers
# ------------------------------------------------------------------

class TestRuleStructure:
    def test_no_rules_provided(self) -> None:
        result = _make_result(total_trades=10)
        suggestions = suggest_improvements([], result)
        assert any("no strategy rules" in s.lower() for s in suggestions)

    def test_all_buy_rules(self) -> None:
        buy_only = [
            StrategyRule(name="r1", action="buy", condition="c1"),
            StrategyRule(name="r2", action="buy", condition="c2"),
        ]
        result = _make_result()
        suggestions = suggest_improvements(buy_only, result)
        assert any("sell" in s.lower() for s in suggestions)

    def test_all_sell_rules(self) -> None:
        sell_only = [
            StrategyRule(name="r1", action="sell", condition="c1"),
            StrategyRule(name="r2", action="sell", condition="c2"),
        ]
        result = _make_result()
        suggestions = suggest_improvements(sell_only, result)
        assert any("buy" in s.lower() for s in suggestions)

    def test_no_sell_rules_triggers_suggestion(self) -> None:
        buy_only = [_BUY_RULE]
        result = _make_result()
        suggestions = suggest_improvements(buy_only, result)
        assert any("exit rules" in s.lower() or "sell" in s.lower() for s in suggestions)


# ------------------------------------------------------------------
# Cap & priority
# ------------------------------------------------------------------

class TestCapAndPriority:
    def test_max_five_suggestions(self) -> None:
        # Trigger as many heuristics as possible
        result = _make_result(
            win_rate=0.2,
            max_drawdown_pct=-0.30,
            sharpe_ratio=0.1,
            profit_factor=0.5,
            total_trades=60,
            worst_trade_pnl_pct=-0.20,
        )
        suggestions = suggest_improvements([], result)
        assert len(suggestions) <= 5

    def test_drawdown_before_win_rate(self) -> None:
        result = _make_result(
            win_rate=0.2,
            max_drawdown_pct=-0.30,
        )
        suggestions = suggest_improvements([_BUY_RULE, _SELL_RULE], result)
        assert len(suggestions) >= 2
        # Drawdown should appear before win rate
        dd_idx = next(i for i, s in enumerate(suggestions) if "drawdown" in s.lower())
        wr_idx = next(i for i, s in enumerate(suggestions) if "win rate" in s.lower())
        assert dd_idx < wr_idx
