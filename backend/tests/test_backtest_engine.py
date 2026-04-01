"""Tests for the backtest engine — simulate_trades() pure function."""

from __future__ import annotations

import pytest

from app.backtest.engine import Trade, simulate_trades
from app.strategy.profiles import PROFILES

# Use the "balanced" profile for most tests.
BALANCED = PROFILES["balanced"]
# balanced: stop_loss_pct=-0.08, take_profit_pct=0.15, max_hold_hours=72,
#           slippage_buy_pct=0.001, slippage_sell_pct=0.001,
#           max_position_pct=0.20


def test_no_trades_on_empty_prices() -> None:
    assert simulate_trades([], BALANCED) == []


def test_no_trades_on_single_price() -> None:
    assert simulate_trades([100.0], BALANCED) == []


def test_stop_loss_triggered() -> None:
    # Entry at bar 0 (price 100), bar 1 price drops 10% → exceeds -8% SL.
    prices = [100.0, 90.0]
    trades = simulate_trades(prices, BALANCED)
    assert len(trades) == 1
    assert trades[0].exit_reason == "stop_loss"
    assert trades[0].entry_index == 0
    assert trades[0].exit_index == 1
    assert trades[0].pnl < 0


def test_take_profit_triggered() -> None:
    # Entry at bar 0 (price 100), bar 1 price rises 20% → exceeds 15% TP.
    prices = [100.0, 120.0]
    trades = simulate_trades(prices, BALANCED)
    assert len(trades) == 1
    assert trades[0].exit_reason == "take_profit"
    assert trades[0].pnl > 0


def test_max_hold_exit() -> None:
    # Flat prices for more than max_hold_hours (72) bars → max_hold exit.
    prices = [100.0] * 80
    trades = simulate_trades(prices, BALANCED)
    assert len(trades) >= 1
    assert trades[0].exit_reason == "max_hold"
    assert trades[0].exit_index - trades[0].entry_index == BALANCED.max_hold_hours


def test_end_of_data_closes_position() -> None:
    # Short flat series — not enough bars for max_hold, no SL/TP.
    prices = [100.0] * 5
    trades = simulate_trades(prices, BALANCED)
    assert len(trades) == 1
    assert trades[0].exit_reason == "end_of_data"
    assert trades[0].exit_index == len(prices) - 1


def test_multiple_trades() -> None:
    # Series long enough for 2+ trades: TP hit, cooldown, then end_of_data.
    prices = [100.0, 120.0]  # trade 1: TP
    # cooldown at index 2, new entry at index 3, end_of_data at index 4
    prices += [100.0, 100.0, 100.0]
    trades = simulate_trades(prices, BALANCED)
    assert len(trades) == 2
    assert trades[0].exit_reason == "take_profit"
    assert trades[1].exit_reason == "end_of_data"


def test_slippage_applied() -> None:
    prices = [100.0, 120.0]
    trades = simulate_trades(prices, BALANCED)
    t = trades[0]
    # Entry price should be higher than raw (slippage_buy adds cost).
    assert t.entry_price == pytest.approx(100.0 * 1.001)
    # Exit price should be lower than raw (slippage_sell reduces proceeds).
    assert t.exit_price == pytest.approx(120.0 * 0.999)


def test_pnl_calculation() -> None:
    prices = [100.0, 120.0]
    trades = simulate_trades(prices, BALANCED, initial_capital=1000.0)
    t = trades[0]
    expected_entry = 100.0 * 1.001
    expected_exit = 120.0 * 0.999
    expected_qty = (1000.0 * 0.20) / expected_entry
    expected_pnl = (expected_exit - expected_entry) * expected_qty
    expected_pnl_pct = (expected_exit - expected_entry) / expected_entry

    assert t.pnl == pytest.approx(expected_pnl)
    assert t.pnl_pct == pytest.approx(expected_pnl_pct)
    assert t.quantity == pytest.approx(expected_qty)


def test_cooldown_between_trades() -> None:
    # After exit at index 1, cooldown skips index 2, entry at index 3.
    prices = [100.0, 120.0, 100.0, 100.0, 100.0]
    trades = simulate_trades(prices, BALANCED)
    assert len(trades) == 2
    # First trade exits at 1, second enters at 3 (gap of 2 indices = 1 cooldown bar).
    assert trades[1].entry_index == 3
    assert trades[1].entry_index - trades[0].exit_index == 2


def test_trade_is_frozen() -> None:
    prices = [100.0, 90.0]
    trades = simulate_trades(prices, BALANCED)
    with pytest.raises(AttributeError):
        trades[0].pnl = 999.0  # type: ignore[misc]


def test_trade_side_always_long() -> None:
    prices = [100.0, 90.0]
    trades = simulate_trades(prices, BALANCED)
    assert all(t.side == "long" for t in trades)
