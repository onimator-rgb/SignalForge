"""MACD (Moving Average Convergence Divergence) calculator."""

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class MACDResult:
    macd: float
    signal: float
    histogram: float


def calc_macd(
    closes: pd.Series,
    fast: int = 12,
    slow: int = 26,
    signal_period: int = 9,
) -> MACDResult | None:
    """Calculate MACD from a series of close prices.

    Args:
        closes: Series of close prices, oldest first.
        fast: Fast EMA period.
        slow: Slow EMA period.
        signal_period: Signal line EMA period.

    Returns:
        MACDResult or None if insufficient data.
    """
    min_required = slow + signal_period
    if len(closes) < min_required:
        return None

    ema_fast = closes.ewm(span=fast, adjust=False).mean()
    ema_slow = closes.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal_period, adjust=False).mean()
    histogram = macd_line - signal_line

    return MACDResult(
        macd=round(float(macd_line.iloc[-1]), 4),
        signal=round(float(signal_line.iloc[-1]), 4),
        histogram=round(float(histogram.iloc[-1]), 4),
    )
