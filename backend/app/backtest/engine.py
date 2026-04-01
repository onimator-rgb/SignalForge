"""Backtest engine — pure trade simulation from a price list.

Walks through historical price bars applying entry/exit rules from a
StrategyProfile and returns a list of Trade dataclasses.  No database,
no API, no side-effects — pure logic only.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from app.strategy.profiles import StrategyProfile


@dataclass(frozen=True)
class Trade:
    entry_index: int
    exit_index: int
    entry_price: float
    exit_price: float
    side: str  # always 'long'
    quantity: float
    pnl: float
    pnl_pct: float
    exit_reason: str  # 'stop_loss' | 'take_profit' | 'max_hold' | 'end_of_data'


@dataclass(frozen=True)
class BacktestResult:
    total_return: float
    total_return_pct: float
    max_drawdown_pct: float
    sharpe_ratio: float
    win_rate: float
    profit_factor: float
    total_trades: int
    avg_trade_pnl_pct: float
    best_trade_pnl_pct: float
    worst_trade_pnl_pct: float


def backtest_metrics(
    trades: list[Trade], initial_capital: float = 1000.0
) -> BacktestResult:
    """Summarise a list of trades into a BacktestResult."""
    if not trades:
        return BacktestResult(
            total_return=0.0,
            total_return_pct=0.0,
            max_drawdown_pct=0.0,
            sharpe_ratio=0.0,
            win_rate=0.0,
            profit_factor=0.0,
            total_trades=0,
            avg_trade_pnl_pct=0.0,
            best_trade_pnl_pct=0.0,
            worst_trade_pnl_pct=0.0,
        )

    n = len(trades)
    pnls = [t.pnl for t in trades]
    pnl_pcts = [t.pnl_pct for t in trades]

    total_return = sum(pnls)
    total_return_pct = total_return / initial_capital

    # --- equity curve & max drawdown ---
    equity = initial_capital
    peak = equity
    max_dd = 0.0
    for pnl in pnls:
        equity += pnl
        if equity > peak:
            peak = equity
        dd = (equity - peak) / peak if peak != 0.0 else 0.0
        if dd < max_dd:
            max_dd = dd

    # --- win rate ---
    wins = sum(1 for p in pnls if p > 0)
    win_rate = wins / n

    # --- profit factor ---
    gross_profit = sum(p for p in pnls if p > 0)
    gross_loss = sum(p for p in pnls if p < 0)
    if gross_loss < 0:
        profit_factor = gross_profit / abs(gross_loss)
    elif gross_profit > 0:
        profit_factor = float("inf")
    else:
        profit_factor = 0.0

    # --- sharpe ratio (annualized) ---
    sharpe = 0.0
    if n >= 2:
        mean_pct = sum(pnl_pcts) / n
        var = sum((x - mean_pct) ** 2 for x in pnl_pcts) / (n - 1)
        std_pct = math.sqrt(var)
        if std_pct > 0:
            avg_bars = sum(t.exit_index - t.entry_index for t in trades) / n
            bars_per_year = 8760
            annualization = math.sqrt(bars_per_year / max(avg_bars, 1.0))
            sharpe = (mean_pct / std_pct) * annualization

    avg_pnl_pct = sum(pnl_pcts) / n
    best_pnl_pct = max(pnl_pcts)
    worst_pnl_pct = min(pnl_pcts)

    return BacktestResult(
        total_return=total_return,
        total_return_pct=total_return_pct,
        max_drawdown_pct=max_dd,
        sharpe_ratio=sharpe,
        win_rate=win_rate,
        profit_factor=profit_factor,
        total_trades=n,
        avg_trade_pnl_pct=avg_pnl_pct,
        best_trade_pnl_pct=best_pnl_pct,
        worst_trade_pnl_pct=worst_pnl_pct,
    )


def simulate_trades(
    prices: list[float],
    profile: StrategyProfile,
    initial_capital: float = 1000.0,
) -> list[Trade]:
    """Simulate paper trades over *prices* using *profile* rules.

    Rules:
    - One position at a time, always long.
    - Entry uses ``profile.max_position_pct`` of current capital.
    - Exit priority: stop-loss → take-profit → max-hold → end-of-data.
    - Slippage applied on entry (buy) and exit (sell).
    - 1-bar cooldown after every exit before next entry.
    """
    if len(prices) < 2:
        return []

    trades: list[Trade] = []
    capital = initial_capital
    cooldown = 0

    in_position = False
    entry_index = 0
    entry_price = 0.0  # after slippage
    raw_entry_price = 0.0  # before slippage (for SL/TP checks)
    quantity = 0.0

    for i, raw_price in enumerate(prices):
        # --- cooldown tick ---
        if cooldown > 0:
            cooldown -= 1
            continue

        # --- not in position: try to enter ---
        if not in_position:
            position_value = capital * profile.max_position_pct
            entry_price = raw_price * (1.0 + profile.slippage_buy_pct)
            raw_entry_price = raw_price
            quantity = position_value / entry_price
            entry_index = i
            in_position = True
            continue

        # --- in position: check exit conditions ---
        change_pct = (raw_price - raw_entry_price) / raw_entry_price
        bars_held = i - entry_index

        exit_reason: str | None = None

        # stop_loss_pct is negative (e.g. -0.08)
        if change_pct <= profile.stop_loss_pct:
            exit_reason = "stop_loss"
        elif change_pct >= profile.take_profit_pct:
            exit_reason = "take_profit"
        elif bars_held >= profile.max_hold_hours:
            exit_reason = "max_hold"
        elif i == len(prices) - 1:
            exit_reason = "end_of_data"

        if exit_reason is not None:
            exit_price = raw_price * (1.0 - profile.slippage_sell_pct)
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
            cooldown = 1  # skip 1 bar before next entry

    return trades
