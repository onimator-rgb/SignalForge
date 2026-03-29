"""Candidate ranking + allocation tiers for demo portfolio.

Produces ranking_score (0-100) and allocation_multiplier (0.0-1.0)
from existing recommendation + indicator + regime data.
Separate from recommendation score — this is a portfolio-level layer.
"""

from datetime import datetime, timezone

from app.indicators.schemas import IndicatorSnapshot
from app.logging_config import get_logger

log = get_logger(__name__)

# Allocation tiers
TIERS = [
    (80, 1.0, "top"),
    (70, 0.8, "strong"),
    (63, 0.6, "medium"),
    (0, 0.0, "skip"),
]


def compute_ranking(
    rec_score: float,
    confidence: str,
    risk_level: str,
    asset_class: str,
    regime: str,
    signal_age_hours: float,
    anomaly_count: int,
    indicators: IndicatorSnapshot | None = None,
    change_24h_pct: float | None = None,
) -> dict:
    """Compute ranking_score + allocation for a candidate.

    Returns dict with ranking_score, allocation_multiplier, tier, factors.
    """
    factors = {}

    # Base = recommendation score
    base = rec_score
    factors["base_score"] = round(base, 2)

    # Confidence bonus
    conf_bonus = {"high": 6, "medium": 2, "low": -2}.get(confidence, 0)
    factors["confidence_bonus"] = conf_bonus

    # Risk penalty
    risk_pen = {"high": -6, "medium": -1, "low": 2}.get(risk_level, 0)
    factors["risk_penalty"] = risk_pen

    # Freshness bonus (newer = better)
    if signal_age_hours < 2:
        fresh = 4
    elif signal_age_hours < 6:
        fresh = 2
    elif signal_age_hours < 12:
        fresh = 0
    else:
        fresh = -3
    factors["freshness_bonus"] = fresh

    # Anomaly pressure
    anom_pen = 0
    if anomaly_count >= 3:
        anom_pen = -4
    elif anomaly_count >= 1:
        anom_pen = -1
    factors["anomaly_penalty"] = anom_pen

    # Regime alignment
    regime_adj = 0
    if regime == "risk_on":
        regime_adj = 2
        if asset_class == "crypto":
            regime_adj = 3  # crypto benefits more from risk_on
    elif regime == "risk_off":
        regime_adj = -2
        if asset_class == "stock":
            regime_adj = 0  # stocks less penalized in risk_off
    factors["regime_adjustment"] = regime_adj

    # Price extension penalty (from Bollinger position)
    ext_pen = 0
    if indicators and indicators.bollinger and indicators.close:
        bb = indicators.bollinger
        band_range = bb.upper - bb.lower
        if band_range > 0:
            bb_pos = (indicators.close - bb.lower) / band_range
            if bb_pos > 0.80:
                ext_pen = -3
            elif bb_pos > 0.70:
                ext_pen = -1
    factors["extension_penalty"] = ext_pen

    # Composite
    ranking_score = max(0, min(100, base + conf_bonus + risk_pen + fresh + anom_pen + regime_adj + ext_pen))
    ranking_score = round(ranking_score, 2)

    # Allocation tier
    alloc = 0.0
    tier = "skip"
    for threshold, multiplier, tier_name in TIERS:
        if ranking_score >= threshold:
            alloc = multiplier
            tier = tier_name
            break

    log.debug("portfolio.ranking_computed",
              ranking_score=ranking_score, tier=tier, alloc=alloc)

    return {
        "ranking_score": ranking_score,
        "allocation_multiplier": alloc,
        "tier": tier,
        "factors": factors,
    }
