"""Recommendation scoring engine — rule-based signal evaluation.

Each signal extractor returns a sub-score in [-1.0, +1.0].
Composite score is weighted sum, normalized to 0-100.

Scoring version history:
  v1: Initial weights and thresholds (candidate_buy >= 70)
  v2: Calibrated weights + lowered candidate_buy to 63
      - MACD 0.20→0.15, volume 0.10→0.05 (weak signals)
      - volatility 0.05→0.10, price_trend 0.15→0.20 (underweighted)
"""

SCORING_VERSION = "v2"

from dataclasses import dataclass

from app.indicators.schemas import BollingerOut, IndicatorSnapshot, MACDOut


@dataclass
class SignalScore:
    """Score from a single signal."""
    name: str
    score: float  # -1.0 to +1.0
    weight: float
    detail: str


@dataclass
class ScoringResult:
    """Full scoring output for an asset."""
    composite_score: float  # 0-100
    recommendation_type: str
    confidence: str
    risk_level: str
    rationale_summary: str
    signal_breakdown: dict
    signals: list[SignalScore]


# ── Signal weights ──────────────────────────────

WEIGHTS = {
    "rsi": 0.25,
    "macd": 0.15,
    "bollinger": 0.15,
    "price_trend": 0.20,
    "volume": 0.05,
    "anomaly": 0.10,
    "volatility": 0.10,
}


# ── Signal extractors ───────────────────────────

def score_rsi(rsi: float | None) -> SignalScore:
    if rsi is None:
        return SignalScore("rsi", 0.0, WEIGHTS["rsi"], "no data")

    if rsi < 25:
        s, d = 1.0, f"strongly oversold ({rsi:.0f})"
    elif rsi < 30:
        s, d = 0.8, f"oversold ({rsi:.0f})"
    elif rsi < 40:
        s, d = 0.4, f"mildly oversold ({rsi:.0f})"
    elif rsi <= 60:
        s, d = 0.0, f"neutral ({rsi:.0f})"
    elif rsi <= 70:
        s, d = -0.4, f"mildly overbought ({rsi:.0f})"
    elif rsi <= 80:
        s, d = -0.8, f"overbought ({rsi:.0f})"
    else:
        s, d = -1.0, f"strongly overbought ({rsi:.0f})"

    return SignalScore("rsi", s, WEIGHTS["rsi"], d)


def score_macd(macd: MACDOut | None) -> SignalScore:
    if macd is None:
        return SignalScore("macd", 0.0, WEIGHTS["macd"], "no data")

    hist = macd.histogram
    if hist > 0:
        # Positive histogram — bullish
        magnitude = min(abs(hist) / max(abs(macd.macd), 0.01), 1.0)
        s = 0.3 + 0.7 * magnitude
        d = f"bullish (hist={hist:.4f})"
    else:
        magnitude = min(abs(hist) / max(abs(macd.macd), 0.01), 1.0)
        s = -(0.3 + 0.7 * magnitude)
        d = f"bearish (hist={hist:.4f})"

    return SignalScore("macd", round(s, 4), WEIGHTS["macd"], d)


def score_bollinger(bb: BollingerOut | None, close: float | None) -> SignalScore:
    if bb is None or close is None or bb.width == 0:
        return SignalScore("bollinger", 0.0, WEIGHTS["bollinger"], "no data")

    # Position within bands: 0 = at lower, 1 = at upper
    band_range = bb.upper - bb.lower
    if band_range <= 0:
        return SignalScore("bollinger", 0.0, WEIGHTS["bollinger"], "bands collapsed")

    position = (close - bb.lower) / band_range  # 0.0 to 1.0

    if position < 0.15:
        s, d = 0.8, f"near lower band ({position:.0%})"
    elif position < 0.30:
        s, d = 0.4, f"lower zone ({position:.0%})"
    elif position <= 0.70:
        s, d = 0.0, f"middle zone ({position:.0%})"
    elif position <= 0.85:
        s, d = -0.4, f"upper zone ({position:.0%})"
    else:
        s, d = -0.7, f"near upper band ({position:.0%})"

    return SignalScore("bollinger", s, WEIGHTS["bollinger"], d)


def score_price_trend(change_24h_pct: float | None) -> SignalScore:
    if change_24h_pct is None:
        return SignalScore("price_trend", 0.0, WEIGHTS["price_trend"], "no data")

    c = change_24h_pct
    if c > 10:
        s, d = -0.3, f"strong rally +{c:.1f}% (risky entry)"
    elif c > 3:
        s, d = 0.4, f"bullish +{c:.1f}%"
    elif c > 0.5:
        s, d = 0.2, f"mildly positive +{c:.1f}%"
    elif c >= -0.5:
        s, d = 0.0, f"flat {c:+.1f}%"
    elif c >= -3:
        s, d = -0.1, f"mildly negative {c:.1f}%"
    elif c >= -8:
        s, d = -0.3, f"declining {c:.1f}%"
    else:
        s, d = -0.5, f"sharp decline {c:.1f}%"

    return SignalScore("price_trend", s, WEIGHTS["price_trend"], d)


