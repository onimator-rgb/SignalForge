"""Tests for strategy performance comparison module."""

from __future__ import annotations

from app.backtest.engine import BacktestResult
from app.strategies.comparison import compare_strategies


def _make_result(
    *,
    total_return_pct: float = 0.0,
    win_rate: float = 0.0,
    max_drawdown_pct: float = 0.0,
    sharpe_ratio: float = 0.0,
    total_trades: int = 0,
    profit_factor: float = 0.0,
) -> BacktestResult:
    return BacktestResult(
        total_return=0.0,
        total_return_pct=total_return_pct,
        max_drawdown_pct=max_drawdown_pct,
        sharpe_ratio=sharpe_ratio,
        win_rate=win_rate,
        profit_factor=profit_factor,
        total_trades=total_trades,
        avg_trade_pnl_pct=0.0,
        best_trade_pnl_pct=0.0,
        worst_trade_pnl_pct=0.0,
    )


def test_empty_input() -> None:
    summary = compare_strategies({})
    assert summary.rows == []
    assert summary.best_return == ""
    assert summary.best_sharpe == ""
    assert summary.lowest_drawdown == ""
    assert summary.best_win_rate == ""


def test_single_strategy() -> None:
    result = _make_result(
        total_return_pct=10.0,
        sharpe_ratio=1.5,
        win_rate=0.6,
        max_drawdown_pct=-5.0,
        total_trades=20,
        profit_factor=1.8,
    )
    summary = compare_strategies({"Alpha": result})

    assert len(summary.rows) == 1
    row = summary.rows[0]
    assert row.rank == 1
    assert row.strategy_name == "Alpha"
    assert row.sharpe_ratio == 1.5
    assert summary.best_return == "Alpha"
    assert summary.best_sharpe == "Alpha"
    assert summary.lowest_drawdown == "Alpha"
    assert summary.best_win_rate == "Alpha"


def test_multiple_strategies() -> None:
    strategies = {
        "Low": _make_result(sharpe_ratio=0.5, total_return_pct=5.0),
        "Mid": _make_result(sharpe_ratio=1.0, total_return_pct=10.0),
        "High": _make_result(sharpe_ratio=2.0, total_return_pct=15.0),
    }
    summary = compare_strategies(strategies)

    assert len(summary.rows) == 3
    assert summary.rows[0].strategy_name == "High"
    assert summary.rows[0].rank == 1
    assert summary.rows[1].strategy_name == "Mid"
    assert summary.rows[1].rank == 2
    assert summary.rows[2].strategy_name == "Low"
    assert summary.rows[2].rank == 3


def test_best_per_metric() -> None:
    strategies = {
        "ReturnKing": _make_result(
            total_return_pct=50.0, sharpe_ratio=0.8, win_rate=0.4, max_drawdown_pct=-20.0
        ),
        "SharpeKing": _make_result(
            total_return_pct=10.0, sharpe_ratio=3.0, win_rate=0.5, max_drawdown_pct=-15.0
        ),
        "SafeKing": _make_result(
            total_return_pct=5.0, sharpe_ratio=1.0, win_rate=0.7, max_drawdown_pct=-2.0
        ),
    }
    summary = compare_strategies(strategies)

    assert summary.best_return == "ReturnKing"
    assert summary.best_sharpe == "SharpeKing"
    assert summary.lowest_drawdown == "SafeKing"  # -2.0 is highest (least negative)
    assert summary.best_win_rate == "SafeKing"


def test_negative_returns() -> None:
    strategies = {
        "Bad": _make_result(
            total_return_pct=-20.0, sharpe_ratio=-1.5, win_rate=0.2, max_drawdown_pct=-30.0
        ),
        "Worse": _make_result(
            total_return_pct=-40.0, sharpe_ratio=-3.0, win_rate=0.1, max_drawdown_pct=-50.0
        ),
    }
    summary = compare_strategies(strategies)

    assert summary.rows[0].strategy_name == "Bad"
    assert summary.rows[0].rank == 1
    assert summary.rows[1].strategy_name == "Worse"
    assert summary.rows[1].rank == 2
    assert summary.best_return == "Bad"
    assert summary.best_sharpe == "Bad"
    assert summary.lowest_drawdown == "Bad"  # -30 > -50
    assert summary.best_win_rate == "Bad"
