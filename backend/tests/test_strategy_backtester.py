"""Tests for strategy backtester — rule-based trade simulation."""

from __future__ import annotations

from app.backtest.engine import BacktestResult, Trade
from app.strategies.backtester import backtest_strategy, simulate_strategy_trades
from app.strategies.models import StrategyCondition, StrategyRule


def _buy_rule(indicator: str = "rsi", op: str = "lt", value: float = 30.0) -> StrategyRule:
    """Helper: create a buy rule."""
    return StrategyRule(
        conditions=[StrategyCondition(indicator=indicator, operator=op, value=value)],
        action="buy",
        description="test buy",
    )


def _sell_rule(indicator: str = "rsi", op: str = "gt", value: float = 70.0) -> StrategyRule:
    """Helper: create a sell rule."""
    return StrategyRule(
        conditions=[StrategyCondition(indicator=indicator, operator=op, value=value)],
        action="sell",
        description="test sell",
    )


def _bar(close: float, rsi: float = 50.0) -> dict:
    """Helper: create a minimal bar dict."""
    return {"close": close, "rsi_14": rsi}


class TestSimulateStrategyTrades:
    def test_empty_bars_returns_empty(self) -> None:
        rules = [_buy_rule(), _sell_rule()]
        assert simulate_strategy_trades(rules, []) == []

    def test_buy_signal_opens_position(self) -> None:
        rules = [_buy_rule(op="lt", value=30.0), _sell_rule(op="gt", value=70.0)]
        bars = [
            _bar(100.0, rsi=25.0),  # buy signal
            _bar(105.0, rsi=50.0),  # hold
            _bar(110.0, rsi=50.0),  # last bar -> end_of_data
        ]
        trades = simulate_strategy_trades(rules, bars)
        assert len(trades) == 1
        assert trades[0].entry_index == 0
        assert trades[0].entry_price == 100.0
        assert trades[0].exit_reason == "end_of_data"

    def test_sell_signal_closes_position(self) -> None:
        rules = [_buy_rule(op="lt", value=30.0), _sell_rule(op="gt", value=70.0)]
        bars = [
            _bar(100.0, rsi=25.0),  # buy
            _bar(105.0, rsi=75.0),  # sell signal
            _bar(110.0, rsi=50.0),  # no position
        ]
        trades = simulate_strategy_trades(rules, bars)
        assert len(trades) == 1
        assert trades[0].exit_reason == "signal"
        assert trades[0].exit_index == 1
        assert trades[0].exit_price == 105.0

    def test_stop_loss_triggers(self) -> None:
        rules = [_buy_rule(op="lt", value=30.0)]
        bars = [
            _bar(100.0, rsi=25.0),  # buy
            _bar(90.0, rsi=50.0),   # -10% drop -> stop loss at -8%
        ]
        trades = simulate_strategy_trades(rules, bars, stop_loss_pct=-0.08)
        assert len(trades) == 1
        assert trades[0].exit_reason == "stop_loss"

    def test_take_profit_triggers(self) -> None:
        rules = [_buy_rule(op="lt", value=30.0)]
        bars = [
            _bar(100.0, rsi=25.0),  # buy
            _bar(120.0, rsi=50.0),  # +20% gain -> take profit at 15%
        ]
        trades = simulate_strategy_trades(rules, bars, take_profit_pct=0.15)
        assert len(trades) == 1
        assert trades[0].exit_reason == "take_profit"

    def test_max_hold_triggers(self) -> None:
        rules = [_buy_rule(op="lt", value=30.0)]
        # Buy at bar 0, hold for 5 bars (max_hold_bars=5)
        bars = [_bar(100.0, rsi=25.0)]  # buy
        bars += [_bar(100.0, rsi=50.0) for _ in range(5)]  # hold 5 bars
        bars.append(_bar(100.0, rsi=50.0))  # extra bar

        trades = simulate_strategy_trades(rules, bars, max_hold_bars=5)
        assert len(trades) == 1
        assert trades[0].exit_reason == "max_hold"
        assert trades[0].exit_index == 5

    def test_end_of_data_forces_exit(self) -> None:
        rules = [_buy_rule(op="lt", value=30.0)]
        bars = [
            _bar(100.0, rsi=25.0),  # buy
            _bar(102.0, rsi=50.0),  # hold
            _bar(103.0, rsi=50.0),  # last bar -> end_of_data
        ]
        trades = simulate_strategy_trades(rules, bars)
        assert len(trades) == 1
        assert trades[0].exit_reason == "end_of_data"
        assert trades[0].exit_index == 2

    def test_no_buy_signal_means_no_trades(self) -> None:
        rules = [_buy_rule(op="lt", value=30.0)]
        bars = [
            _bar(100.0, rsi=50.0),  # no buy (rsi > 30)
            _bar(105.0, rsi=60.0),
            _bar(110.0, rsi=55.0),
        ]
        trades = simulate_strategy_trades(rules, bars)
        assert trades == []

    def test_multiple_trades(self) -> None:
        rules = [_buy_rule(op="lt", value=30.0), _sell_rule(op="gt", value=70.0)]
        bars = [
            _bar(100.0, rsi=25.0),  # buy
            _bar(105.0, rsi=75.0),  # sell
            _bar(100.0, rsi=25.0),  # buy again
            _bar(110.0, rsi=75.0),  # sell again
            _bar(110.0, rsi=50.0),  # extra bar so index 3 isn't last
        ]
        trades = simulate_strategy_trades(rules, bars)
        assert len(trades) == 2
        assert trades[0].exit_reason == "signal"
        assert trades[1].exit_reason == "signal"

    def test_trade_returns_correct_types(self) -> None:
        rules = [_buy_rule(op="lt", value=30.0)]
        bars = [_bar(100.0, rsi=25.0), _bar(110.0, rsi=50.0)]
        trades = simulate_strategy_trades(rules, bars)
        assert len(trades) == 1
        t = trades[0]
        assert isinstance(t, Trade)
        assert t.side == "long"
        assert t.quantity > 0
        assert t.pnl > 0  # price went up

    def test_pnl_calculation(self) -> None:
        rules = [_buy_rule(op="lt", value=30.0)]
        bars = [_bar(100.0, rsi=25.0), _bar(110.0, rsi=50.0)]
        trades = simulate_strategy_trades(
            rules, bars, initial_capital=1000.0, max_position_pct=0.20,
        )
        t = trades[0]
        expected_qty = (1000.0 * 0.20) / 100.0  # 2.0
        assert t.quantity == expected_qty
        assert t.pnl == (110.0 - 100.0) * expected_qty
        assert t.pnl_pct == (110.0 - 100.0) / 100.0

    def test_stop_loss_priority_over_sell_signal(self) -> None:
        """Hard exits take priority over rule-based signals."""
        rules = [_buy_rule(op="lt", value=30.0), _sell_rule(op="gt", value=70.0)]
        bars = [
            _bar(100.0, rsi=25.0),  # buy
            _bar(88.0, rsi=75.0),   # stop loss AND sell signal -> stop loss wins
        ]
        trades = simulate_strategy_trades(rules, bars, stop_loss_pct=-0.08)
        assert trades[0].exit_reason == "stop_loss"