def score_volume(avg_volume: float | None, latest_volume: float | None) -> SignalScore:
    if avg_volume is None or latest_volume is None or avg_volume <= 0:
        return SignalScore("volume", 0.0, WEIGHTS["volume"], "no data")

    ratio = latest_volume / avg_volume

    if ratio > 2.0:
        s, d = 0.4, f"high volume ({ratio:.1f}x avg)"
    elif ratio > 1.3:
        s, d = 0.2, f"above avg ({ratio:.1f}x)"
    elif ratio > 0.7:
        s, d = 0.0, f"normal ({ratio:.1f}x)"
    else:
        s, d = -0.2, f"low volume ({ratio:.1f}x)"

    return SignalScore("volume", s, WEIGHTS["volume"], d)


def score_anomaly(unresolved_count: int, has_rsi_extreme_oversold: bool) -> SignalScore:
    if unresolved_count == 0:
        return SignalScore("anomaly", 0.0, WEIGHTS["anomaly"], "none active")

    if has_rsi_extreme_oversold:
        return SignalScore("anomaly", 0.4, WEIGHTS["anomaly"],
                           f"{unresolved_count} anomalies (includes RSI oversold)")

    return SignalScore("anomaly", -0.2, WEIGHTS["anomaly"],
                       f"{unresolved_count} anomalies active")


def score_volatility(bb_width: float | None, asset_class: str) -> SignalScore:
    base_risk = 0.0 if asset_class == "stock" else -0.1  # crypto inherently riskier

    if bb_width is None:
        return SignalScore("volatility", base_risk, WEIGHTS["volatility"], f"no data ({asset_class})")

    # High width = high volatility = risky
    if bb_width > 0.10:
        s = base_risk - 0.4
        d = f"high volatility (BB width={bb_width:.4f})"
    elif bb_width > 0.05:
        s = base_risk - 0.1
        d = f"moderate volatility (BB width={bb_width:.4f})"
    else:
        s = base_risk + 0.1
        d = f"low volatility (BB width={bb_width:.4f})"

    return SignalScore("volatility", max(-1.0, min(1.0, s)), WEIGHTS["volatility"], d)


# ── Composite scoring ────────────────────────────

def compute_recommendation(
    indicators: IndicatorSnapshot | None,
    change_24h_pct: float | None,
    avg_volume: float | None,
    latest_volume: float | None,
    unresolved_anomalies: int,
    has_rsi_extreme_oversold: bool,
    asset_class: str,
    asset_symbol: str,
) -> ScoringResult:
    """Compute composite recommendation from all signals."""

    rsi_val = indicators.rsi_14 if indicators else None
    macd_val = indicators.macd if indicators else None
    bb_val = indicators.bollinger if indicators else None
    close_val = indicators.close if indicators else None
    bb_width = bb_val.width if bb_val else None

    signals = [
        score_rsi(rsi_val),
        score_macd(macd_val),
        score_bollinger(bb_val, close_val),
        score_price_trend(change_24h_pct),
        score_volume(avg_volume, latest_volume),
        score_anomaly(unresolved_anomalies, has_rsi_extreme_oversold),
        score_volatility(bb_width, asset_class),
    ]

    # Weighted sum: range [-1.0, +1.0]
    raw = sum(s.score * s.weight for s in signals)
    # Normalize to 0-100 (raw -1 → 0, raw 0 → 50, raw +1 → 100)
    composite = round(max(0.0, min(100.0, (raw + 1.0) * 50.0)), 2)

    # Classification (v2: lowered candidate_buy from 70 to 63)
    if composite >= 63:
        rec_type = "candidate_buy"
    elif composite >= 55:
        rec_type = "watch_only"
    elif composite >= 40:
        rec_type = "neutral"
    else:
        rec_type = "avoid"

    # Confidence: how aligned are the signals?
    positive = sum(1 for s in signals if s.score > 0.1)
    negative = sum(1 for s in signals if s.score < -0.1)
    with_data = sum(1 for s in signals if "no data" not in s.detail)
    if with_data == 0:
        confidence = "low"
    elif positive >= 5 or negative >= 5:
        confidence = "high"
    elif positive >= 3 or negative >= 3:
        confidence = "medium"
    else:
        confidence = "low"

    # Risk level
    if asset_class == "crypto" and (bb_width or 0) > 0.08:
        risk = "high"
    elif asset_class == "crypto":
        risk = "medium"
    elif (bb_width or 0) > 0.06:
        risk = "medium"
    else:
        risk = "low"

    if unresolved_anomalies >= 3:
        risk = "high"

    # Rationale
    top_signals = sorted(signals, key=lambda s: abs(s.score), reverse=True)[:3]
    rationale_parts = []
    for s in top_signals:
        if s.score > 0.1:
            rationale_parts.append(f"{s.name}: {s.detail} (bullish)")
        elif s.score < -0.1:
            rationale_parts.append(f"{s.name}: {s.detail} (bearish)")

    if not rationale_parts:
        rationale = f"Mixed signals for {asset_symbol} — no strong directional bias."
    else:
        direction = "bullish" if composite >= 55 else "bearish" if composite < 40 else "neutral"
        rationale = (
            f"Technical signals lean {direction} for {asset_symbol}. "
            + "; ".join(rationale_parts) + "."
        )

    breakdown = {
        s.name: {"score": round(s.score, 4), "weight": s.weight, "detail": s.detail}
        for s in signals
    }

    return ScoringResult(
        composite_score=composite,
        recommendation_type=rec_type,
        confidence=confidence,
        risk_level=risk,
        rationale_summary=rationale,
        signal_breakdown=breakdown,
        signals=signals,
    )
