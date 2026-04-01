"""Strategy parameter optimizer — grid search over StrategyProfile fields.

Generates all combinations of provided parameter ranges, runs backtests
for each, and returns top results ranked by Sharpe ratio.
"""

from __future__ import annotations

import dataclasses
import itertools
from dataclasses import dataclass
from typing import Any

from app.backtest.engine import BacktestResult, backtest_metrics, simulate_trades
from app.strategy.profiles import StrategyProfile

MAX_COMBINATIONS = 10_000


@dataclass(frozen=True)
class ParamRange:
    field_name: str
    values: list[float]


@dataclass(frozen=True)
class OptimizationResult:
    params: dict[str, float]
    sharpe_ratio: float
    total_return_pct: float
    max_drawdown_pct: float
    win_rate: float
    profit_factor: float
    total_trades: int


def optimize_params(
    base_profile: StrategyProfile,
    prices: list[float],
    param_ranges: list[ParamRange],
    top_n: int = 5,
    initial_capital: float = 1000.0,
) -> list[OptimizationResult]:
    """Grid-search over *param_ranges* and return top configs by Sharpe ratio."""
    if len(prices) < 10:
        raise ValueError("At least 10 price bars are required for optimization.")

    # Validate field names
    valid_fields = {f.name for f in dataclasses.fields(StrategyProfile)}
    for pr in param_ranges:
        if pr.field_name not in valid_fields:
            raise ValueError(f"Unknown StrategyProfile field: {pr.field_name}")

    # Empty ranges → evaluate base profile only
    if not param_ranges:
        trades = simulate_trades(prices, base_profile, initial_capital)
        metrics = backtest_metrics(trades, initial_capital)
        return [_metrics_to_result({}, metrics)]

    # Build combinations
    field_names = [pr.field_name for pr in param_ranges]
    value_lists = [pr.values for pr in param_ranges]

    total = 1
    for v in value_lists:
        total *= len(v)
    if total > MAX_COMBINATIONS:
        raise ValueError(
            f"Too many parameter combinations ({total}); limit is {MAX_COMBINATIONS}."
        )

    results: list[OptimizationResult] = []
    for combo in itertools.product(*value_lists):
        overrides: dict[str, Any] = dict(zip(field_names, combo))
        profile = dataclasses.replace(base_profile, **overrides)
        trades = simulate_trades(prices, profile, initial_capital)
        metrics = backtest_metrics(trades, initial_capital)
        results.append(_metrics_to_result(overrides, metrics))

    results.sort(key=lambda r: r.sharpe_ratio, reverse=True)
    return results[:top_n]


def _metrics_to_result(
    params: dict[str, float], m: BacktestResult
) -> OptimizationResult:
    return OptimizationResult(
        params=params,
        sharpe_ratio=m.sharpe_ratio,
        total_return_pct=m.total_return_pct,
        max_drawdown_pct=m.max_drawdown_pct,
        win_rate=m.win_rate,
        profit_factor=m.profit_factor,
        total_trades=m.total_trades,
    )
