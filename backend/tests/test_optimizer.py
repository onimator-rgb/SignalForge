"""Tests for the strategy parameter grid-search optimizer."""

from __future__ import annotations

import math

import pytest

from app.strategies.optimizer import OptimizationResult, ParamRange, optimize_params
from app.strategy.profiles import PROFILES

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

BASE_PROFILE = PROFILES["balanced"]
PRICES = [100.0 + math.sin(i / 10) * 10 for i in range(200)]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_optimize_single_param() -> None:
    """Optimize stop_loss_pct over 3 values; results sorted by Sharpe desc."""
    ranges = [ParamRange(name="stop_loss_pct", values=[-0.05, -0.08, -0.12])]
    results = optimize_params(BASE_PROFILE, PRICES, ranges, top_n=5)

    assert len(results) == 3
    sharpes = [r.backtest.sharpe_ratio for r in results]
    assert sharpes == sorted(sharpes, reverse=True)


def test_optimize_two_params() -> None:
    """3x3 = 9 combos; top_n=3 returns exactly 3 results."""
    ranges = [
        ParamRange(name="stop_loss_pct", values=[-0.05, -0.08, -0.12]),
        ParamRange(name="take_profit_pct", values=[0.10, 0.15, 0.20]),
    ]
    results = optimize_params(BASE_PROFILE, PRICES, ranges, top_n=3)

    assert len(results) == 3
    sharpes = [r.backtest.sharpe_ratio for r in results]
    assert sharpes == sorted(sharpes, reverse=True)


def test_optimize_empty_ranges() -> None:
    """Empty param_ranges returns a single result with the base profile."""
    results = optimize_params(BASE_PROFILE, PRICES, [], top_n=5)

    assert len(results) == 1
    assert results[0].params == {}
    assert results[0].profile is BASE_PROFILE


def test_optimize_invalid_param_name() -> None:
    """Raise ValueError for an unknown StrategyProfile field."""
    ranges = [ParamRange(name="nonexistent_field", values=[1.0, 2.0])]
    with pytest.raises(ValueError, match="Unknown StrategyProfile field"):
        optimize_params(BASE_PROFILE, PRICES, ranges)


def test_optimize_too_few_prices() -> None:
    """Raise ValueError when prices has fewer than 10 elements."""
    ranges = [ParamRange(name="stop_loss_pct", values=[-0.05])]
    with pytest.raises(ValueError, match="at least 10 elements"):
        optimize_params(BASE_PROFILE, [100.0] * 5, ranges)


def test_optimize_too_many_combinations() -> None:
    """Raise ValueError when the grid exceeds 10 000 combinations."""
    ranges = [
        ParamRange(name="stop_loss_pct", values=[float(-i) for i in range(101)]),
        ParamRange(name="take_profit_pct", values=[float(i) for i in range(101)]),
    ]
    with pytest.raises(ValueError, match="Too many combinations"):
        optimize_params(BASE_PROFILE, PRICES, ranges)


def test_result_contains_modified_profile() -> None:
    """Returned profile has the overridden parameter values."""
    ranges = [ParamRange(name="stop_loss_pct", values=[-0.03, -0.06])]
    results = optimize_params(BASE_PROFILE, PRICES, ranges, top_n=5)

    for r in results:
        assert r.profile.stop_loss_pct == r.params["stop_loss_pct"]
        assert isinstance(r, OptimizationResult)
