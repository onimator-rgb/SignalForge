"""Market regime calculator — breadth + ADX + price-trend regime detection.

Computes risk_on / neutral / risk_off from current system data.
No ML, no external data — pure internal signal aggregation.
"""

import statistics

import pandas as pd
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.anomalies.models import AnomalyEvent
from app.assets.models import Asset
from app.indicators.calculators.adx import calc_adx
from app.live.cache import get_all_prices
from app.logging_config import get_logger
from app.market_data.models import PriceBar
from app.recommendations.models import Recommendation

log = get_logger(__name__)


async def _calc_avg_adx(db: AsyncSession) -> float | None:
    """Calculate average ADX across all active assets.

    Fetches last 30 bars (1h) per active asset, computes ADX for each,
    and returns the mean. Returns None if insufficient data.
    """
    active_res = await db.execute(
        select(Asset.id).where(Asset.is_active.is_(True))
    )
    asset_ids = [row[0] for row in active_res.all()]
    if not asset_ids:
        return None

    adx_values: list[float] = []
    for asset_id in asset_ids:
        try:
            bars_res = await db.execute(
                select(PriceBar)
                .where(PriceBar.asset_id == asset_id, PriceBar.interval == "1h")
                .order_by(PriceBar.time.desc())
                .limit(30)
            )
            bars = list(bars_res.scalars().all())
            if len(bars) < 16:  # need at least period+2 bars for ADX
                continue
            bars.reverse()  # oldest first
            highs = pd.Series([float(b.high) for b in bars])
            lows = pd.Series([float(b.low) for b in bars])
            closes = pd.Series([float(b.close) for b in bars])
            result = calc_adx(highs, lows, closes, period=14)
            if result is not None:
                adx_values.append(result.adx)
        except Exception:
            log.warning("strategy.adx_calc_failed", asset_id=str(asset_id))
            continue

    if not adx_values:
        return None
    return round(statistics.mean(adx_values), 2)


def _calc_price_trend_score(cache: dict) -> int:
    """Score based on median 24h price change from live cache.

    Returns +1 if median > 2%, -1 if median < -2%, else 0.
    """
    changes = [
        p.change_24h_pct for p in cache.values()
        if p.change_24h_pct is not None
    ]
    if not changes:
        return 0
    median = statistics.median(changes)
    if median > 2.0:
        return 1
    if median < -2.0:
        return -1
    return 0


async def calculate_regime(db: AsyncSession) -> dict:
    """Calculate current market regime from system data.

    Returns:
        dict with regime, inputs, and reasoning.
    """
    # 1. Breadth: % of assets with positive 24h change (from live cache)
    cache = get_all_prices()
    positive = sum(1 for p in cache.values() if p.change_24h_pct and p.change_24h_pct > 0)
    total_cached = len(cache) or 1
    breadth_ratio = round(positive / total_cached, 3) if cache else 0.5

    # 2. Average active recommendation score
    avg_score_res = await db.execute(
        select(func.avg(Recommendation.score)).where(Recommendation.status == "active")
    )
    avg_score = float(avg_score_res.scalar_one() or 50)

    # 3. Buy signal count
    buy_count_res = await db.execute(
        select(func.count()).where(
            Recommendation.status == "active",
            Recommendation.recommendation_type == "candidate_buy",
        )
    )
    buy_signals = buy_count_res.scalar_one()

    # 4. Anomaly pressure
    anomaly_count_res = await db.execute(
        select(func.count()).where(AnomalyEvent.is_resolved.is_(False))
    )
    unresolved_anomalies = anomaly_count_res.scalar_one()

    # Active asset count
    active_res = await db.execute(
        select(func.count()).where(Asset.is_active.is_(True))
    )
    active_assets = active_res.scalar_one()
    anomaly_ratio = round(unresolved_anomalies / max(active_assets, 1), 3)

    # ── Regime decision ───────────────────────────
    score = 0  # -10 to +10 scale

    # Breadth contribution
    if breadth_ratio > 0.60:
        score += 3
    elif breadth_ratio > 0.45:
        score += 1
    elif breadth_ratio < 0.35:
        score -= 3
    else:
        score -= 1

    # Avg score contribution
    if avg_score > 58:
        score += 2
    elif avg_score > 52:
        score += 0
    else:
        score -= 2

    # Buy signals
    if buy_signals >= 4:
        score += 2
    elif buy_signals >= 2:
        score += 1
    elif buy_signals == 0:
        score -= 1

    # Anomaly pressure (negative = more risk)
    if anomaly_ratio > 0.30:
        score -= 2
    elif anomaly_ratio > 0.15:
        score -= 1

    # ADX trend strength
    avg_adx: float | None = None
    try:
        avg_adx = await _calc_avg_adx(db)
    except Exception:
        log.warning("strategy.adx_calculation_skipped")

    if avg_adx is not None and avg_adx > 30:
        if breadth_ratio > 0.55:
            score += 2
        elif breadth_ratio < 0.40:
            score -= 2

    # Price trend from live cache
    price_trend_score = _calc_price_trend_score(cache)
    score += price_trend_score

    # Classify
    if score >= 4:
        regime = "risk_on"
    elif score <= -3:
        regime = "risk_off"
    else:
        regime = "neutral"

    result = {
        "regime": regime,
        "score": score,
        "inputs": {
            "breadth_positive_ratio": breadth_ratio,
            "avg_recommendation_score": round(avg_score, 2),
            "buy_signal_count": buy_signals,
            "unresolved_anomalies": unresolved_anomalies,
            "anomaly_ratio": anomaly_ratio,
            "cached_prices": total_cached,
            "avg_adx": avg_adx,
            "price_trend_score": price_trend_score,
        },
    }

    log.debug("strategy.regime_calculated", regime=regime, score=score)
    return result


def get_regime_score_adjustment(regime: str) -> float:
    """Score adjustment applied to recommendations based on regime."""
    if regime == "risk_on":
        return 2.0
    elif regime == "risk_off":
        return -4.0
    return 0.0


def get_regime_position_multiplier(regime: str) -> float:
    """Position size multiplier based on regime."""
    if regime == "risk_on":
        return 1.0
    elif regime == "risk_off":
        return 0.5
    return 0.8
