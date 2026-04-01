"""Tests for Pivot Points calculator."""

import dataclasses

import pandas as pd
import pytest

from app.indicators.calculators.pivot import PivotResult, calc_pivot_points


def test_pivot_basic() -> None:
    """Verify pivot calculations against known values."""
    # Previous bar: H=110, L=90, C=105
    # Current bar: arbitrary (should be ignored)
    highs = pd.Series([110.0, 120.0])
    lows = pd.Series([90.0, 95.0])
    closes = pd.Series([105.0, 115.0])

    result = calc_pivot_points(highs, lows, closes)
    assert result is not None

    # PP = (110 + 90 + 105) / 3 = 101.6667
    assert result.pp == pytest.approx(101.6667, abs=1e-4)
    # R1 = 2 * 101.6667 - 90 = 113.3333
    assert result.r1 == pytest.approx(113.3333, abs=1e-4)
    # S1 = 2 * 101.6667 - 110 = 93.3333
    assert result.s1 == pytest.approx(93.3333, abs=1e-4)
    # R2 = 101.6667 + (110 - 90) = 121.6667
    assert result.r2 == pytest.approx(121.6667, abs=1e-4)
    # S2 = 101.6667 - (110 - 90) = 81.6667
    assert result.s2 == pytest.approx(81.6667, abs=1e-4)
    # R3 = 110 + 2 * (101.6667 - 90) = 133.3333
    assert result.r3 == pytest.approx(133.3333, abs=1e-4)
    # S3 = 90 - 2 * (110 - 101.6667) = 73.3333
    assert result.s3 == pytest.approx(73.3333, abs=1e-4)


def test_pivot_insufficient_data() -> None:
    """Returns None when fewer than 2 bars provided."""
    highs = pd.Series([100.0])
    lows = pd.Series([90.0])
    closes = pd.Series([95.0])

    assert calc_pivot_points(highs, lows, closes) is None


def test_pivot_empty_data() -> None:
    """Returns None for empty series."""
    assert calc_pivot_points(pd.Series(dtype=float), pd.Series(dtype=float), pd.Series(dtype=float)) is None


def test_pivot_uses_previous_bar() -> None:
    """Calculation must use second-to-last bar, not the last."""
    # 3 bars: bar0, bar1 (previous), bar2 (current)
    highs = pd.Series([200.0, 110.0, 999.0])
    lows = pd.Series([180.0, 90.0, 1.0])
    closes = pd.Series([190.0, 105.0, 500.0])

    result = calc_pivot_points(highs, lows, closes)
    assert result is not None

    # Should use bar1: H=110, L=90, C=105 (same as basic test)
    assert result.pp == pytest.approx(101.6667, abs=1e-4)
    assert result.r1 == pytest.approx(113.3333, abs=1e-4)


def test_pivot_result_is_frozen() -> None:
    """PivotResult is a frozen dataclass."""
    highs = pd.Series([110.0, 120.0])
    lows = pd.Series([90.0, 95.0])
    closes = pd.Series([105.0, 115.0])

    result = calc_pivot_points(highs, lows, closes)
    assert result is not None

    with pytest.raises(dataclasses.FrozenInstanceError):
        result.pp = 999.0  # type: ignore[misc]


def test_pivot_ordering() -> None:
    """For typical data: S3 < S2 < S1 < PP < R1 < R2 < R3."""
    highs = pd.Series([110.0, 120.0])
    lows = pd.Series([90.0, 95.0])
    closes = pd.Series([105.0, 115.0])

    result = calc_pivot_points(highs, lows, closes)
    assert result is not None

    assert result.s3 < result.s2 < result.s1 < result.pp < result.r1 < result.r2 < result.r3
