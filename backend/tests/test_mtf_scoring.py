"""Tests for multi-timeframe confluence scoring — marketpulse-task-2026-04-01-0015."""

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from app.indicators.schemas import BollingerOut, IndicatorSnapshot, MACDOut
from app.recommendations.scoring import (
    WEIGHTS,
    SignalScore,
    compute_recommendation,
    score_mtf_confluence,
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


# ── score_mtf_confluence unit tests ─────────────────

class TestScoreMtfConfluence:
    """Tests for the score_mtf_confluence() function."""

    def test_none_returns_zero(self) -> None:
        result = score_mtf_confluence(None)
        assert result.score == 0.0
        assert result.name == "mtf_confluence"
        assert "insufficient data" in result.detail

    def test_empty_dict_returns_zero(self) -> None:
        result = score_mtf_confluence({})
        assert result.score == 0.0
        assert "insufficient data" in result.detail

    def test_single_timeframe_returns_zero(self) -> None:
        result = score_mtf_confluence({"1h": _snap()})
        assert result.score == 0.0
        assert "insufficient data" in result.detail

    def test_none_values_insufficient(self) -> None:
        result = score_mtf_confluence({"1h": _snap(), "4h": None, "1d": None})
        assert result.score == 0.0

    def test_return_type(self) -> None:
        mtf = {"1h": _snap(), "4h": _snap()}
        result = score_mtf_confluence(mtf)
        assert isinstance(result, SignalScore)
        assert result.name == "mtf_confluence"
        assert result.weight == WEIGHTS["mtf_confluence"]

    def test_score_in_range(self) -> None:
        mtf = {
            "1h": _snap(rsi=20, macd_hist=1.0, close=91.0),
            "4h": _snap(rsi=25, macd_hist=0.5, close=92.0),
            "1d": _snap(rsi=28, macd_hist=0.3, close=91.5),
        }
        result = score_mtf_confluence(mtf)
        assert -1.0 <= result.score <= 1.0

    def test_bullish_confluence_4h_1d_oversold(self) -> None:
        """RSI oversold on both 4h and 1d → strongly positive (>0.5)."""
        mtf = {
            "4h": _snap(rsi=20, macd_hist=1.0, close=91.0),
            "1d": _snap(rsi=25, macd_hist=0.8, close=91.5),
        }
        result = score_mtf_confluence(mtf)
        assert result.score > 0.5, f"Expected >0.5, got {result.score}"

    def test_bearish_overrides_1h_bullish(self) -> None:
        """RSI oversold on 1h only, overbought on 4h and 1d → negative."""
        mtf = {
            "1h": _snap(rsi=20, macd_hist=1.0, close=91.0),
            "4h": _snap(rsi=80, macd_hist=-1.0, close=109.0),
            "1d": _snap(rsi=75, macd_hist=-0.5, close=108.0),
        }
        result = score_mtf_confluence(mtf)
        assert result.score < 0.0, f"Expected <0, got {result.score}"

    def test_all_bearish(self) -> None:
        """All timeframes bearish → strongly negative."""
        mtf = {
            "1h": _snap(rsi=80, macd_hist=-1.0, close=109.0),
            "4h": _snap(rsi=85, macd_hist=-2.0, close=110.0),
            "1d": _snap(rsi=75, macd_hist=-0.8, close=108.5),
        }
        result = score_mtf_confluence(mtf)
        assert result.score < -0.5

    def test_mixed_signals_near_zero(self) -> None:
        """Neutral indicators across timeframes → near zero."""
        mtf = {
            "1h": _snap(rsi=50, macd_hist=0.0, close=100.0),
            "4h": _snap(rsi=50, macd_hist=0.0, close=100.0),
            "1d": _snap(rsi=50, macd_hist=0.0, close=100.0),
        }
        result = score_mtf_confluence(mtf)
        assert result.score == 0.0

    def test_unknown_timeframe_ignored(self) -> None:
        """Timeframes not in MTF_TIMEFRAME_WEIGHTS are ignored."""
        mtf = {
            "5m": _snap(rsi=20, macd_hist=5.0, close=91.0),
            "1h": _snap(rsi=50, macd_hist=0.0, close=100.0),
        }
        # Only "1h" is valid → insufficient (need >=2)
        result = score_mtf_confluence(mtf)
        assert result.score == 0.0

    def test_detail_contains_per_timeframe(self) -> None:
        mtf = {
            "1h": _snap(rsi=20),
            "4h": _snap(rsi=80),
        }
        result = score_mtf_confluence(mtf)
        assert "1h:" in result.detail
        assert "4h:" in result.detail


# ── Weights validation ──────────────────────────────

class TestWeights:
    """Ensure weight invariants hold."""

    def test_weights_sum_to_one(self) -> None:
        total = sum(WEIGHTS.values())
        assert abs(total - 1.00) < 1e-9, f"Weights sum to {total}, expected 1.00"

    def test_mtf_confluence_weight(self) -> None:
        assert WEIGHTS["mtf_confluence"] == 0.08

    def test_ten_signals(self) -> None:
        assert len(WEIGHTS) == 10


# ── compute_recommendation integration tests ────────

class TestComputeRecommendationMtf:
    """Tests for MTF integration in compute_recommendation."""

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

    def test_without_mtf_backward_compatible(self) -> None:
        """Calling without mtf_indicators works (backward compatible)."""
        result = compute_recommendation(**self._base_kwargs())
        assert result.composite_score >= 0
        assert result.recommendation_type in (
            "candidate_buy", "watch_only", "neutral", "avoid"
        )
        # mtf_confluence should be in signals with score=0.0
        mtf_sig = [s for s in result.signals if s.name == "mtf_confluence"]
        assert len(mtf_sig) == 1
        assert mtf_sig[0].score == 0.0

    def test_mtf_none_same_as_omitted(self) -> None:
        """Passing mtf_indicators=None is equivalent to omitting it."""
        base = self._base_kwargs()
        result_omit = compute_recommendation(**base)
        result_none = compute_recommendation(**base, mtf_indicators=None)
        assert result_omit.composite_score == result_none.composite_score

    def test_bullish_mtf_increases_score(self) -> None:
        """Strong bullish MTF data should increase composite score."""
        base = self._base_kwargs()
        result_no_mtf = compute_recommendation(**base)

        bullish_mtf = {
            "1h": _snap(rsi=20, macd_hist=2.0, close=91.0),
            "4h": _snap(rsi=25, macd_hist=1.5, close=91.5),
            "1d": _snap(rsi=28, macd_hist=1.0, close=92.0),
        }
        result_with_mtf = compute_recommendation(**base, mtf_indicators=bullish_mtf)

        assert result_with_mtf.composite_score > result_no_mtf.composite_score

    def test_bearish_mtf_decreases_score(self) -> None:
        """Strong bearish MTF data should decrease composite score."""
        base = self._base_kwargs()
        result_no_mtf = compute_recommendation(**base)

        bearish_mtf = {
            "1h": _snap(rsi=80, macd_hist=-2.0, close=109.0),
            "4h": _snap(rsi=85, macd_hist=-1.5, close=110.0),
            "1d": _snap(rsi=75, macd_hist=-1.0, close=108.0),
        }
        result_with_mtf = compute_recommendation(**base, mtf_indicators=bearish_mtf)

        assert result_with_mtf.composite_score < result_no_mtf.composite_score

    def test_ten_signals_in_result(self) -> None:
        """compute_recommendation should produce exactly 10 signals."""
        result = compute_recommendation(**self._base_kwargs())
        assert len(result.signals) == 10

    def test_confluence_in_breakdown(self) -> None:
        """mtf_confluence must appear in signal_breakdown dict."""
        result = compute_recommendation(**self._base_kwargs())
        assert "mtf_confluence" in result.signal_breakdown
        assert "score" in result.signal_breakdown["mtf_confluence"]
        assert "weight" in result.signal_breakdown["mtf_confluence"]
