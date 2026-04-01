"""VWAP (Volume-Weighted Average Price) calculator."""

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class VWAPResult:
    vwap: float


def calc_vwap(
    highs: pd.Series,
    lows: pd.Series,
    closes: pd.Series,
    volumes: pd.Series,
) -> VWAPResult | None:
    """Calculate VWAP from high, low, close, volume series.

    Args:
        highs: Series of high prices, oldest first.
        lows: Series of low prices, oldest first.
        closes: Series of close prices, oldest first.
        volumes: Series of volumes, oldest first.

    Returns:
        VWAPResult or None if fewer than 2 bars or total volume is zero.
    """
    if len(highs) < 2:
        return None

    h = highs.reset_index(drop=True).astype(float)
    l = lows.reset_index(drop=True).astype(float)
    c = closes.reset_index(drop=True).astype(float)
    v = volumes.reset_index(drop=True).astype(float)

    total_volume = v.sum()
    if total_volume == 0:
        return None

    typical_price = (h + l + c) / 3.0
    vwap = float((typical_price * v).sum() / total_volume)

    return VWAPResult(vwap=round(vwap, 4))
