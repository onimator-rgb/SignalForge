"""Strategy parameter optimizer – grid search over StrategyProfile fields."""

from __future__ import annotations

import dataclasses
import itertools
from dataclasses import dataclass
from typing import Any

from app.backtest.engine import BacktestResult, backtest_metrics, simulate_trades
from app.strategy.profiles import StrategyProfile


@dataclass(frozen=True)
class ParamRange:
    """Discrete values to try for one StrategyProfile parameter."""

    name: str
    values: list[float]


@dataclass(frozen=True)
class OptimizationResult:
    """Single row: parameter overrides + backtest result + modified profile."""

    params: dict[str, float]
    backtest: BacktestResult
    profile: StrategyProfile


_PROFILE_FIELDS: set[str] = {f.name for f in dataclasses.fields(StrategyProfile)}

_MAX_COMBINATIONS = 10_000


def optimize_params(
    base_profile: StrategyProfile,
    prices: list[float],
    param_ranges: list[ParamRange],
    top_n: int = 5,
    initial_capital: float = 1000.0,
) -> list[OptimizationResult]:
    """Run grid search over *param_ranges* and return top configs by Sharpe."""

    # --- validation -----------------------------------------------------------
    for pr in param_ranges:
        if pr.name not in _PROFILE_FIELDS:
            raise ValueError(
                f"Unknown StrategyProfile field: '{pr.name}'"
            )

    if len(prices) < 10:
        raise ValueError("prices must have at least 10 elements")

    # --- compute total combinations ------------------------------------------
    if param_ranges:
        total = 1
        for pr in param_ranges:
            total *= len(pr.values)
        if total > _MAX_COMBINATIONS:
            raise ValueError(
                f"Too many combinations: {total}. Maximum is {_MAX_COMBINATIONS}."
            )

    # --- empty ranges: single base-profile run --------------------------------
    if not param_ranges:
        trades = simulate_trades(prices, base_profile, initial_capital)
        metrics = backtest_metrics(trades, initial_capital)
        return [OptimizationResult(params={}, backtest=metrics, profile=base_profile)]

    # --- grid search ----------------------------------------------------------
    names = [pr.name for pr in param_ranges]
    value_lists = [pr.values for pr in param_ranges]
    results: list[OptimizationResult] = []

    for combo in itertools.product(*value_lists):
        overrides = dict(zip(names, combo))
        kw: dict[str, Any] = overrides
        profile = dataclasses.replace(base_profile, **kw)
        trades = simulate_trades(prices, profile, initial_capital)
        metrics = backtest_metrics(trades, initial_capital)
        results.append(
            OptimizationResult(params=overrides, backtest=metrics, profile=profile)
        )

    results.sort(key=lambda r: r.backtest.sharpe_ratio, reverse=True)
    return results[:top_n]
