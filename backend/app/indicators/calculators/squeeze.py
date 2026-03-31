"""Squeeze Momentum indicator — BB-inside-KC detector."""

from dataclasses import dataclass

import pandas as pd

from app.indicators.calculators.bollinger import BollingerResult, calc_bollinger


@dataclass(frozen=True)
class KeltnerResult:
    upper: float
    middle: float
    lower: float


@dataclass(frozen=True)
class SqueezeState:
    is_squeeze: bool
    momentum: float
    keltner: KeltnerResult
    bb_width: float
    kc_width: float


def calc_keltner(
    closes: pd.Series,
    highs: pd.Series,
    lows: pd.Series,
    ema_period: int = 20,
    atr_period: int = 10,
    atr_mult: float = 1.5,
) -> KeltnerResult | None:
    """Calculate Keltner Channels from close, high, low price series.

    Args:
        closes: Series of close prices, oldest first.
        highs: Series of high prices, oldest first.
        lows: Series of low prices, oldest first.
        ema_period: EMA lookback period for middle line.
        atr_period: ATR lookback period for band width.
        atr_mult: ATR multiplier for channel width.

    Returns:
        KeltnerResult or None if insufficient data.
    """
    min_required = max(ema_period, atr_period) + 1
    if len(closes) < min_required or len(highs) < min_required or len(lows) < min_required:
        return None

    close = closes.reset_index(drop=True).astype(float)
    high = highs.reset_index(drop=True).astype(float)
    low = lows.reset_index(drop=True).astype(float)

    # EMA of closes for middle line
    ema = close.ewm(span=ema_period, adjust=False).mean()
    middle = float(ema.iloc[-1])

    # True Range for ATR
    prev_close = close.shift(1)
    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1).iloc[1:]  # drop first NaN

    # ATR = SMA of True Range
    atr = tr.rolling(window=atr_period).mean()
    atr_val = float(atr.iloc[-1])

    upper = middle + atr_mult * atr_val
    lower = middle - atr_mult * atr_val

    return KeltnerResult(
        upper=round(upper, 4),
        middle=round(middle, 4),
        lower=round(lower, 4),
    )


def detect_squeeze(
    closes: pd.Series,
    highs: pd.Series,
    lows: pd.Series,
) -> SqueezeState | None:
    """Detect Bollinger Band squeeze inside Keltner Channels.

    Squeeze occurs when BB upper < KC upper AND BB lower > KC lower,
    indicating low volatility and a potential imminent breakout.

    Args:
        closes: Series of close prices, oldest first.
        highs: Series of high prices, oldest first.
        lows: Series of low prices, oldest first.

    Returns:
        SqueezeState or None if insufficient data.
    """
    bb = calc_bollinger(closes, period=20, num_std=2.0)
    if bb is None:
        return None

    kc = calc_keltner(closes, highs, lows, ema_period=20, atr_period=10, atr_mult=1.5)
    if kc is None:
        return None

    is_squeeze = (bb.upper < kc.upper) and (bb.lower > kc.lower)
    momentum = round(float(closes.iloc[-1]) - (kc.middle + bb.middle) / 2, 4)
    bb_width = round(bb.upper - bb.lower, 4)
    kc_width = round(kc.upper - kc.lower, 4)

    return SqueezeState(
        is_squeeze=is_squeeze,
        momentum=momentum,
        keltner=kc,
        bb_width=bb_width,
        kc_width=kc_width,
    )
