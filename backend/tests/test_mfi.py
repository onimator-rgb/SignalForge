"""Tests for MFI (Money Flow Index) calculator."""

import pandas as pd
import pytest

from app.indicators.calculators.mfi import MFIResult, calc_mfi


def test_mfi_insufficient_data() -> None:
    """Returns None when fewer than period+1 bars provided."""
    n = 14  # need 15 (period+1)
    highs = pd.Series([110.0] * n)
    lows = pd.Series([90.0] * n)
    closes = pd.Series([100.0] * n)
    volumes = pd.Series([1000.0] * n)
    assert calc_mfi(highs, lows, closes, volumes, period=14) is None


def test_mfi_uptrend() -> None:
    """Monotonically increasing closes -> MFI > 70 (strong buying pressure)."""
    n = 30
    highs = pd.Series([50.0 + i * 3.0 + 2 for i in range(n)])
    lows = pd.Series([50.0 + i * 3.0 - 2 for i in range(n)])
    closes = pd.Series([50.0 + i * 3.0 for i in range(n)])
    volumes = pd.Series([1000.0] * n)
    result = calc_mfi(highs, lows, closes, volumes, period=14)
    assert result is not None
    assert isinstance(result, MFIResult)
    assert result.mfi > 70, f"Expected MFI > 70 for uptrend, got {result.mfi}"


def test_mfi_downtrend() -> None:
    """Monotonically decreasing closes -> MFI < 30 (strong selling pressure)."""
    n = 30
    highs = pd.Series([500.0 - i * 3.0 + 2 for i in range(n)])
    lows = pd.Series([500.0 - i * 3.0 - 2 for i in range(n)])
    closes = pd.Series([500.0 - i * 3.0 for i in range(n)])
    volumes = pd.Series([1000.0] * n)
    result = calc_mfi(highs, lows, closes, volumes, period=14)
    assert result is not None
    assert result.mfi < 30, f"Expected MFI < 30 for downtrend, got {result.mfi}"


def test_mfi_range() -> None:
    """MFI should always be in [0, 100] for various inputs."""
    n = 30
    highs = pd.Series([100.0 + i * 0.5 + 2 for i in range(n)])
    lows = pd.Series([100.0 + i * 0.5 - 2 for i in range(n)])
    closes = pd.Series([100.0 + i * 0.5 for i in range(n)])
    volumes = pd.Series([1000.0 + i * 10 for i in range(n)])
    result = calc_mfi(highs, lows, closes, volumes, period=14)
    assert result is not None
    assert 0 <= result.mfi <= 100


def test_mfi_known_values() -> None:
    """Hand-calculated MFI with period=2 and 3 bars."""
    # Bar 0: H=12, L=8, C=10 -> TP=10.0, RMF=10*100=1000
    # Bar 1: H=14, L=10, C=12 -> TP=12.0 (up), RMF=12*150=1800 -> positive
    # Bar 2: H=11, L=7, C=9  -> TP=9.0  (down), RMF=9*200=1800  -> negative
    # Period=2: pos_sum=1800, neg_sum=1800
    # Ratio=1.0, MFI = 100 - 100/(1+1) = 50.0
    highs = pd.Series([12.0, 14.0, 11.0])
    lows = pd.Series([8.0, 10.0, 7.0])
    closes = pd.Series([10.0, 12.0, 9.0])
    volumes = pd.Series([100.0, 150.0, 200.0])
    result = calc_mfi(highs, lows, closes, volumes, period=2)
    assert result is not None
    assert result.mfi == pytest.approx(50.0, abs=0.01)


def test_mfi_zero_negative_flow() -> None:
    """All prices increasing -> MFI should be 100.0."""
    n = 20
    highs = pd.Series([100.0 + i * 2.0 + 1 for i in range(n)])
    lows = pd.Series([100.0 + i * 2.0 - 1 for i in range(n)])
    closes = pd.Series([100.0 + i * 2.0 for i in range(n)])
    volumes = pd.Series([1000.0] * n)
    result = calc_mfi(highs, lows, closes, volumes, period=14)
    assert result is not None
    assert result.mfi == 100.0


def test_mfi_frozen_dataclass() -> None:
    """MFIResult is a frozen dataclass."""
    n = 20
    highs = pd.Series([100.0 + i * 2.0 + 1 for i in range(n)])
    lows = pd.Series([100.0 + i * 2.0 - 1 for i in range(n)])
    closes = pd.Series([100.0 + i * 2.0 for i in range(n)])
    volumes = pd.Series([1000.0] * n)
    result = calc_mfi(highs, lows, closes, volumes, period=14)
    assert result is not None
    with pytest.raises(AttributeError):
        result.mfi = 50.0  # type: ignore[misc]


def test_mfi_exported_from_init() -> None:
    """calc_mfi and MFIResult are exported from calculators __init__.py."""
    from app.indicators.calculators import MFIResult as MR
    from app.indicators.calculators import calc_mfi as cm

    assert cm is calc_mfi
    assert MR is MFIResult