class TestBacktestStrategy:
    def test_returns_backtest_result(self) -> None:
        rules = [_buy_rule(op="lt", value=30.0)]
        bars = [_bar(100.0, rsi=25.0), _bar(110.0, rsi=50.0)]
        result = backtest_strategy(rules, bars)
        assert isinstance(result, BacktestResult)
        assert result.total_trades == 1
        assert result.total_return > 0

    def test_empty_bars_returns_zero_metrics(self) -> None:
        result = backtest_strategy([_buy_rule()], [])
        assert result.total_trades == 0
        assert result.total_return == 0.0
        assert result.win_rate == 0.0

    def test_metrics_with_winning_trade(self) -> None:
        rules = [_buy_rule(op="lt", value=30.0)]
        bars = [_bar(100.0, rsi=25.0), _bar(110.0, rsi=50.0)]
        result = backtest_strategy(rules, bars, initial_capital=1000.0)
        assert result.win_rate == 1.0
        assert result.total_return > 0

    def test_metrics_with_losing_trade(self) -> None:
        rules = [_buy_rule(op="lt", value=30.0)]
        bars = [_bar(100.0, rsi=25.0), _bar(90.0, rsi=50.0)]
        result = backtest_strategy(rules, bars, initial_capital=1000.0)
        assert result.win_rate == 0.0
        assert result.total_return < 0
