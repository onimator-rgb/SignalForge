"""Stochastic RSI calculator.

Applies the stochastic oscillator formula to RSI values instead of price,
producing a more sensitive momentum oscillator (0-100).
"""

from dataclasses import dataclass

import pandas as pd

from app.indicators.calculators.rsi import calc_rsi


@dataclass(frozen=True)
class StochRSIResult:
    k: float  # %K line (0-100)
    d: float  # %D line (0-100)


def calc_stochrsi(
    closes: pd.Series,
    rsi_period: int = 14,
    stoch_period: int = 14,
    k_smooth: int = 3,
    d_smooth: int = 3,
) -> StochRSIResult | None:
    """Calculate Stochastic RSI from a series of close prices.

    Args:
        closes: Series of close prices, oldest first.
        rsi_period: RSI lookback period.
        stoch_period: Stochastic lookback period applied to RSI.
        k_smooth: SMA smoothing for %K.
        d_smooth: SMA smoothing for %D.

    Returns:
        StochRSIResult with k and d (both 0-100), or None if insufficient data.
    """
    min_bars = rsi_period + stoch_period + k_smooth + d_smooth
    if len(closes) < min_bars:
        return None

    # Compute RSI for each bar where we have enough data
    rsi_values: list[float] = []
    for i in range(rsi_period, len(closes)):
        rsi = calc_rsi(closes.iloc[: i + 1], period=rsi_period)
        if rsi is not None:
            rsi_values.append(rsi)

    rsi_series = pd.Series(rsi_values)

    if len(rsi_series) < stoch_period:
        return None

    # Stochastic formula on RSI values
    rsi_min = rsi_series.rolling(window=stoch_period).min()
    rsi_max = rsi_series.rolling(window=stoch_period).max()
    rsi_range = rsi_max - rsi_min

    # When range is 0, RSI is constant over the window.
    # Map to 100 if RSI is high (>=50), 0 if low (<50).
    raw_k = pd.Series(0.0, index=rsi_series.index)
    has_range = rsi_range > 0
    raw_k[has_range] = ((rsi_series[has_range] - rsi_min[has_range]) / rsi_range[has_range]) * 100.0
    no_range = ~has_range & rsi_min.notna()
    raw_k[no_range] = (rsi_series[no_range] >= 50).astype(float) * 100.0

    # %K = SMA of raw_k
    k_line = raw_k.rolling(window=k_smooth).mean()
    # %D = SMA of %K
    d_line = k_line.rolling(window=d_smooth).mean()

    # Drop NaNs and get last values
    k_line = k_line.dropna()
    d_line = d_line.dropna()

    if k_line.empty or d_line.empty:
        return None

    k_val = round(max(0.0, min(100.0, float(k_line.iloc[-1]))), 2)
    d_val = round(max(0.0, min(100.0, float(d_line.iloc[-1]))), 2)

    return StochRSIResult(k=k_val, d=d_val)
