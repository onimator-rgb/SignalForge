"""Strategy performance comparison — side-by-side metrics.

Pure-logic module: takes multiple BacktestResult objects, produces a ranked
comparison table sorted by Sharpe ratio descending.
"""

from __future__ import annotations

from pydantic import BaseModel

from app.backtest.engine import BacktestResult


class ComparisonRow(BaseModel):
    strategy_name: str
    total_return_pct: float
    win_rate: float
    max_drawdown_pct: float
    sharpe_ratio: float
    total_trades: int
    profit_factor: float
    rank: int


class ComparisonSummary(BaseModel):
    rows: list[ComparisonRow]
    best_return: str
    best_sharpe: str
    lowest_drawdown: str
    best_win_rate: str


def compare_strategies(
    strategies: dict[str, BacktestResult],
) -> ComparisonSummary:
    """Compare multiple back-test results and return a ranked summary."""
    if not strategies:
        return ComparisonSummary(
            rows=[],
            best_return="",
            best_sharpe="",
            lowest_drawdown="",
            best_win_rate="",
        )

    # Build rows sorted by sharpe_ratio descending (stable sort).
    sorted_names = sorted(
        strategies.keys(),
        key=lambda n: strategies[n].sharpe_ratio,
        reverse=True,
    )

    rows: list[ComparisonRow] = []
    for rank, name in enumerate(sorted_names, start=1):
        r = strategies[name]
        rows.append(
            ComparisonRow(
                strategy_name=name,
                total_return_pct=r.total_return_pct,
                win_rate=r.win_rate,
                max_drawdown_pct=r.max_drawdown_pct,
                sharpe_ratio=r.sharpe_ratio,
                total_trades=r.total_trades,
                profit_factor=r.profit_factor,
                rank=rank,
            )
        )

    best_return = max(strategies, key=lambda n: strategies[n].total_return_pct)
    best_sharpe = sorted_names[0]
    lowest_drawdown = max(strategies, key=lambda n: strategies[n].max_drawdown_pct)
    best_win_rate = max(strategies, key=lambda n: strategies[n].win_rate)

    return ComparisonSummary(
        rows=rows,
        best_return=best_return,
        best_sharpe=best_sharpe,
        lowest_drawdown=lowest_drawdown,
        best_win_rate=best_win_rate,
    )
