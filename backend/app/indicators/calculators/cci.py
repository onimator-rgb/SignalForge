"""CCI (Commodity Channel Index) calculator."""

import pandas as pd


def calc_cci(
    highs: pd.Series,
    lows: pd.Series,
    closes: pd.Series,
    period: int = 20,
) -> float | None:
    """Calculate Commodity Channel Index from price data.

    Args:
        highs: Series of high prices, oldest first.
        lows: Series of low prices, oldest first.
        closes: Series of close prices, oldest first.
        period: CCI lookback period.

    Returns:
        CCI value, or None if insufficient data.
    """
    if len(closes) < period:
        return None

    tp = (highs + lows + closes) / 3.0

    tp_window = tp.iloc[-period:]
    sma = tp_window.mean()
    mean_deviation = (tp_window - sma).abs().mean()

    if mean_deviation == 0:
        return 0.0

    cci = (tp.iloc[-1] - sma) / (0.015 * mean_deviation)
    return round(cci, 2)
