"""Pivot Points calculator."""

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class PivotResult:
    pp: float
    r1: float
    r2: float
    r3: float
    s1: float
    s2: float
    s3: float


def calc_pivot_points(
    highs: pd.Series,
    lows: pd.Series,
    closes: pd.Series,
) -> PivotResult | None:
    """Calculate classic Pivot Points from previous period OHLC data.

    Uses the second-to-last bar (previous period) to compute pivot levels
    for the current bar.

    Args:
        highs: Series of high prices, oldest first.
        lows: Series of low prices, oldest first.
        closes: Series of close prices, oldest first.

    Returns:
        PivotResult or None if fewer than 2 bars provided.
    """
    if len(highs) < 2 or len(lows) < 2 or len(closes) < 2:
        return None

    h = float(highs.iloc[-2])
    l = float(lows.iloc[-2])
    c = float(closes.iloc[-2])

    pp = (h + l + c) / 3
    r1 = 2 * pp - l
    s1 = 2 * pp - h
    r2 = pp + (h - l)
    s2 = pp - (h - l)
    r3 = h + 2 * (pp - l)
    s3 = l - 2 * (h - pp)

    return PivotResult(
        pp=round(pp, 4),
        r1=round(r1, 4),
        r2=round(r2, 4),
        r3=round(r3, 4),
        s1=round(s1, 4),
        s2=round(s2, 4),
        s3=round(s3, 4),
    )
