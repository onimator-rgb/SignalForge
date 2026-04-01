"""Tests for StochRSI calculator and scoring integration."""

import pandas as pd
import pytest

from app.indicators.calculators.stochrsi import StochRSIResult, calc_stochrsi
from app.recommendations.scoring import WEIGHTS, score_stochrsi


# ── calc_stochrsi tests ───────────────────────────


def test_stochrsi_insufficient_data() -> None:
    """Returns None when fewer bars than minimum required."""
    # Need rsi_period(14) + stoch_period(14) + k_smooth(3) + d_smooth(3) = 34
    closes = pd.Series([100.0 + i for i in range(30)])
    assert calc_stochrsi(closes) is None


def test_stochrsi_returns_result_for_valid_input() -> None:
    """Returns StochRSIResult with k and d in 0-100 range."""
    n = 60
    closes = pd.Series([100.0 + i * 0.5 + (i % 5) * 0.3 for i in range(n)])
    result = calc_stochrsi(closes)
    assert result is not None
    assert isinstance(result, StochRSIResult)
    assert 0 <= result.k <= 100
    assert 0 <= result.d <= 100


def test_stochrsi_strong_uptrend() -> None:
    """For monotonically rising closes, %K and %D should be above 80."""
    n = 80
    closes = pd.Series([50.0 + i * 2.0 for i in range(n)])
    result = calc_stochrsi(closes)
    assert result is not None
    assert result.k > 80, f"Expected %K > 80 for uptrend, got {result.k}"
    assert result.d > 80, f"Expected %D > 80 for uptrend, got {result.d}"


def test_stochrsi_strong_downtrend() -> None:
    """For monotonically falling closes, %K and %D should be below 20."""
    n = 80
    closes = pd.Series([500.0 - i * 2.0 for i in range(n)])
    result = calc_stochrsi(closes)
    assert result is not None
    assert result.k < 20, f"Expected %K < 20 for downtrend, got {result.k}"
    assert result.d < 20, f"Expected %D < 20 for downtrend, got {result.d}"


def test_stochrsi_sideways() -> None:
    """For sideways/oscillating data, %K and %D should be in 30-70 range."""
    import random

    random.seed(42)
    n = 80
    # Oscillating around 100 with small amplitude
    closes = pd.Series([100.0 + 2.0 * (i % 6 - 3) + random.uniform(-0.5, 0.5) for i in range(n)])
    result = calc_stochrsi(closes)
    assert result is not None
    assert 30 <= result.k <= 70, f"Expected %K in 30-70 for sideways, got {result.k}"
    assert 30 <= result.d <= 70, f"Expected %D in 30-70 for sideways, got {result.d}"


def test_stochrsi_exported_from_init() -> None:
    """StochRSIResult and calc_stochrsi are exported from calculators __init__."""
    from app.indicators.calculators import StochRSIResult as SR
    from app.indicators.calculators import calc_stochrsi as cs

    assert SR is StochRSIResult
    assert cs is calc_stochrsi


# ── score_stochrsi tests ──────────────────────────


def test_score_stochrsi_none() -> None:
    """score_stochrsi(None, None) returns score 0.0."""
    signal = score_stochrsi(None, None)
    assert signal.score == 0.0
    assert signal.name == "stoch_rsi"
    assert "no data" in signal.detail


def test_score_stochrsi_oversold() -> None:
    """StochRSI with low %K and %D returns positive score."""
    signal = score_stochrsi(15.0, 15.0)
    assert signal.score > 0, f"Expected positive score for oversold, got {signal.score}"
    assert signal.score == pytest.approx(0.7)


def test_score_stochrsi_overbought() -> None:
    """StochRSI with high %K and %D returns negative score."""
    signal = score_stochrsi(85.0, 85.0)
    assert signal.score < 0, f"Expected negative score for overbought, got {signal.score}"
    assert signal.score == pytest.approx(-0.7)


def test_score_stochrsi_neutral() -> None:
    """StochRSI in neutral zone returns score 0.0."""
    signal = score_stochrsi(50.0, 50.0)
    assert signal.score == 0.0


# ── Weight validation ─────────────────────────────


def test_weights_sum() -> None:
    """WEIGHTS must sum to 1.0 and have 10 entries."""
    assert len(WEIGHTS) == 10, f"Expected 10 weights, got {len(WEIGHTS)}"
    total = sum(WEIGHTS.values())
    assert abs(total - 1.0) < 0.001, f"WEIGHTS sum to {total}, expected 1.0"


def test_weights_contains_stoch_rsi() -> None:
    """WEIGHTS must include stoch_rsi."""
    assert "stoch_rsi" in WEIGHTS
