"""Market regime calculator — simple breadth-based regime detection.

Computes risk_on / neutral / risk_off from current system data.
No ML, no external data — pure internal signal aggregation.
"""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.anomalies.models import AnomalyEvent
from app.assets.models import Asset
from app.live.cache import get_all_prices
from app.logging_config import get_logger
from app.recommendations.models import Recommendation

log = get_logger(__name__)


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
