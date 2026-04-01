"""Recommendation scoring engine — rule-based signal evaluation.

Each signal extractor returns a sub-score in [-1.0, +1.0].
Composite score is weighted sum, normalized to 0-100.

Scoring version history:
  v1: Initial weights and thresholds (candidate_buy >= 70)
  v2: Calibrated weights + lowered candidate_buy to 63
      - MACD 0.20→0.15, volume 0.10→0.05 (weak signals)
      - volatility 0.05→0.10, price_trend 0.15→0.20 (underweighted)
  v3: Added MTF confluence as 10th signal (weight 0.08)
      - Redistributed weights to sum to 1.00
  v4: Added sentiment as 11th signal (weight 0.08)
      - Redistributed weights: each existing signal reduced by 0.008
      - sentiment score maps classifier [-1, 1] output directly
"""

SCORING_VERSION = "v4"

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
    "rsi": 0.132,
    "macd": 0.132,
    "bollinger": 0.132,
    "price_trend": 0.132,
    "volume": 0.042,
    "anomaly": 0.082,
    "volatility": 0.082,
    "adx": 0.082,
    "stoch_rsi": 0.032,
    "mtf_confluence": 0.072,
    "sentiment": 0.08,
}

# Timeframe weights for multi-timeframe confluence scoring
MTF_TIMEFRAME_WEIGHTS: dict[str, float] = {
    "1h": 0.20,
    "4h": 0.35,
    "1d": 0.45,
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


def score_adx(
    adx: float | None,
    plus_di: float | None,
    minus_di: float | None,
) -> SignalScore:
    if adx is None or plus_di is None or minus_di is None:
        return SignalScore("adx", 0.0, WEIGHTS["adx"], "no data")

    if adx < 20:
        return SignalScore("adx", 0.0, WEIGHTS["adx"], f"weak trend (ADX={adx:.0f})")

    bullish = plus_di > minus_di
    direction = "bullish" if bullish else "bearish"

    if adx > 50:
        s = 0.8 if bullish else -0.8
        d = f"very strong {direction} (ADX={adx:.0f}, +DI={plus_di:.0f}, -DI={minus_di:.0f})"
    elif adx >= 25:
        s = 0.6 if bullish else -0.6
        d = f"strong {direction} (ADX={adx:.0f}, +DI={plus_di:.0f}, -DI={minus_di:.0f})"
    else:
        # adx 20-25
        s = 0.3 if bullish else -0.3
        d = f"emerging {direction} (ADX={adx:.0f}, +DI={plus_di:.0f}, -DI={minus_di:.0f})"

    return SignalScore("adx", s, WEIGHTS["adx"], d)


def score_stochrsi(k: float | None, d: float | None) -> SignalScore:
    if k is None or d is None:
        return SignalScore("stoch_rsi", 0.0, WEIGHTS["stoch_rsi"], "no data")

    if k < 20 and d < 20:
        s, detail = 0.7, f"strongly oversold (%K={k:.0f}, %D={d:.0f})"
    elif k < 20 or d < 30:
        s, detail = 0.4, f"oversold (%K={k:.0f}, %D={d:.0f})"
    elif k > d and k < 50:
        s, detail = 0.3, f"bullish momentum (%K={k:.0f}, %D={d:.0f})"
    elif k > 80 and d > 80:
        s, detail = -0.7, f"strongly overbought (%K={k:.0f}, %D={d:.0f})"
    elif k > 80 or d > 70:
        s, detail = -0.4, f"overbought (%K={k:.0f}, %D={d:.0f})"
    elif k < d and k > 50:
        s, detail = -0.3, f"bearish momentum (%K={k:.0f}, %D={d:.0f})"
    else:
        s, detail = 0.0, f"neutral (%K={k:.0f}, %D={d:.0f})"

    return SignalScore("stoch_rsi", s, WEIGHTS["stoch_rsi"], detail)


# ── Sentiment signal ──────────────────────────────

def score_sentiment(sentiment_score: float | None) -> SignalScore:
    """Score based on news headline sentiment from classifier.

    The classifier returns a value in [-1, 1]. We pass it through directly
    as the signal score, clamped for safety.
    """
    if sentiment_score is None:
        return SignalScore("sentiment", 0.0, WEIGHTS["sentiment"], "no data")

    clamped = max(-1.0, min(1.0, sentiment_score))

    if clamped > 0.3:
        detail = "positive sentiment"
    elif clamped < -0.3:
        detail = "negative sentiment"
    else:
        detail = "neutral sentiment"

    return SignalScore("sentiment", clamped, WEIGHTS["sentiment"], detail)


# ── Multi-timeframe confluence ──────────────────

def _rsi_direction(rsi: float | None) -> float:
    """RSI signal direction: oversold=+1, overbought=-1, neutral=0."""
    if rsi is None:
        return 0.0
    if rsi < 30:
        return 1.0
    if rsi > 70:
        return -1.0
    return 0.0


def _macd_direction(macd: MACDOut | None) -> float:
    """MACD signal direction: histogram>0 = +1, <0 = -1."""
    if macd is None:
        return 0.0
    if macd.histogram > 0:
        return 1.0
    if macd.histogram < 0:
        return -1.0
    return 0.0


def _bollinger_direction(bb: BollingerOut | None, close: float | None) -> float:
    """Bollinger position: below lower=+1, above upper=-1, middle=0."""
    if bb is None or close is None:
        return 0.0
    band_range = bb.upper - bb.lower
    if band_range <= 0:
        return 0.0
    position = (close - bb.lower) / band_range
    if position < 0.25:
        return 1.0
    if position > 0.75:
        return -1.0
    return 0.0


def score_mtf_confluence(
    mtf_indicators: dict[str, IndicatorSnapshot | None] | None,
) -> SignalScore:
    """Score multi-timeframe signal confluence.

    Compares RSI, MACD, and Bollinger directions across 1h/4h/1d timeframes.
    Higher timeframes receive more weight. When signals agree across
    timeframes, the confluence score is strong; disagreement yields weak scores.
    """
    if mtf_indicators is None:
        return SignalScore("mtf_confluence", 0.0, WEIGHTS["mtf_confluence"],
                          "insufficient data")

    # Filter timeframes that have data and are in our weight map
    valid: dict[str, IndicatorSnapshot] = {}
    for tf, snap in mtf_indicators.items():
        if snap is not None and tf in MTF_TIMEFRAME_WEIGHTS:
            valid[tf] = snap

    if len(valid) < 2:
        return SignalScore("mtf_confluence", 0.0, WEIGHTS["mtf_confluence"],
                          "insufficient data")

    # Compute weighted agreement for each indicator type
    rsi_agreement = 0.0
    macd_agreement = 0.0
    bb_agreement = 0.0
    total_weight = sum(MTF_TIMEFRAME_WEIGHTS[tf] for tf in valid)

    per_tf_details: list[str] = []
    for tf, snap in valid.items():
        w = MTF_TIMEFRAME_WEIGHTS[tf]
        r_dir = _rsi_direction(snap.rsi_14)
        m_dir = _macd_direction(snap.macd)
        b_dir = _bollinger_direction(snap.bollinger, snap.close)

        rsi_agreement += r_dir * w
        macd_agreement += m_dir * w
        bb_agreement += b_dir * w

        per_tf_details.append(
            f"{tf}:RSI={r_dir:+.0f}/MACD={m_dir:+.0f}/BB={b_dir:+.0f}"
        )

    # Normalize by total weight of available timeframes
    rsi_agreement /= total_weight
    macd_agreement /= total_weight
    bb_agreement /= total_weight

    # Average the three indicator agreements → [-1.0, +1.0]
    confluence = (rsi_agreement + macd_agreement + bb_agreement) / 3.0
    confluence = max(-1.0, min(1.0, confluence))

    detail = f"confluence={confluence:+.3f} ({', '.join(per_tf_details)})"
    return SignalScore("mtf_confluence", round(confluence, 4),
                       WEIGHTS["mtf_confluence"], detail)


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
    adx_14: float | None = None,
    plus_di: float | None = None,
    minus_di: float | None = None,
    mtf_indicators: dict[str, IndicatorSnapshot | None] | None = None,
    sentiment_score: float | None = None,
) -> ScoringResult:
    """Compute composite recommendation from all signals."""

    rsi_val = indicators.rsi_14 if indicators else None
    macd_val = indicators.macd if indicators else None
    bb_val = indicators.bollinger if indicators else None
    close_val = indicators.close if indicators else None
    bb_width = bb_val.width if bb_val else None

    # Use ADX from indicators if not explicitly provided
    if adx_14 is None and indicators is not None:
        adx_14 = indicators.adx_14
    if plus_di is None and indicators is not None:
        plus_di = indicators.plus_di
    if minus_di is None and indicators is not None:
        minus_di = indicators.minus_di

    stoch_rsi_k = indicators.stoch_rsi_k if indicators else None
    stoch_rsi_d = indicators.stoch_rsi_d if indicators else None

    signals = [
        score_rsi(rsi_val),
        score_macd(macd_val),
        score_bollinger(bb_val, close_val),
        score_price_trend(change_24h_pct),
        score_volume(avg_volume, latest_volume),
        score_anomaly(unresolved_anomalies, has_rsi_extreme_oversold),
        score_volatility(bb_width, asset_class),
        score_adx(adx_14, plus_di, minus_di),
        score_stochrsi(stoch_rsi_k, stoch_rsi_d),
        score_mtf_confluence(mtf_indicators),
        score_sentiment(sentiment_score),
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
