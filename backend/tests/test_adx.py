"""Tests for ADX calculator and scoring integration."""

import pandas as pd
import pytest

from app.indicators.calculators.adx import ADXResult, calc_adx
from app.recommendations.scoring import WEIGHTS, score_adx


# ── calc_adx tests ─────────────────────────────────


def test_adx_insufficient_data() -> None:
    """Returns None when fewer than 2*period (28) bars provided."""
    n = 20  # Less than 28
    highs = pd.Series([100.0 + i for i in range(n)])
    lows = pd.Series([99.0 + i for i in range(n)])
    closes = pd.Series([99.5 + i for i in range(n)])
    assert calc_adx(highs, lows, closes, period=14) is None


def test_adx_known_values() -> None:
    """Steadily rising prices should produce ADX > 25 and +DI > -DI."""
    n = 60
    # Strong uptrend: each bar higher than the last
    highs = pd.Series([100.0 + i * 2.0 for i in range(n)])
    lows = pd.Series([98.0 + i * 2.0 for i in range(n)])
    closes = pd.Series([99.0 + i * 2.0 for i in range(n)])

    result = calc_adx(highs, lows, closes, period=14)
    assert result is not None
    assert result.adx > 25, f"Expected ADX > 25 for uptrend, got {result.adx}"
    assert result.plus_di > result.minus_di, (
        f"Expected +DI > -DI for uptrend, got +DI={result.plus_di}, -DI={result.minus_di}"
    )


def test_adx_range() -> None:
    """ADX, +DI, -DI should all be between 0 and 100."""
    n = 60
    highs = pd.Series([100.0 + i * 1.5 for i in range(n)])
    lows = pd.Series([98.0 + i * 1.5 for i in range(n)])
    closes = pd.Series([99.0 + i * 1.5 for i in range(n)])

    result = calc_adx(highs, lows, closes, period=14)
    assert result is not None
    assert 0 <= result.adx <= 100
    assert 0 <= result.plus_di <= 100
    assert 0 <= result.minus_di <= 100


def test_adx_strong_downtrend() -> None:
    """Steadily falling prices should produce ADX > 25 and -DI > +DI."""
    n = 80
    highs = pd.Series([500.0 - i * 2.0 + 1.0 for i in range(n)])
    lows = pd.Series([500.0 - i * 2.0 - 1.0 for i in range(n)])
    closes = pd.Series([500.0 - i * 2.0 for i in range(n)])

    result = calc_adx(highs, lows, closes, period=14)
    assert result is not None
    assert result.adx > 25, f"Expected ADX > 25 for downtrend, got {result.adx}"
    assert result.minus_di > result.plus_di, (
        f"Expected -DI > +DI for downtrend, got +DI={result.plus_di}, -DI={result.minus_di}"
    )


def test_adx_exported_from_init() -> None:
    """ADXResult and calc_adx should be importable from calculators __init__."""
    from app.indicators.calculators import ADXResult as ADXResult2
    from app.indicators.calculators import calc_adx as calc_adx2

    assert ADXResult2 is ADXResult
    assert calc_adx2 is calc_adx


def test_adx_sideways_market() -> None:
    """Flat/oscillating prices should produce ADX < 25."""
    import random

    random.seed(42)
    n = 80
    # Random walk that stays near 100 — alternating up/down moves
    close_vals = [100.0]
    for _ in range(n - 1):
        # Mean-reverting: nudge back toward 100
        drift = (100.0 - close_vals[-1]) * 0.1
        close_vals.append(close_vals[-1] + drift + random.uniform(-1.0, 1.0))

    closes = pd.Series(close_vals)
    highs = closes + pd.Series([random.uniform(0.5, 1.5) for _ in range(n)])
    lows = closes - pd.Series([random.uniform(0.5, 1.5) for _ in range(n)])

    result = calc_adx(highs, lows, closes, period=14)
    assert result is not None
    assert result.adx < 25, f"Expected ADX < 25 for sideways market, got {result.adx}"


# ── score_adx tests ────────────────────────────────


def test_score_adx_none() -> None:
    """score_adx(None, None, None) returns score 0.0."""
    signal = score_adx(None, None, None)
    assert signal.score == 0.0
    assert signal.name == "adx"


def test_score_adx_strong_bullish() -> None:
    """ADX=40, +DI=30, -DI=15 → score +0.6."""
    signal = score_adx(40.0, 30.0, 15.0)
    assert signal.score == pytest.approx(0.6)


def test_score_adx_strong_bearish() -> None:
    """ADX=40, +DI=15, -DI=30 → score -0.6."""
    signal = score_adx(40.0, 15.0, 30.0)
    assert signal.score == pytest.approx(-0.6)


def test_score_adx_weak_trend() -> None:
    """ADX=15 → score 0.0 regardless of DI values."""
    signal = score_adx(15.0, 30.0, 20.0)
    assert signal.score == 0.0


# ── Weight validation ──────────────────────────────


def test_weights_sum() -> None:
    """WEIGHTS must sum to 1.0."""
    total = sum(WEIGHTS.values())
    assert abs(total - 1.0) < 0.001, f"WEIGHTS sum to {total}, expected 1.0"
