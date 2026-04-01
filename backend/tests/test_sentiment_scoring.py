"""Tests for sentiment signal in scoring engine — marketpulse-task-2026-04-01-0001."""

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from app.indicators.schemas import BollingerOut, IndicatorSnapshot, MACDOut
from app.recommendations.scoring import (
    WEIGHTS,
    SignalScore,
    compute_recommendation,
    score_sentiment,
)


# ── Helpers ─────────────────────────────────────────

def _snap(
    rsi: float | None = 50.0,
    macd_hist: float = 0.0,
    close: float = 100.0,
    bb_lower: float = 90.0,
    bb_upper: float = 110.0,
    interval: str = "1h",
) -> IndicatorSnapshot:
    """Create a minimal IndicatorSnapshot for testing."""
    bb = BollingerOut(
        upper=bb_upper,
        lower=bb_lower,
        middle=(bb_upper + bb_lower) / 2,
        width=(bb_upper - bb_lower) / ((bb_upper + bb_lower) / 2),
    )
    macd = MACDOut(macd=0.5, signal=0.3, histogram=macd_hist)
    return IndicatorSnapshot(
        asset_id=uuid4(),
        asset_symbol="TEST",
        interval=interval,
        bar_time=datetime.now(timezone.utc),
        close=close,
        rsi_14=rsi,
        macd=macd,
        bollinger=bb,
        bars_available=60,
    )


# ── score_sentiment unit tests ─────────────────────

class TestScoreSentiment:
    """Tests for the score_sentiment() function."""

    def test_none_returns_zero_neutral(self) -> None:
        result = score_sentiment(None)
        assert result.score == 0.0
        assert result.name == "sentiment"
        assert result.weight == WEIGHTS["sentiment"]
        assert "no data" in result.detail

    def test_positive_score(self) -> None:
        result = score_sentiment(0.8)
        assert result.score == 0.8
        assert "positive sentiment" in result.detail

    def test_negative_score(self) -> None:
        result = score_sentiment(-0.6)
        assert result.score == -0.6
        assert "negative sentiment" in result.detail

    def test_neutral_score(self) -> None:
        result = score_sentiment(0.1)
        assert "neutral sentiment" in result.detail

    def test_clamp_upper(self) -> None:
        result = score_sentiment(5.0)
        assert result.score == 1.0

    def test_clamp_lower(self) -> None:
        result = score_sentiment(-5.0)
        assert result.score == -1.0


# ── Weights validation ──────────────────────────────

class TestWeightsWithSentiment:
    """Ensure weight invariants hold after adding sentiment."""

    def test_weights_sum_to_one(self) -> None:
        total = sum(WEIGHTS.values())
        assert abs(total - 1.00) < 0.001, f"Weights sum to {total}, expected 1.00"


# ── compute_recommendation integration tests ────────

class TestComputeRecommendationSentiment:
    """Tests for sentiment integration in compute_recommendation."""

    def _base_kwargs(self) -> dict:
        """Common kwargs for compute_recommendation (neutral baseline)."""
        return dict(
            indicators=_snap(rsi=50, macd_hist=0.0, close=100.0),
            change_24h_pct=0.0,
            avg_volume=1000.0,
            latest_volume=1000.0,
            unresolved_anomalies=0,
            has_rsi_extreme_oversold=False,
            asset_class="crypto",
            asset_symbol="BTC",
        )

    def test_positive_sentiment_higher_than_negative(self) -> None:
        """Positive sentiment should produce higher composite than negative."""
        base = self._base_kwargs()
        result_pos = compute_recommendation(**base, sentiment_score=0.8)
        result_neg = compute_recommendation(**base, sentiment_score=-0.8)
        assert result_pos.composite_score > result_neg.composite_score

    def test_backward_compatible_without_sentiment(self) -> None:
        """Calling without sentiment_score works (backward compatible)."""
        result = compute_recommendation(**self._base_kwargs())
        assert result.composite_score >= 0
        assert result.recommendation_type in (
            "candidate_buy", "watch_only", "neutral", "avoid"
        )
        sent_sig = [s for s in result.signals if s.name == "sentiment"]
        assert len(sent_sig) == 1
        assert sent_sig[0].score == 0.0
