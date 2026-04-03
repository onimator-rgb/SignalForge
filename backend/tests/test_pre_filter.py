"""Tests for the pre-filter system — rule-based gating before LLM calls."""

from __future__ import annotations

import pytest

from app.ai_traders.pre_filter import (
    apply_pre_filter,
    pre_filter_conservative,
    pre_filter_momentum,
    pre_filter_mean_reversion,
    pre_filter_sentiment,
    pre_filter_scalper,
    pre_filter_whale,
    pre_filter_fibonacci,
)


def _base_ctx(**overrides) -> dict:
    ctx = {
        "asset": {"symbol": "BTC"},
        "price": {"current": 65000, "change_24h_pct": 2.0, "volume_24h": 5000000,
                  "daily_closes_7d": [62000, 63000, 64000, 65000, 64500, 63800, 65000]},
        "indicators": {"composite_score": 60, "recommendation_type": "HOLD"},
        "anomalies": [],
        "timestamp": "2026-04-03T12:00:00",
    }
    ctx.update(overrides)
    return ctx


# --- Conservative ---

class TestConservativeFilter:
    def test_passes_with_good_score(self):
        ctx = _base_ctx(indicators={"composite_score": 70, "recommendation_type": "BUY"})
        result = pre_filter_conservative(ctx)
        assert result.should_analyze is True

    def test_skips_low_score(self):
        ctx = _base_ctx(indicators={"composite_score": 40, "recommendation_type": "HOLD"})
        result = pre_filter_conservative(ctx)
        assert result.should_analyze is False
        assert "score_too_low" in result.skip_reason

    def test_skips_high_anomalies(self):
        ctx = _base_ctx(anomalies=[{"type": "price_spike", "severity": "high"}])
        result = pre_filter_conservative(ctx)
        assert result.should_analyze is False
        assert "high_anomaly" in result.skip_reason

    def test_passes_existing_position(self):
        ctx = _base_ctx(
            indicators={"composite_score": 40},
            existing_position={"entry_price": 60000},
        )
        result = pre_filter_conservative(ctx)
        assert result.should_analyze is True

    def test_skips_no_price(self):
        ctx = _base_ctx(price={"current": None})
        result = pre_filter_conservative(ctx)
        assert result.should_analyze is False


# --- Momentum ---

class TestMomentumFilter:
    def test_passes_with_momentum(self):
        ctx = _base_ctx(price={"current": 65000, "change_24h_pct": 5.0})
        result = pre_filter_momentum(ctx)
        assert result.should_analyze is True

    def test_skips_flat_market(self):
        ctx = _base_ctx(price={"current": 65000, "change_24h_pct": 0.3})
        result = pre_filter_momentum(ctx)
        assert result.should_analyze is False
        assert "no_momentum" in result.skip_reason

    def test_passes_negative_momentum(self):
        ctx = _base_ctx(price={"current": 65000, "change_24h_pct": -4.0})
        result = pre_filter_momentum(ctx)
        assert result.should_analyze is True  # Momentum exists (downward)


# --- Sentiment ---

class TestSentimentFilter:
    def test_skips_without_anomalies(self):
        ctx = _base_ctx(anomalies=[])
        result = pre_filter_sentiment(ctx)
        assert result.should_analyze is False
        assert "no_anomalies" in result.skip_reason

    def test_passes_with_anomalies(self):
        ctx = _base_ctx(anomalies=[{"type": "volume_surge", "severity": "medium"}])
        result = pre_filter_sentiment(ctx)
        assert result.should_analyze is True


# --- Whale Follower ---

class TestWhaleFilter:
    def test_skips_without_volume_anomaly(self):
        ctx = _base_ctx(anomalies=[{"type": "rsi_extreme", "severity": "medium"}])
        result = pre_filter_whale(ctx)
        assert result.should_analyze is False

    def test_passes_with_volume_anomaly(self):
        ctx = _base_ctx(anomalies=[{"type": "volume_surge", "severity": "high"}])
        result = pre_filter_whale(ctx)
        assert result.should_analyze is True


# --- Scalper ---

class TestScalperFilter:
    def test_skips_with_anomalies(self):
        ctx = _base_ctx(anomalies=[{"type": "price_spike", "severity": "low"}])
        result = pre_filter_scalper(ctx)
        assert result.should_analyze is False

    def test_passes_clean_market(self):
        ctx = _base_ctx()
        result = pre_filter_scalper(ctx)
        assert result.should_analyze is True


# --- Fibonacci ---

class TestFibonacciFilter:
    def test_skips_insufficient_history(self):
        ctx = _base_ctx(price={"current": 65000, "daily_closes_7d": [65000]})
        result = pre_filter_fibonacci(ctx)
        assert result.should_analyze is False

    def test_passes_with_history(self):
        ctx = _base_ctx()
        result = pre_filter_fibonacci(ctx)
        assert result.should_analyze is True


# --- Registry ---

class TestApplyPreFilter:
    def test_known_trader(self):
        ctx = _base_ctx()
        result = apply_pre_filter("balanced_hybrid", ctx)
        assert result.should_analyze is True

    def test_unknown_trader_passes(self):
        ctx = _base_ctx()
        result = apply_pre_filter("nonexistent_trader", ctx)
        assert result.should_analyze is True  # No filter = pass through

    def test_cost_savings_estimate(self):
        """Demonstrate how pre-filters save LLM calls on typical data."""
        # Scenario: 8 traders x 25 assets = 200 potential LLM calls
        # With pre-filters, many will be skipped
        ctx_neutral = _base_ctx()  # neutral market, no anomalies
        ctx_trending = _base_ctx(price={"current": 65000, "change_24h_pct": 6.0, "volume_24h": 5000000,
                                        "daily_closes_7d": [60000, 61000, 62000, 63000, 64000, 64500, 65000]})
        ctx_crash = _base_ctx(
            price={"current": 55000, "change_24h_pct": -10.0, "volume_24h": 10000000,
                   "daily_closes_7d": [65000, 63000, 60000, 58000, 56000, 55500, 55000]},
            anomalies=[{"type": "price_spike", "severity": "high"}, {"type": "volume_surge", "severity": "critical"}],
            indicators={"composite_score": 30, "recommendation_type": "SELL"},
        )

        traders = [
            "conservative_quant", "momentum_hunter", "mean_reversion",
            "sentiment_contrarian", "balanced_hybrid",
            "scalper_quant", "whale_follower", "fibonacci_trader",
        ]

        neutral_skipped = sum(1 for t in traders if not apply_pre_filter(t, ctx_neutral).should_analyze)
        trending_skipped = sum(1 for t in traders if not apply_pre_filter(t, ctx_trending).should_analyze)
        crash_skipped = sum(1 for t in traders if not apply_pre_filter(t, ctx_crash).should_analyze)

        # In neutral market, at least sentiment + whale should be skipped
        assert neutral_skipped >= 2
        # In crash, conservative should skip (high anomaly)
        assert crash_skipped >= 1
