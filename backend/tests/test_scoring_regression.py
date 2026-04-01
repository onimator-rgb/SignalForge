"""Regression tests for scoring engine — marketpulse-task-2026-04-01-0001.

Locks down compute_recommendation() behavior with hardcoded indicator values
that produce deterministic recommendation types and composite score ranges.
"""

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from app.indicators.schemas import BollingerOut, IndicatorSnapshot, MACDOut
from app.recommendations.scoring import compute_recommendation


# ── Helpers ─────────────────────────────────────────


def _make_snapshot(
    rsi: float | None = 50.0,
    macd_hist: float = 0.0,
    macd_line: float = 0.5,
    close: float = 100.0,
    bb_lower: float = 90.0,
    bb_upper: float = 110.0,
    bb_width: float | None = None,
    adx: float | None = None,
    plus_di: float | None = None,
    minus_di: float | None = None,
    stoch_rsi_k: float | None = None,
    stoch_rsi_d: float | None = None,
) -> IndicatorSnapshot:
    """Create a minimal IndicatorSnapshot for regression tests."""
    bb_middle = (bb_upper + bb_lower) / 2
    width = bb_width if bb_width is not None else (bb_upper - bb_lower) / bb_middle
    bb = BollingerOut(upper=bb_upper, lower=bb_lower, middle=bb_middle, width=width)
    macd = MACDOut(macd=macd_line, signal=macd_line - macd_hist, histogram=macd_hist)
    return IndicatorSnapshot(
        asset_id=uuid4(),
        asset_symbol="TEST",
        interval="1d",
        bar_time=datetime.now(timezone.utc),
        close=close,
        rsi_14=rsi,
        macd=macd,
        bollinger=bb,
        adx_14=adx,
        plus_di=plus_di,
        minus_di=minus_di,
        stoch_rsi_k=stoch_rsi_k,
        stoch_rsi_d=stoch_rsi_d,
        bars_available=100,
    )


# ── 1. Strong buy signals ──────────────────────────


def test_strong_buy_signals() -> None:
    snap = _make_snapshot(
        rsi=35,
        macd_hist=0.5,
        close=93.0,
        bb_lower=90.0,
        bb_upper=110.0,
        adx=30,
        plus_di=25,
        minus_di=10,
        stoch_rsi_k=15,
        stoch_rsi_d=18,
    )
    result = compute_recommendation(
        indicators=snap,
        change_24h_pct=3.0,
        avg_volume=1000.0,
        latest_volume=2000.0,
        unresolved_anomalies=0,
        has_rsi_extreme_oversold=True,
        asset_class="stock",
        asset_symbol="TEST",
    )
    assert result.recommendation_type == "candidate_buy"
    assert result.composite_score >= 63


# ── 2. Strong avoid signals ───────────────────────


def test_strong_avoid_signals() -> None:
    snap = _make_snapshot(
        rsi=78,
        macd_hist=-0.8,
        close=108.0,
        bb_lower=90.0,
        bb_upper=110.0,
        bb_width=0.12,
        adx=35,
        plus_di=10,
        minus_di=30,
        stoch_rsi_k=85,
        stoch_rsi_d=82,
    )
    result = compute_recommendation(
        indicators=snap,
        change_24h_pct=-5.0,
        avg_volume=1000.0,
        latest_volume=300.0,
        unresolved_anomalies=3,
        has_rsi_extreme_oversold=False,
        asset_class="stock",
        asset_symbol="TEST",
    )
    assert result.recommendation_type == "avoid"
    assert result.composite_score < 40


# ── 3. Neutral mixed signals ──────────────────────


def test_neutral_mixed_signals() -> None:
    snap = _make_snapshot(
        rsi=50,
        macd_hist=0.0,
        close=100.0,
        bb_lower=90.0,
        bb_upper=110.0,
        adx=15,
        plus_di=15,
        minus_di=15,
        stoch_rsi_k=50,
        stoch_rsi_d=50,
    )
    result = compute_recommendation(
        indicators=snap,
        change_24h_pct=0.0,
        avg_volume=1000.0,
        latest_volume=1000.0,
        unresolved_anomalies=1,
        has_rsi_extreme_oversold=False,
        asset_class="stock",
        asset_symbol="TEST",
    )
    assert result.recommendation_type in ("neutral", "watch_only")
    assert 40 <= result.composite_score < 63


# ── 4. Watch-only mild bullish ─────────────────────


