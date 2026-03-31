"""ADX (Average Directional Index) calculator."""

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class ADXResult:
    adx: float
    plus_di: float
    minus_di: float


def calc_adx(
    highs: pd.Series,
    lows: pd.Series,
    closes: pd.Series,
    period: int = 14,
) -> ADXResult | None:
    """Calculate ADX from high, low, close price series.

    Args:
        highs: Series of high prices, oldest first.
        lows: Series of low prices, oldest first.
        closes: Series of close prices, oldest first.
        period: Smoothing period (default 14).

    Returns:
        ADXResult or None if insufficient data.
    """
    min_required = 2 * period
    if len(highs) < min_required or len(lows) < min_required or len(closes) < min_required:
        return None

    high = highs.reset_index(drop=True).astype(float)
    low = lows.reset_index(drop=True).astype(float)
    close = closes.reset_index(drop=True).astype(float)

    prev_high = high.shift(1)
    prev_low = low.shift(1)
    prev_close = close.shift(1)

    # True Range
    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

    # Directional Movement
    up_move = high - prev_high
    down_move = prev_low - low

    plus_dm = pd.Series(0.0, index=high.index)
    minus_dm = pd.Series(0.0, index=high.index)

    plus_dm = plus_dm.where(~((up_move > down_move) & (up_move > 0)), up_move)
    minus_dm = minus_dm.where(~((down_move > up_move) & (down_move > 0)), down_move)

    # Drop first row (NaN from shift)
    tr = tr.iloc[1:]
    plus_dm = plus_dm.iloc[1:]
    minus_dm = minus_dm.iloc[1:]

    # Wilder's smoothing
    def wilder_smooth(series: pd.Series, n: int) -> pd.Series:
        values = series.values
        result = [float("nan")] * len(values)
        # First value = sum of first n values
        result[n - 1] = sum(values[:n])
        for i in range(n, len(values)):
            result[i] = result[i - 1] - result[i - 1] / n + values[i]
        return pd.Series(result, index=series.index)

    smoothed_tr = wilder_smooth(tr, period)
    smoothed_plus_dm = wilder_smooth(plus_dm, period)
    smoothed_minus_dm = wilder_smooth(minus_dm, period)

    # +DI and -DI
    plus_di = 100.0 * smoothed_plus_dm / smoothed_tr
    minus_di = 100.0 * smoothed_minus_dm / smoothed_tr

    # DX
    di_sum = plus_di + minus_di
    di_diff = (plus_di - minus_di).abs()
    dx = 100.0 * di_diff / di_sum.replace(0, float("nan"))

    # ADX = Wilder's smoothed average of DX (mean-based, not sum-based)
    dx_valid = dx.dropna().reset_index(drop=True)
    if len(dx_valid) < period:
        return None

    adx_vals = [float("nan")] * len(dx_valid)
    # First ADX = simple average of first `period` DX values
    adx_vals[period - 1] = float(dx_valid.iloc[:period].mean())
    for i in range(period, len(dx_valid)):
        adx_vals[i] = (adx_vals[i - 1] * (period - 1) + float(dx_valid.iloc[i])) / period
    last_adx = pd.Series(adx_vals).dropna()
    if last_adx.empty:
        return None

    adx_val = round(float(last_adx.iloc[-1]), 2)
    plus_di_val = round(float(plus_di.dropna().iloc[-1]), 2)
    minus_di_val = round(float(minus_di.dropna().iloc[-1]), 2)

    # Clamp to valid range
    adx_val = max(0.0, min(100.0, adx_val))
    plus_di_val = max(0.0, min(100.0, plus_di_val))
    minus_di_val = max(0.0, min(100.0, minus_di_val))

    return ADXResult(adx=adx_val, plus_di=plus_di_val, minus_di=minus_di_val)
