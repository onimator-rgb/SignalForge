"""Fibonacci Retracement Levels calculator."""

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class FibonacciResult:
    swing_high: float
    swing_low: float
    level_0: float  # 0% retracement (= swing_low)
    level_236: float  # 23.6% retracement
    level_382: float  # 38.2% retracement
    level_500: float  # 50% retracement
    level_618: float  # 61.8% retracement
    level_786: float  # 78.6% retracement
    level_100: float  # 100% retracement (= swing_high)
    trend: str  # 'up' if swing_low before swing_high, else 'down'


def calc_fibonacci(
    highs: pd.Series,
    lows: pd.Series,
    closes: pd.Series,
    lookback: int = 20,
) -> FibonacciResult | None:
    """Calculate Fibonacci retracement levels from recent swing points.

    Args:
        highs: Series of high prices, oldest first.
        lows: Series of low prices, oldest first.
        closes: Series of close prices, oldest first.
        lookback: Number of bars to scan for swing high/low.

    Returns:
        FibonacciResult or None if insufficient data or flat market.
    """
    if len(highs) < lookback or len(lows) < lookback or len(closes) < lookback:
        return None

    recent_highs = highs.iloc[-lookback:]
    recent_lows = lows.iloc[-lookback:]

    swing_high = float(recent_highs.max())
    swing_low = float(recent_lows.min())

    if swing_high == swing_low:
        return None

    diff = swing_high - swing_low

    level_0 = round(swing_low, 2)
    level_236 = round(swing_low + 0.236 * diff, 2)
    level_382 = round(swing_low + 0.382 * diff, 2)
    level_500 = round(swing_low + 0.5 * diff, 2)
    level_618 = round(swing_low + 0.618 * diff, 2)
    level_786 = round(swing_low + 0.786 * diff, 2)
    level_100 = round(swing_high, 2)

    # Determine trend: compare index positions of swing high vs swing low
    high_idx = int(recent_highs.idxmax())
    low_idx = int(recent_lows.idxmin())
    trend = "up" if low_idx < high_idx else "down"

    return FibonacciResult(
        swing_high=round(swing_high, 2),
        swing_low=round(swing_low, 2),
        level_0=level_0,
        level_236=level_236,
        level_382=level_382,
        level_500=level_500,
        level_618=level_618,
        level_786=level_786,
        level_100=level_100,
        trend=trend,
    )
