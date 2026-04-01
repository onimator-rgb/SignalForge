"""Tests for VWAP calculator."""

import pandas as pd

from app.indicators.calculators.vwap import VWAPResult, calc_vwap


def test_vwap_basic() -> None:
    """VWAP computed correctly for a known dataset."""
    highs = pd.Series([12.0, 14.0, 13.0, 15.0, 16.0])
    lows = pd.Series([10.0, 11.0, 11.0, 12.0, 13.0])
    closes = pd.Series([11.0, 13.0, 12.0, 14.0, 15.0])
    volumes = pd.Series([100.0, 200.0, 150.0, 300.0, 250.0])

    # typical_price = (H+L+C)/3
    # tp = [11.0, 12.6667, 12.0, 13.6667, 14.6667]
    # tp*v = [1100, 2533.33, 1800, 4100, 3666.67]
    # sum(tp*v) = 13200.0, sum(v) = 1000
    # vwap = 13200/1000 = 13.2
    expected = round(
        sum(
            ((h + l + c) / 3) * v
            for h, l, c, v in zip(
                highs.tolist(), lows.tolist(), closes.tolist(), volumes.tolist()
            )
        )
        / sum(volumes.tolist()),
        4,
    )

    result = calc_vwap(highs, lows, closes, volumes)
    assert result is not None
    assert isinstance(result, VWAPResult)
    assert result.vwap == expected


def test_vwap_insufficient_bars() -> None:
    """Returns None when fewer than 2 bars."""
    highs = pd.Series([10.0])
    lows = pd.Series([9.0])
    closes = pd.Series([9.5])
    volumes = pd.Series([100.0])
    assert calc_vwap(highs, lows, closes, volumes) is None


def test_vwap_zero_volume() -> None:
    """Returns None when total volume is zero."""
    highs = pd.Series([10.0, 12.0, 11.0])
    lows = pd.Series([9.0, 10.0, 9.5])
    closes = pd.Series([9.5, 11.0, 10.0])
    volumes = pd.Series([0.0, 0.0, 0.0])
    assert calc_vwap(highs, lows, closes, volumes) is None


def test_vwap_single_bar_volume() -> None:
    """When only one bar has volume, VWAP equals that bar's typical price."""
    highs = pd.Series([10.0, 15.0, 12.0])
    lows = pd.Series([8.0, 12.0, 10.0])
    closes = pd.Series([9.0, 14.0, 11.0])
    volumes = pd.Series([0.0, 500.0, 0.0])

    # Only bar index 1 has volume; its typical_price = (15+12+14)/3 = 13.6667
    expected = round((15.0 + 12.0 + 14.0) / 3.0, 4)

    result = calc_vwap(highs, lows, closes, volumes)
    assert result is not None
    assert result.vwap == expected


def test_vwap_uniform_volume() -> None:
    """When all volumes are equal, VWAP equals simple average of typical prices."""
    highs = pd.Series([10.0, 20.0, 30.0, 40.0])
    lows = pd.Series([8.0, 16.0, 24.0, 32.0])
    closes = pd.Series([9.0, 18.0, 27.0, 36.0])
    volumes = pd.Series([100.0, 100.0, 100.0, 100.0])

    typical_prices = [(h + l + c) / 3.0 for h, l, c in zip(
        highs.tolist(), lows.tolist(), closes.tolist()
    )]
    expected = round(sum(typical_prices) / len(typical_prices), 4)

    result = calc_vwap(highs, lows, closes, volumes)
    assert result is not None
    assert result.vwap == expected
