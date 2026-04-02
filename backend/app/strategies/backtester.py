"""Strategy backtester — rule-based trade simulation over historical bars.

Walks through price/indicator bars, calls evaluate_rules() at each bar to
decide entry/exit, and returns a list of Trade objects compatible with
the backtest metrics engine. Pure logic — no DB, no API, no side-effects.
"""

from __future__ import annotations

from app.backtest.engine import BacktestResult, Trade, backtest_metrics
from app.strategies.evaluator import evaluate_rules
from app.strategies.models import StrategyRule


def simulate_strategy_trades(
    rules: list[StrategyRule],
    bars: list[dict],
    initial_capital: float = 1000.0,
    stop_loss_pct: float = -0.08,
    take_profit_pct: float = 0.15,
    max_hold_bars: int = 72,
    max_position_pct: float = 0.20,
) -> list[Trade]:
    """Simulate trades over *bars* using strategy *rules*.

    At each bar, evaluate_rules() determines whether to buy or sell.
    Hard exits (stop-loss, take-profit, max-hold) take priority over signals.

    Returns a list of completed Trade objects.
    """
    if not bars:
        return []

    trades: list[Trade] = []
    capital = initial_capital

    in_position = False
    entry_index = 0
    entry_price = 0.0
    quantity = 0.0

    for i, bar in enumerate(bars):
        close = bar["close"]

        if not in_position:
            result = evaluate_rules(rules, bar)
            if result.signal == "buy":
                position_value = capital * max_position_pct
                entry_price = close
                quantity = position_value / entry_price
                entry_index = i
                in_position = True
            continue

        # In position — check hard exits first
        change_pct = (close - entry_price) / entry_price
        bars_held = i - entry_index

        exit_reason: str | None = None

        if change_pct <= stop_loss_pct:
            exit_reason = "stop_loss"
        elif change_pct >= take_profit_pct:
            exit_reason = "take_profit"
        elif bars_held >= max_hold_bars:
            exit_reason = "max_hold"
        elif i == len(bars) - 1:
            exit_reason = "end_of_data"
        else:
            # Check rule-based sell signal
            result = evaluate_rules(rules, bar)
            if result.signal == "sell":
                exit_reason = "signal"

        if exit_reason is not None:
            exit_price = close
            pnl = (exit_price - entry_price) * quantity
            pnl_pct = (exit_price - entry_price) / entry_price

            trades.append(
                Trade(
                    entry_index=entry_index,
                    exit_index=i,
                    entry_price=entry_price,
                    exit_price=exit_price,
                    side="long",
                    quantity=quantity,
                    pnl=pnl,
                    pnl_pct=pnl_pct,
                    exit_reason=exit_reason,
                )
            )
            capital += pnl
            in_position = False

    return trades


def backtest_strategy(
    rules: list[StrategyRule],
    bars: list[dict],
    **kwargs: object,
) -> BacktestResult:
    """Convenience wrapper: simulate trades then compute metrics."""
    initial_capital = float(kwargs.get("initial_capital", 1000.0))  # type: ignore[arg-type]
    trades = simulate_strategy_trades(rules, bars, **kwargs)  # type: ignore[arg-type]
    return backtest_metrics(trades, initial_capital)
