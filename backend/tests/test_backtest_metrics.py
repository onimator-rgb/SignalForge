"""Tests for backtest_metrics() — BacktestResult from a trade list."""

from __future__ import annotations

import math

import pytest

from app.backtest.engine import BacktestResult, Trade, backtest_metrics


def _trade(
    entry_idx: int = 0,
    exit_idx: int = 10,
    entry_price: float = 100.0,
    exit_price: float = 110.0,
    quantity: float = 1.0,
    pnl: float | None = None,
    pnl_pct: float | None = None,
    exit_reason: str = "take_profit",
) -> Trade:
    """Helper to build a Trade with sensible defaults."""
    if pnl is None:
        pnl = (exit_price - entry_price) * quantity
    if pnl_pct is None:
        pnl_pct = (exit_price - entry_price) / entry_price
    return Trade(
        entry_index=entry_idx,
        exit_index=exit_idx,
        entry_price=entry_price,
        exit_price=exit_price,
        side="long",
        quantity=quantity,
        pnl=pnl,
        pnl_pct=pnl_pct,
        exit_reason=exit_reason,
    )


class TestEmptyTrades:
    def test_all_zeros(self) -> None:
        result = backtest_metrics([])
        assert result.total_return == 0.0
        assert result.total_return_pct == 0.0
        assert result.max_drawdown_pct == 0.0
        assert result.sharpe_ratio == 0.0
        assert result.win_rate == 0.0
        assert result.profit_factor == 0.0
        assert result.total_trades == 0
        assert result.avg_trade_pnl_pct == 0.0
        assert result.best_trade_pnl_pct == 0.0
        assert result.worst_trade_pnl_pct == 0.0

    def test_returns_backtest_result_type(self) -> None:
        result = backtest_metrics([])
        assert isinstance(result, BacktestResult)


class TestSingleWinningTrade:
    @pytest.fixture()
    def result(self) -> BacktestResult:
        trade = _trade(entry_price=100.0, exit_price=110.0, quantity=10.0)
        return backtest_metrics([trade], initial_capital=1000.0)

    def test_total_return(self, result: BacktestResult) -> None:
        assert result.total_return == pytest.approx(100.0)

    def test_total_return_pct(self, result: BacktestResult) -> None:
        assert result.total_return_pct == pytest.approx(0.10)

    def test_win_rate(self, result: BacktestResult) -> None:
        assert result.win_rate == 1.0

    def test_profit_factor_inf(self, result: BacktestResult) -> None:
        assert result.profit_factor == float("inf")

    def test_sharpe_zero_single_trade(self, result: BacktestResult) -> None:
        assert result.sharpe_ratio == 0.0

    def test_max_drawdown_non_positive(self, result: BacktestResult) -> None:
        assert result.max_drawdown_pct <= 0.0

    def test_best_worst_equal(self, result: BacktestResult) -> None:
        assert result.best_trade_pnl_pct == result.worst_trade_pnl_pct


class TestSingleLosingTrade:
    @pytest.fixture()
    def result(self) -> BacktestResult:
        trade = _trade(entry_price=100.0, exit_price=90.0, quantity=10.0)
        return backtest_metrics([trade], initial_capital=1000.0)

    def test_negative_return(self, result: BacktestResult) -> None:
        assert result.total_return == pytest.approx(-100.0)

    def test_win_rate_zero(self, result: BacktestResult) -> None:
        assert result.win_rate == 0.0

    def test_profit_factor_zero(self, result: BacktestResult) -> None:
        assert result.profit_factor == 0.0

    def test_drawdown_negative(self, result: BacktestResult) -> None:
        assert result.max_drawdown_pct < 0.0


class TestMixedTrades:
    @pytest.fixture()
    def result(self) -> BacktestResult:
        trades = [
            _trade(entry_idx=0, exit_idx=5, entry_price=100, exit_price=120, quantity=5),
            _trade(entry_idx=7, exit_idx=12, entry_price=120, exit_price=100, quantity=5),
            _trade(entry_idx=14, exit_idx=20, entry_price=100, exit_price=115, quantity=5),
        ]
        return backtest_metrics(trades, initial_capital=1000.0)

    def test_total_trades(self, result: BacktestResult) -> None:
        assert result.total_trades == 3

    def test_win_rate(self, result: BacktestResult) -> None:
        assert result.win_rate == pytest.approx(2 / 3)

    def test_profit_factor(self, result: BacktestResult) -> None:
        gross_profit = (20 * 5) + (15 * 5)  # 100 + 75 = 175
        gross_loss = abs(-20 * 5)  # 100
        assert result.profit_factor == pytest.approx(gross_profit / gross_loss)

    def test_max_drawdown_negative(self, result: BacktestResult) -> None:
        assert result.max_drawdown_pct < 0.0

    def test_sharpe_nonzero(self, result: BacktestResult) -> None:
        assert result.sharpe_ratio != 0.0

    def test_best_trade(self, result: BacktestResult) -> None:
        assert result.best_trade_pnl_pct == pytest.approx(20 / 100)

    def test_worst_trade(self, result: BacktestResult) -> None:
        assert result.worst_trade_pnl_pct == pytest.approx(-20 / 120)


class TestAllWinningTrades:
    @pytest.fixture()
    def result(self) -> BacktestResult:
        trades = [
            _trade(entry_price=100, exit_price=110, quantity=1, entry_idx=0, exit_idx=5),
            _trade(entry_price=110, exit_price=120, quantity=1, entry_idx=7, exit_idx=12),
        ]
        return backtest_metrics(trades, initial_capital=1000.0)

    def test_profit_factor_inf(self, result: BacktestResult) -> None:
        assert result.profit_factor == float("inf")

    def test_win_rate_one(self, result: BacktestResult) -> None:
        assert result.win_rate == 1.0

    def test_drawdown_zero(self, result: BacktestResult) -> None:
        assert result.max_drawdown_pct == 0.0


class TestDrawdownAlwaysNonPositive:
    @pytest.mark.parametrize(
        "trades",
        [
            [],
            [_trade(entry_price=100, exit_price=110)],
            [_trade(entry_price=100, exit_price=90)],
            [
                _trade(entry_price=100, exit_price=110, entry_idx=0, exit_idx=5),
                _trade(entry_price=110, exit_price=90, entry_idx=7, exit_idx=12),
            ],
        ],
    )
    def test_max_drawdown_non_positive(self, trades: list[Trade]) -> None:
        result = backtest_metrics(trades)
        assert result.max_drawdown_pct <= 0.0


class TestBacktestResultFrozen:
    def test_frozen(self) -> None:
        result = backtest_metrics([])
        with pytest.raises(AttributeError):
            result.total_return = 42.0  # type: ignore[misc]
