"""Entry confirmation engine v1 — quality filters before opening positions.

4 confirmation rules:
  1. weak_momentum — MACD bearish + negative price trend
  2. no_chasing — price extended near upper Bollinger + strong rally
  3. weak_volume — volume below threshold vs average
  4. stale_signal — recommendation too old

All must pass for entry to proceed.
"""

from datetime import datetime, timedelta, timezone

from app.indicators.schemas import IndicatorSnapshot
from app.logging_config import get_logger

log = get_logger(__name__)

# Thresholds (normal mode)
CHASING_BB_POSITION = 0.85
CHASING_CHANGE_PCT = 4.0
VOLUME_MIN_RATIO = 0.8
SIGNAL_MAX_AGE_CRYPTO_H = 6
SIGNAL_MAX_AGE_STOCK_H = 12

# Risk-off tightened thresholds
RISKOFF_CHASING_BB = 0.75
RISKOFF_CHASING_CHANGE = 2.5
RISKOFF_VOLUME_RATIO = 1.0


def check_confirmations(
    indicators: IndicatorSnapshot | None,
    change_24h_pct: float | None,
    avg_volume: float | None,
    latest_volume: float | None,
    rec_generated_at: datetime | None,
    asset_class: str,
    regime: str,
    now: datetime | None = None,
) -> dict:
    """Run all confirmation checks.

    Returns:
        {"allowed": bool, "reason_codes": [...], "reason_text": str, "context": {...}}
    """
    now = now or datetime.now(timezone.utc)
    reasons = []
    context = {}
    risk_off = regime == "risk_off"

    # ── 1. Momentum confirmation ──────────────────
    if indicators and indicators.macd:
        hist = indicators.macd.histogram
        context["macd_histogram"] = round(hist, 4)
        context["change_24h_pct"] = change_24h_pct

        if hist < 0 and (change_24h_pct or 0) < -1.5:
            reasons.append("weak_momentum")

    # ── 2. No-chasing filter ─────────────────────
    if indicators and indicators.bollinger and indicators.close:
        bb = indicators.bollinger
        band_range = bb.upper - bb.lower
        if band_range > 0:
            bb_pos = (indicators.close - bb.lower) / band_range
            context["bollinger_position"] = round(bb_pos, 3)

            bb_thresh = RISKOFF_CHASING_BB if risk_off else CHASING_BB_POSITION
            chg_thresh = RISKOFF_CHASING_CHANGE if risk_off else CHASING_CHANGE_PCT

            if bb_pos > bb_thresh and (change_24h_pct or 0) > chg_thresh:
                reasons.append("no_chasing")

    # ── 3. Volume confirmation ────────────────────
    if avg_volume and latest_volume and avg_volume > 0:
        vol_ratio = latest_volume / avg_volume
        context["volume_ratio"] = round(vol_ratio, 3)

        vol_thresh = RISKOFF_VOLUME_RATIO if risk_off else VOLUME_MIN_RATIO
        if vol_ratio < vol_thresh:
            reasons.append("weak_volume")

    # ── 4. Fresh signal confirmation ──────────────
    if rec_generated_at:
        age_h = (now - rec_generated_at).total_seconds() / 3600
        context["signal_age_hours"] = round(age_h, 1)

        max_age = SIGNAL_MAX_AGE_CRYPTO_H if asset_class == "crypto" else SIGNAL_MAX_AGE_STOCK_H
        if age_h > max_age:
            reasons.append("stale_signal")

    allowed = len(reasons) == 0
    reason_text = ""
    if reasons:
        parts = {
            "weak_momentum": "bearish momentum (MACD + negative trend)",
            "no_chasing": "price extended near upper band",
            "weak_volume": "volume below confirmation threshold",
            "stale_signal": "recommendation signal is stale",
        }
        reason_text = "Entry blocked: " + "; ".join(parts.get(r, r) for r in reasons) + "."

    if not allowed:
        log.info("portfolio.entry_confirmation_blocked", reasons=reasons)
    else:
        log.debug("portfolio.entry_confirmation_passed")

    return {
        "allowed": allowed,
        "reason_codes": reasons,
        "reason_text": reason_text,
        "context": context,
    }
