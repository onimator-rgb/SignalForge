"""Tests for CCI (Commodity Channel Index) calculator."""

import pandas as pd
import pytest

from app.indicators.calculators.cci import calc_cci


def test_cci_insufficient_data() -> None:
    """Returns None when fewer than `period` bars are provided."""
    highs = pd.Series([10.0, 11.0, 12.0])
    lows = pd.Series([9.0, 10.0, 11.0])
    closes = pd.Series([9.5, 10.5, 11.5])
    assert calc_cci(highs, lows, closes, period=20) is None


def test_cci_returns_float() -> None:
    """Valid input with enough bars returns a float."""
    n = 25
    highs = pd.Series([100.0 + i * 0.5 for i in range(n)])
    lows = pd.Series([99.0 + i * 0.5 for i in range(n)])
    closes = pd.Series([99.5 + i * 0.5 for i in range(n)])
    result = calc_cci(highs, lows, closes, period=20)
    assert isinstance(result, float)


def test_cci_uptrend_positive() -> None:
    """Strong uptrend should produce CCI > 0."""
    n = 30
    highs = pd.Series([50.0 + i * 2.0 for i in range(n)])
    lows = pd.Series([49.0 + i * 2.0 for i in range(n)])
    closes = pd.Series([49.5 + i * 2.0 for i in range(n)])
    result = calc_cci(highs, lows, closes, period=20)
    assert result is not None
    assert result > 0


def test_cci_downtrend_negative() -> None:
    """Strong downtrend should produce CCI < 0."""
    n = 30
    highs = pd.Series([150.0 - i * 2.0 for i in range(n)])
    lows = pd.Series([149.0 - i * 2.0 for i in range(n)])
    closes = pd.Series([149.5 - i * 2.0 for i in range(n)])
    result = calc_cci(highs, lows, closes, period=20)
    assert result is not None
    assert result < 0


def test_cci_flat_near_zero() -> None:
    """Flat prices should produce CCI of 0.0 (mean deviation is 0)."""
    n = 25
    highs = pd.Series([100.0] * n)
    lows = pd.Series([100.0] * n)
    closes = pd.Series([100.0] * n)
    result = calc_cci(highs, lows, closes, period=20)
    assert result == 0.0


def test_cci_extreme_overbought() -> None:
    """Rapid price rise at the end should produce CCI > 100."""
    n = 25
    # Flat for most of the period, then a sharp spike
    highs_data = [100.0] * 20 + [100.0 + i * 10.0 for i in range(1, 6)]
    lows_data = [99.0] * 20 + [99.0 + i * 10.0 for i in range(1, 6)]
    closes_data = [99.5] * 20 + [99.5 + i * 10.0 for i in range(1, 6)]
    highs = pd.Series(highs_data)
    lows = pd.Series(lows_data)
    closes = pd.Series(closes_data)
    result = calc_cci(highs, lows, closes, period=20)
    assert result is not None
    assert result > 100


def test_cci_registered_in_init() -> None:
    """calc_cci should be importable from the calculators package."""
    from app.indicators.calculators import calc_cci as imported_calc_cci

    assert imported_calc_cci is calc_cci
