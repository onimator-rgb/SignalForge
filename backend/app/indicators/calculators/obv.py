"""OBV (On-Balance Volume) calculator."""

import pandas as pd


def calc_obv(closes: pd.Series, volumes: pd.Series) -> float | None:
    """Calculate On-Balance Volume from close prices and volumes.

    Args:
        closes: Series of close prices, oldest first.
        volumes: Series of volumes, oldest first.

    Returns:
        Final cumulative OBV value as a float, or None if fewer than 2 bars.
    """
    if len(closes) < 2 or len(volumes) < 2:
        return None

    obv = 0.0
    for i in range(1, len(closes)):
        if closes.iloc[i] > closes.iloc[i - 1]:
            obv += volumes.iloc[i]
        elif closes.iloc[i] < closes.iloc[i - 1]:
            obv -= volumes.iloc[i]

    return round(obv, 2)
