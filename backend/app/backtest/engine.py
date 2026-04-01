"""Backtest engine — pure trade simulation from a price list.

Walks through historical price bars applying entry/exit rules from a
StrategyProfile and returns a list of Trade dataclasses.  No database,
no API, no side-effects — pure logic only.
"""

from __future__ import annotations

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
