"""MFI (Money Flow Index) calculator."""

import pandas as pd


def calc_mfi(
    highs: pd.Series,
    lows: pd.Series,
    closes: pd.Series,
    volumes: pd.Series,
    period: int = 14,
) -> float | None:
    """Calculate Money Flow Index from price and volume data.

    Args:
        highs: Series of high prices, oldest first.
        lows: Series of low prices, oldest first.
        closes: Series of close prices, oldest first.
        volumes: Series of volume values, oldest first.
        period: MFI lookback period.

    Returns:
        MFI value (0-100), or None if insufficient data.
    """
    if len(closes) < period + 1:
        return None

    tp = (highs + lows + closes) / 3.0
    rmf = tp * volumes

    tp_diff = tp.diff()

    positive_flow = pd.Series(0.0, index=rmf.index)
    negative_flow = pd.Series(0.0, index=rmf.index)

    positive_flow[tp_diff > 0] = rmf[tp_diff > 0]
    negative_flow[tp_diff <= 0] = rmf[tp_diff <= 0]

    # Sum over the last `period` bars (excluding the first bar which has NaN diff)
    pos_sum = positive_flow.iloc[-period:].sum()
    neg_sum = negative_flow.iloc[-period:].sum()

    if neg_sum == 0:
        return 100.0

    ratio = pos_sum / neg_sum
    mfi = 100.0 - (100.0 / (1.0 + ratio))
    return round(mfi, 2)
