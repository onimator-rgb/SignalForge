"""Tests for MFI (Money Flow Index) calculator."""

import pandas as pd

from app.indicators.calculators.mfi import calc_mfi


def test_mfi_insufficient_data() -> None:
    """Returns None when fewer than period+1 bars provided."""
    n = 14  # need 15 (period+1)
    highs = pd.Series([110.0] * n)
    lows = pd.Series([90.0] * n)
    closes = pd.Series([100.0] * n)
    volumes = pd.Series([1000.0] * n)
    assert calc_mfi(highs, lows, closes, volumes, period=14) is None


def test_mfi_returns_float_in_range() -> None:
    """Returns a float in [0, 100] for valid input."""
    n = 30
    highs = pd.Series([100.0 + i * 0.5 + 2 for i in range(n)])
    lows = pd.Series([100.0 + i * 0.5 - 2 for i in range(n)])
    closes = pd.Series([100.0 + i * 0.5 for i in range(n)])
    volumes = pd.Series([1000.0 + i * 10 for i in range(n)])
    result = calc_mfi(highs, lows, closes, volumes, period=14)
    assert result is not None
    assert isinstance(result, float)
    assert 0 <= result <= 100


def test_mfi_strong_uptrend() -> None:
    """MFI > 50 for a strong uptrend with rising prices and volume."""
    n = 30
    highs = pd.Series([50.0 + i * 3.0 + 2 for i in range(n)])
    lows = pd.Series([50.0 + i * 3.0 - 2 for i in range(n)])
    closes = pd.Series([50.0 + i * 3.0 for i in range(n)])
    volumes = pd.Series([1000.0 + i * 100 for i in range(n)])
    result = calc_mfi(highs, lows, closes, volumes, period=14)
    assert result is not None
    assert result > 50, f"Expected MFI > 50 for uptrend, got {result}"


def test_mfi_strong_downtrend() -> None:
    """MFI < 50 for a strong downtrend with falling prices and volume."""
    n = 30
    highs = pd.Series([500.0 - i * 3.0 + 2 for i in range(n)])
    lows = pd.Series([500.0 - i * 3.0 - 2 for i in range(n)])
    closes = pd.Series([500.0 - i * 3.0 for i in range(n)])
    volumes = pd.Series([1000.0 + i * 100 for i in range(n)])
    result = calc_mfi(highs, lows, closes, volumes, period=14)
    assert result is not None
    assert result < 50, f"Expected MFI < 50 for downtrend, got {result}"


def test_mfi_all_negative_flows_zero() -> None:
    """Returns 100.0 when all flows are positive (negative_sum == 0)."""
    n = 20
    # Strictly rising typical price -> all flows are positive
    highs = pd.Series([100.0 + i * 2.0 + 1 for i in range(n)])
    lows = pd.Series([100.0 + i * 2.0 - 1 for i in range(n)])
    closes = pd.Series([100.0 + i * 2.0 for i in range(n)])
    volumes = pd.Series([1000.0] * n)
    result = calc_mfi(highs, lows, closes, volumes, period=14)
    assert result == 100.0


def test_mfi_registered_in_init() -> None:
    """calc_mfi is exported from calculators __init__.py."""
    from app.indicators.calculators import calc_mfi as cm

    assert cm is calc_mfi
