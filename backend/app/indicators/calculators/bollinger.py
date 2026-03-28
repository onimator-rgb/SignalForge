"""Bollinger Bands calculator."""

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class BollingerResult:
    upper: float
    middle: float
    lower: float
    width: float  # (upper - lower) / middle — normalized bandwidth


def calc_bollinger(
    closes: pd.Series,
    period: int = 20,
    num_std: float = 2.0,
) -> BollingerResult | None:
    """Calculate Bollinger Bands from a series of close prices.

    Args:
        closes: Series of close prices, oldest first.
        period: SMA lookback period.
        num_std: Number of standard deviations.

    Returns:
        BollingerResult or None if insufficient data.
    """
    if len(closes) < period:
        return None

    sma = closes.rolling(window=period).mean()
    std = closes.rolling(window=period).std()

    middle = float(sma.iloc[-1])
    upper = float(sma.iloc[-1] + num_std * std.iloc[-1])
    lower = float(sma.iloc[-1] - num_std * std.iloc[-1])

    width = (upper - lower) / middle if middle != 0 else 0.0

    return BollingerResult(
        upper=round(upper, 4),
        middle=round(middle, 4),
        lower=round(lower, 4),
        width=round(width, 6),
    )
