"""Strategy advisor — heuristic improvement suggestions for backtest results.

Pure logic module. No DB, no API, no LLM calls.
Analyzes BacktestResult metrics and strategy rule structure to produce
actionable plain-English improvement tips.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.backtest.engine import BacktestResult


@dataclass(frozen=True)
class StrategyRule:
    """Lightweight rule descriptor used by the advisor.

    *action* is ``"buy"`` or ``"sell"``.
    """

    name: str
    action: str  # "buy" | "sell"
    condition: str  # human-readable condition description


# ------------------------------------------------------------------
# Priority weights (lower = more severe, checked first)
# ------------------------------------------------------------------
_PRIORITY_DRAWDOWN = 1
_PRIORITY_PROFIT_FACTOR = 2
_PRIORITY_WORST_TRADE = 3
_PRIORITY_WIN_RATE = 4
_PRIORITY_SHARPE = 5
_PRIORITY_TOO_MANY_TRADES = 6
_PRIORITY_TOO_FEW_TRADES = 7
_PRIORITY_NO_RULES = 8
_PRIORITY_NO_SELL_RULES = 9
_PRIORITY_ALL_SAME_ACTION = 10

_MAX_SUGGESTIONS = 5


def suggest_improvements(
    strategy_rules: list[StrategyRule],
    backtest_result: BacktestResult,
) -> list[str]:
    """Return up to 5 prioritized improvement suggestions.

    Analyzes *backtest_result* metrics and *strategy_rules* structure,
    returning a list of plain-English suggestion strings sorted by
    severity (drawdown / profit-factor issues first).
    """
    # Early exit: nothing to say when there are no trades AND no rules.
    if backtest_result.total_trades == 0 and not strategy_rules:
        return []

    # Collect (priority, suggestion) pairs.
    suggestions: list[tuple[int, str]] = []

    # --- Metric-based heuristics ---
    if backtest_result.total_trades > 0:
        if backtest_result.max_drawdown_pct < -0.15:
            suggestions.append((
                _PRIORITY_DRAWDOWN,
                "High max drawdown detected — consider adding a stop-loss rule "
                "or tightening existing stop-loss values to limit downside risk.",
            ))

        if backtest_result.profit_factor < 1.0:
            suggestions.append((
                _PRIORITY_PROFIT_FACTOR,
                "Profit factor is below 1.0 — losses exceed gains. "
                "Review exit timing and consider closing losing positions earlier.",
            ))

        if backtest_result.worst_trade_pnl_pct < -0.10:
            suggestions.append((
                _PRIORITY_WORST_TRADE,
                "Largest losing trade exceeds -10% — consider tighter stop-loss "
                "levels or smaller position sizing to cap individual trade risk.",
            ))

        if backtest_result.win_rate < 0.4:
            suggestions.append((
                _PRIORITY_WIN_RATE,
                "Win rate is below 40% — consider tightening entry conditions "
                "or adding confirmation indicators to filter out weak signals.",
            ))

        if backtest_result.sharpe_ratio < 0.5:
            suggestions.append((
                _PRIORITY_SHARPE,
                "Sharpe ratio is low — consider reducing position frequency "
                "or adding trend-following filters to improve risk-adjusted returns.",
            ))

        if backtest_result.total_trades > 50:
            suggestions.append((
                _PRIORITY_TOO_MANY_TRADES,
                "Over 50 trades detected — consider adding a cooldown period "
                "or stricter entry filters to reduce overtrading.",
            ))

        if backtest_result.total_trades < 5:
            suggestions.append((
                _PRIORITY_TOO_FEW_TRADES,
                "Fewer than 5 trades — consider relaxing entry conditions "
                "to generate more signals for a statistically meaningful backtest.",
            ))

    # --- Rule-structure heuristics ---
    if not strategy_rules:
        suggestions.append((
            _PRIORITY_NO_RULES,
            "No strategy rules provided — add at least one entry rule "
            "and one exit rule to define a complete trading strategy.",
        ))
    else:
        actions = {r.action for r in strategy_rules}

        if len(actions) == 1:
            only_action = next(iter(actions))
            opposite = "sell" if only_action == "buy" else "buy"
            suggestions.append((
                _PRIORITY_ALL_SAME_ACTION,
                f"All rules have the same action ('{only_action}') — "
                f"consider adding '{opposite}' rules for a balanced strategy.",
            ))

        if "sell" not in actions:
            suggestions.append((
                _PRIORITY_NO_SELL_RULES,
                "No sell/exit rules found — add exit rules for proper "
                "risk management and to lock in profits.",
            ))

    # Sort by priority (lower number = higher severity) and cap at 5.
    suggestions.sort(key=lambda t: t[0])
    return [msg for _, msg in suggestions[:_MAX_SUGGESTIONS]]