def test_watch_only_mild_bullish() -> None:
    snap = _make_snapshot(
        rsi=38,
        macd_hist=0.2,
        close=96.0,
        bb_lower=90.0,
        bb_upper=110.0,
        bb_width=0.04,
        adx=26,
        plus_di=20,
        minus_di=14,
        stoch_rsi_k=25,
        stoch_rsi_d=28,
    )
    result = compute_recommendation(
        indicators=snap,
        change_24h_pct=1.5,
        avg_volume=1000.0,
        latest_volume=1400.0,
        unresolved_anomalies=0,
        has_rsi_extreme_oversold=False,
        asset_class="stock",
        asset_symbol="TEST",
    )
    assert result.recommendation_type in ("watch_only", "candidate_buy")
    assert result.composite_score >= 55


# ── 5. Determinism ─────────────────────────────────


def _determinism_call(snap: IndicatorSnapshot) -> tuple[float, str]:
    r = compute_recommendation(
        indicators=snap,
        change_24h_pct=2.0,
        avg_volume=1000.0,
        latest_volume=1500.0,
        unresolved_anomalies=0,
        has_rsi_extreme_oversold=False,
        asset_class="stock",
        asset_symbol="TEST",
    )
    return r.composite_score, r.recommendation_type


def test_determinism() -> None:
    snap = _make_snapshot(rsi=45, macd_hist=0.2, close=95.0, adx=25, plus_di=20, minus_di=15)
    results = [_determinism_call(snap) for _ in range(10)]
    scores = {r[0] for r in results}
    types = {r[1] for r in results}
    assert len(scores) == 1, f"Non-deterministic scores: {scores}"
    assert len(types) == 1, f"Non-deterministic types: {types}"


# ── 6. Score range bounds ──────────────────────────


@pytest.mark.parametrize(
    "rsi, macd_hist, change, anomalies, oversold",
    [
        (20, 1.0, 5.0, 0, True),    # extreme bullish
        (85, -1.0, -10.0, 5, False), # extreme bearish
    ],
    ids=["extreme_bullish", "extreme_bearish"],
)
def test_score_range_bounds(
    rsi: float,
    macd_hist: float,
    change: float,
    anomalies: int,
    oversold: bool,
) -> None:
    snap = _make_snapshot(rsi=rsi, macd_hist=macd_hist, close=100.0)
    result = compute_recommendation(
        indicators=snap,
        change_24h_pct=change,
        avg_volume=1000.0,
        latest_volume=1000.0,
        unresolved_anomalies=anomalies,
        has_rsi_extreme_oversold=oversold,
        asset_class="stock",
        asset_symbol="TEST",
    )
    assert 0 <= result.composite_score <= 100


# ── 7. Anomaly penalty ────────────────────────────


def test_anomaly_penalty() -> None:
    snap = _make_snapshot(rsi=35, macd_hist=0.3, close=93.0, adx=25, plus_di=20, minus_di=12)
    score_clean = compute_recommendation(
        indicators=snap, change_24h_pct=2.0, avg_volume=1000.0, latest_volume=1500.0,
        unresolved_anomalies=0, has_rsi_extreme_oversold=False,
        asset_class="stock", asset_symbol="TEST",
    ).composite_score
    score_dirty = compute_recommendation(
        indicators=snap, change_24h_pct=2.0, avg_volume=1000.0, latest_volume=1500.0,
        unresolved_anomalies=5, has_rsi_extreme_oversold=False,
        asset_class="stock", asset_symbol="TEST",
    ).composite_score
    assert score_clean > score_dirty, (
        f"Anomalies should reduce score: clean={score_clean}, dirty={score_dirty}"
    )


# ── 8. Volume impact ──────────────────────────────


def test_volume_impact() -> None:
    snap = _make_snapshot(rsi=45, macd_hist=0.2, close=100.0)
    score_high_vol = compute_recommendation(
        indicators=snap, change_24h_pct=1.0, avg_volume=1000.0, latest_volume=3000.0,
        unresolved_anomalies=0, has_rsi_extreme_oversold=False,
        asset_class="stock", asset_symbol="TEST",
    ).composite_score
    score_low_vol = compute_recommendation(
        indicators=snap, change_24h_pct=1.0, avg_volume=1000.0, latest_volume=200.0,
        unresolved_anomalies=0, has_rsi_extreme_oversold=False,
        asset_class="stock", asset_symbol="TEST",
    ).composite_score
    assert score_high_vol != score_low_vol, (
        f"Volume should affect score: high_vol={score_high_vol}, low_vol={score_low_vol}"
    )
    assert score_high_vol > score_low_vol, (
        f"Higher volume should yield higher score: high={score_high_vol}, low={score_low_vol}"
    )
