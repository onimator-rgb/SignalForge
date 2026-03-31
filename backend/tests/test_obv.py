"""Tests for OBV (On-Balance Volume) calculator."""

import pandas as pd

from app.indicators.calculators import calc_obv


def test_obv_insufficient_data() -> None:
    """Returns None when fewer than 2 bars provided."""
    closes = pd.Series([100.0])
    volumes = pd.Series([1000.0])
    assert calc_obv(closes, volumes) is None


def test_obv_uptrend() -> None:
    """Monotonically increasing closes with constant volume=100 -> OBV = 400."""
    closes = pd.Series([10.0, 11.0, 12.0, 13.0, 14.0])
    volumes = pd.Series([100.0, 100.0, 100.0, 100.0, 100.0])
    result = calc_obv(closes, volumes)
    assert result == 400.0


def test_obv_downtrend() -> None:
    """Monotonically decreasing closes with constant volume=100 -> OBV = -400."""
    closes = pd.Series([14.0, 13.0, 12.0, 11.0, 10.0])
    volumes = pd.Series([100.0, 100.0, 100.0, 100.0, 100.0])
    result = calc_obv(closes, volumes)
    assert result == -400.0


def test_obv_mixed() -> None:
    """Mixed series: closes=[10,12,11,13,12], volumes=[100,150,200,100,50].

    OBV: +150 - 200 + 100 - 50 = 0.
    """
    closes = pd.Series([10.0, 12.0, 11.0, 13.0, 12.0])
    volumes = pd.Series([100.0, 150.0, 200.0, 100.0, 50.0])
    result = calc_obv(closes, volumes)
    assert result == 0.0


def test_obv_flat_close() -> None:
    """When close[i] == close[i-1], volume is not added to OBV."""
    closes = pd.Series([10.0, 10.0, 12.0])
    volumes = pd.Series([100.0, 200.0, 300.0])
    # Bar 1: same close -> no change (0)
    # Bar 2: up -> +300
    result = calc_obv(closes, volumes)
    assert result == 300.0
