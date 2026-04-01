"""Indicator service — loads bars from DB, computes indicators on-the-fly."""

import uuid

import pandas as pd
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.indicators.calculators.adx import calc_adx
from app.indicators.calculators.bollinger import BollingerResult, calc_bollinger
from app.indicators.calculators.macd import MACDResult, calc_macd
from app.indicators.calculators.mfi import calc_mfi
from app.indicators.calculators.rsi import calc_rsi
from app.indicators.calculators.stochrsi import calc_stochrsi
from app.indicators.calculators.squeeze import KeltnerResult, calc_keltner
from app.indicators.calculators.vwap import calc_vwap
from app.indicators.schemas import BollingerOut, IndicatorHistory, IndicatorSnapshot, KeltnerOut, MACDOut
from app.logging_config import get_logger
from app.market_data.models import PriceBar

log = get_logger(__name__)

# Enough bars for all indicators: MACD needs 26+9=35, Bollinger needs 20, RSI needs 15.
# Fetching 60 gives comfortable margin.
DEFAULT_LOOKBACK = 60


async def get_indicators(
    db: AsyncSession,
    asset_id: uuid.UUID,
    asset_symbol: str,
    interval: str = "1h",
    lookback: int = DEFAULT_LOOKBACK,
) -> IndicatorSnapshot | None:
    """Compute current indicators for an asset from stored price bars.

    Returns None if no bars are available.
    """
    log.debug("indicators_calc_start", asset=asset_symbol, interval=interval)

    # Load recent bars (oldest first for pandas calculations)
    result = await db.execute(
        select(PriceBar)
        .where(PriceBar.asset_id == asset_id, PriceBar.interval == interval)
        .order_by(PriceBar.time.desc())
        .limit(lookback)
    )
    bars = list(result.scalars().all())

    if not bars:
        log.debug("indicators_no_bars", asset=asset_symbol, interval=interval)
        return None

    # Reverse to chronological order (oldest first)
    bars.reverse()

    closes = pd.Series([float(b.close) for b in bars])
    highs = pd.Series([float(b.high) for b in bars])
    lows = pd.Series([float(b.low) for b in bars])
    volumes = pd.Series([float(b.volume) for b in bars])
    latest_bar = bars[-1]

    # Calculate each indicator
    rsi_val = calc_rsi(closes, period=14)
    macd_res = calc_macd(closes, fast=12, slow=26, signal_period=9)
    bb_res = calc_bollinger(closes, period=20, num_std=2.0)
    adx_res = calc_adx(highs, lows, closes, period=14)
    mfi_val = calc_mfi(highs, lows, closes, volumes, period=14)
    stochrsi_res = calc_stochrsi(closes)
    vwap_res = calc_vwap(highs, lows, closes, volumes)
    kc_res = calc_keltner(closes, highs, lows, ema_period=20, atr_period=10, atr_mult=1.5)

    log.debug(
        "indicators_calc_done",
        asset=asset_symbol,
        bars_used=len(bars),
        rsi=rsi_val,
        has_macd=macd_res is not None,
        has_bb=bb_res is not None,
        has_adx=adx_res is not None,
        mfi=mfi_val,
        has_stochrsi=stochrsi_res is not None,
        has_vwap=vwap_res is not None,
        has_keltner=kc_res is not None,
    )

    return IndicatorSnapshot(
        asset_id=asset_id,
        asset_symbol=asset_symbol,
        interval=interval,
        bar_time=latest_bar.time,
        close=float(latest_bar.close),
        rsi_14=rsi_val,
        macd=_macd_to_out(macd_res),
        bollinger=_bb_to_out(bb_res),
        adx_14=adx_res.adx if adx_res else None,
        plus_di=adx_res.plus_di if adx_res else None,
        minus_di=adx_res.minus_di if adx_res else None,
        mfi_14=mfi_val,
        stoch_rsi_k=stochrsi_res.k if stochrsi_res else None,
        stoch_rsi_d=stochrsi_res.d if stochrsi_res else None,
        vwap=vwap_res.vwap if vwap_res else None,
        keltner=_kc_to_out(kc_res),
        bars_available=len(bars),
    )


async def get_indicator_history(
    db: AsyncSession,
    asset_id: uuid.UUID,
    asset_symbol: str,
    interval: str = "1h",
    lookback: int = DEFAULT_LOOKBACK,
) -> IndicatorHistory | None:
    """Compute rolling indicator values for sparkline display."""
    result = await db.execute(
        select(PriceBar)
        .where(PriceBar.asset_id == asset_id, PriceBar.interval == interval)
        .order_by(PriceBar.time.desc())
        .limit(lookback)
    )
    bars = list(result.scalars().all())
    if not bars:
        return None

    bars.reverse()
    closes = pd.Series([float(b.close) for b in bars])
    highs = pd.Series([float(b.high) for b in bars])
    lows = pd.Series([float(b.low) for b in bars])
    bar_times = [b.time for b in bars]

    # Rolling RSI
    rsi_series: list[float | None] = []
    for i in range(len(closes)):
        if i < 14:
            rsi_series.append(None)
        else:
            val = calc_rsi(closes[: i + 1], period=14)
            rsi_series.append(round(val, 2) if val is not None else None)

    # Rolling MACD histogram
    macd_hist: list[float | None] = []
    for i in range(len(closes)):
        if i < 35:
            macd_hist.append(None)
        else:
            res = calc_macd(closes[: i + 1])
            macd_hist.append(round(res.histogram, 4) if res else None)

    # Rolling ADX
    adx_series: list[float | None] = []
    for i in range(len(closes)):
        if i < 28:
            adx_series.append(None)
        else:
            res = calc_adx(highs[: i + 1], lows[: i + 1], closes[: i + 1], period=14)
            adx_series.append(round(res.adx, 2) if res else None)

    return IndicatorHistory(
        asset_id=asset_id,
        interval=interval,
        bars_used=len(bars),
        rsi_14=rsi_series,
        macd_histogram=macd_hist,
        adx_14=adx_series,
        bar_times=bar_times,
    )


async def get_closes_series(
    db: AsyncSession,
    asset_id: uuid.UUID,
    interval: str,
    lookback: int = DEFAULT_LOOKBACK,
) -> tuple[pd.Series, pd.Series] | None:
    """Load close and volume series for an asset. Returns (closes, volumes) oldest-first, or None."""
    result = await db.execute(
        select(PriceBar)
        .where(PriceBar.asset_id == asset_id, PriceBar.interval == interval)
        .order_by(PriceBar.time.desc())
        .limit(lookback)
    )
    bars = list(result.scalars().all())
    if not bars:
        return None

    bars.reverse()
    closes = pd.Series([float(b.close) for b in bars])
    volumes = pd.Series([float(b.volume) for b in bars])
    return closes, volumes


def _macd_to_out(res: MACDResult | None) -> MACDOut | None:
    if res is None:
        return None
    return MACDOut(macd=res.macd, signal=res.signal, histogram=res.histogram)


def _bb_to_out(res: BollingerResult | None) -> BollingerOut | None:
    if res is None:
        return None
    return BollingerOut(upper=res.upper, middle=res.middle, lower=res.lower, width=res.width)


def _kc_to_out(res: KeltnerResult | None) -> KeltnerOut | None:
    if res is None:
        return None
    return KeltnerOut(upper=res.upper, middle=res.middle, lower=res.lower)
