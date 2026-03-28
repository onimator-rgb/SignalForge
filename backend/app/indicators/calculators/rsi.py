"""RSI (Relative Strength Index) calculator."""

import pandas as pd


def calc_rsi(closes: pd.Series, period: int = 14) -> float | None:
    """Calculate RSI from a series of close prices.

    Args:
        closes: Series of close prices, oldest first.
        period: RSI lookback period.

    Returns:
        RSI value (0-100), or None if insufficient data.
    """
    if len(closes) < period + 1:
        return None

    delta = closes.diff()
    gain = delta.clip(lower=0)
    loss = (-delta).clip(lower=0)

    avg_gain = gain.iloc[1 : period + 1].mean()
    avg_loss = loss.iloc[1 : period + 1].mean()

    # Smoothed moving average for remaining bars
    for i in range(period + 1, len(delta)):
        avg_gain = (avg_gain * (period - 1) + gain.iloc[i]) / period
        avg_loss = (avg_loss * (period - 1) + loss.iloc[i]) / period

    if avg_loss == 0:
        return 100.0

    rs = avg_gain / avg_loss
    return round(100.0 - (100.0 / (1.0 + rs)), 2)
