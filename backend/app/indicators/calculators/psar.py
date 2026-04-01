"""Parabolic SAR (Stop and Reverse) calculator."""

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class PSARResult:
    sar: float  # Current SAR value
    trend: str  # 'bullish' or 'bearish'
    af: float  # Current acceleration factor


def calc_psar(
    highs: pd.Series,
    lows: pd.Series,
    af_start: float = 0.02,
    af_increment: float = 0.02,
    af_max: float = 0.20,
) -> PSARResult | None:
    """Calculate Parabolic SAR using Welles Wilder's algorithm.

    Args:
        highs: Series of high prices, oldest first.
        lows: Series of low prices, oldest first.
        af_start: Initial acceleration factor (default 0.02).
        af_increment: AF increment on new extreme (default 0.02).
        af_max: Maximum acceleration factor (default 0.20).

    Returns:
        PSARResult or None if insufficient data (fewer than 2 bars).
    """
    if len(highs) < 2 or len(lows) < 2:
        return None

    high = highs.reset_index(drop=True).astype(float)
    low = lows.reset_index(drop=True).astype(float)
    n = len(high)

    # Initialize: assume bullish trend
    bullish = True
    sar = float(low.iloc[0])
    ep = float(high.iloc[0])  # extreme point
    af = af_start

    for i in range(1, n):
        cur_high = float(high.iloc[i])
        cur_low = float(low.iloc[i])

        # Calculate new SAR
        sar = sar + af * (ep - sar)

        if bullish:
            # SAR cannot be above the prior two lows
            if i >= 2:
                sar = min(sar, float(low.iloc[i - 1]), float(low.iloc[i - 2]))
            else:
                sar = min(sar, float(low.iloc[i - 1]))

            # Check for reversal
            if cur_low < sar:
                # Reverse to bearish
                bullish = False
                sar = ep
                ep = cur_low
                af = af_start
            else:
                # Update extreme point
                if cur_high > ep:
                    ep = cur_high
                    af = min(af + af_increment, af_max)
        else:
            # SAR cannot be below the prior two highs
            if i >= 2:
                sar = max(sar, float(high.iloc[i - 1]), float(high.iloc[i - 2]))
            else:
                sar = max(sar, float(high.iloc[i - 1]))

            # Check for reversal
            if cur_high > sar:
                # Reverse to bullish
                bullish = True
                sar = ep
                ep = cur_high
                af = af_start
            else:
                # Update extreme point
                if cur_low < ep:
                    ep = cur_low
                    af = min(af + af_increment, af_max)

    trend = "bullish" if bullish else "bearish"
    return PSARResult(
        sar=round(sar, 8),
        trend=trend,
        af=round(af, 4),
    )
