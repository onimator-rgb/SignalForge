"""Tests for news aggregation, deduplication, and cross-verification."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.news.aggregator import (
    NewsAggregator,
    _normalize_title,
    _title_hash,
    _titles_similar,
    _domain_reliability_boost,
)
from app.news.fetchers.base import RawNewsItem


# ---------------------------------------------------------------------------
# Title normalization and dedup
# ---------------------------------------------------------------------------

class TestTitleNormalization:
    def test_normalize_removes_punctuation(self):
        assert _normalize_title("Bitcoin hits $100k!") == "bitcoin hits 100k"

    def test_normalize_collapses_spaces(self):
        assert _normalize_title("  Bitcoin   surges  ") == "bitcoin surges"

    def test_hash_consistent(self):
        h1 = _title_hash("Bitcoin hits new all-time high")
        h2 = _title_hash("Bitcoin hits new all-time high")
        assert h1 == h2

    def test_hash_different_titles(self):
        h1 = _title_hash("Bitcoin surges to $100k")
        h2 = _title_hash("Ethereum drops 10%")
        assert h1 != h2


class TestTitleSimilarity:
    def test_identical_titles(self):
        assert _titles_similar("Bitcoin hits $100k", "Bitcoin hits $100k") is True

    def test_similar_titles_different_wording(self):
        assert _titles_similar(
            "Bitcoin surges past $100,000 milestone",
            "Bitcoin surges above $100,000 in historic rally"
        ) is True

    def test_completely_different_titles(self):
        assert _titles_similar(
            "Bitcoin hits new high",
            "Ethereum network upgrade complete"
        ) is False

    def test_empty_titles(self):
        assert _titles_similar("", "") is False
        assert _titles_similar("Bitcoin", "") is False


class TestDomainReliability:
    def test_trusted_domain_boost(self):
        assert _domain_reliability_boost("https://reuters.com/article/123") == 0.15
        assert _domain_reliability_boost("https://bloomberg.com/news") == 0.15

    def test_unknown_domain_no_boost(self):
        assert _domain_reliability_boost("https://random-blog.com") == 0.0

    def test_coindesk_trusted(self):
        assert _domain_reliability_boost("https://www.coindesk.com/markets") == 0.15


# ---------------------------------------------------------------------------
# Deduplication
# ---------------------------------------------------------------------------

class TestDeduplication:
    def _make_item(self, title: str, source: str, reliability: float = 0.5) -> RawNewsItem:
        return RawNewsItem(
            title=title,
            source=source,
            reliability=reliability,
            raw_data={},
        )

    def test_removes_duplicates(self):
        aggregator = NewsAggregator()
        items = [
            self._make_item("Bitcoin hits $100k today", "marketaux", 0.7),
            self._make_item("Bitcoin hits $100k in historic move", "cryptopanic", 0.6),
            self._make_item("Ethereum upgrade complete", "alphavantage", 0.8),
        ]
        result = aggregator.deduplicate(items)
        assert len(result) == 2  # BTC stories merged, ETH separate

    def test_keeps_most_reliable(self):
        aggregator = NewsAggregator()
        items = [
            self._make_item("BTC surges to new high", "cryptopanic", 0.5),
            self._make_item("BTC surges to all-time high", "alphavantage", 0.8),
        ]
        result = aggregator.deduplicate(items)
        assert len(result) == 1
        assert result[0].source == "alphavantage"  # Higher reliability kept

    def test_cross_source_boost(self):
        aggregator = NewsAggregator()
        items = [
            self._make_item("Bitcoin mining difficulty increases sharply", "marketaux", 0.5),
            self._make_item("Bitcoin mining difficulty increases to record", "cryptopanic", 0.5),
            self._make_item("Bitcoin mining difficulty increases dramatically", "alphavantage", 0.5),
        ]
        result = aggregator.deduplicate(items)
        assert len(result) == 1
        # 3 sources = +0.20 boost
        assert result[0].reliability >= 0.7

    def test_no_false_dedup(self):
        aggregator = NewsAggregator()
        items = [
            self._make_item("Bitcoin price analysis", "marketaux", 0.5),
            self._make_item("Ethereum network upgrade", "cryptopanic", 0.5),
            self._make_item("Solana DeFi growth", "alphavantage", 0.5),
        ]
        result = aggregator.deduplicate(items)
        assert len(result) == 3  # All unique, no dedup


# ---------------------------------------------------------------------------
# Scoring and ranking
# ---------------------------------------------------------------------------

class TestScoringAndRanking:
    def test_recent_news_boosted(self):
        aggregator = NewsAggregator()
        recent = RawNewsItem(
            title="Breaking: BTC hits high",
            source="marketaux",
            reliability=0.5,
            published_at=datetime.now(timezone.utc),
            raw_data={"cross_source_count": 1},
        )
        old = RawNewsItem(
            title="Old news about ETH",
            source="cryptopanic",
            reliability=0.5,
            published_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            raw_data={"cross_source_count": 1},
        )
        result = aggregator.score_and_rank([old, recent])
        assert result[0].title == recent.title  # Recent ranked first

    def test_strong_sentiment_boosted(self):
        aggregator = NewsAggregator()
        strong = RawNewsItem(
            title="Very bullish news",
            source="marketaux",
            reliability=0.5,
            sentiment_score=0.8,
            raw_data={"cross_source_count": 1},
        )
        neutral = RawNewsItem(
            title="Neutral market update",
            source="cryptopanic",
            reliability=0.5,
            sentiment_score=0.0,
            raw_data={"cross_source_count": 1},
        )
        result = aggregator.score_and_rank([neutral, strong])
        assert result[0].title == strong.title


# ---------------------------------------------------------------------------
# News Sentiment Trader pre-filter
# ---------------------------------------------------------------------------

class TestNewsSentimentPreFilter:
    def test_skips_without_news(self):
        from app.ai_traders.pre_filter import apply_pre_filter
        ctx = {
            "asset": {"symbol": "BTC"},
            "price": {"current": 65000},
            "indicators": {},
            "anomalies": [],
        }
        result = apply_pre_filter("news_sentiment", ctx)
        assert result.should_analyze is False

    def test_passes_with_news(self):
        from app.ai_traders.pre_filter import apply_pre_filter
        ctx = {
            "asset": {"symbol": "BTC"},
            "price": {"current": 65000},
            "indicators": {},
            "anomalies": [],
            "news": [{"title": "BTC surges", "sentiment": "positive"}],
        }
        result = apply_pre_filter("news_sentiment", ctx)
        assert result.should_analyze is True

    def test_passes_with_existing_position(self):
        from app.ai_traders.pre_filter import apply_pre_filter
        ctx = {
            "asset": {"symbol": "BTC"},
            "price": {"current": 65000},
            "indicators": {},
            "anomalies": [],
            "existing_position": {"entry_price": 60000},
        }
        result = apply_pre_filter("news_sentiment", ctx)
        assert result.should_analyze is True


# ---------------------------------------------------------------------------
# News in trader prompts
# ---------------------------------------------------------------------------

class TestNewsInPrompts:
    def test_prompt_includes_news(self):
        from app.ai_traders.base import BaseAITrader
        from app.llm.router import TaskComplexity

        class T(BaseAITrader):
            def get_system_prompt(self): return "Test"
            def get_complexity(self): return TaskComplexity.SIMPLE

        trader = T(name="T", slug="t", llm_provider="groq", llm_model="test")
        ctx = {
            "asset": {"symbol": "BTC"},
            "price": {"current": 65000},
            "indicators": {},
            "anomalies": [],
            "news": [
                {"title": "Bitcoin ETF approved", "sentiment": "positive",
                 "verified": True, "source": "reuters", "reliability": 0.9,
                 "sources_count": 3},
            ],
            "timestamp": "now",
        }
        prompt = trader.build_user_prompt(ctx)
        assert "Verified News" in prompt
        assert "Bitcoin ETF approved" in prompt
        assert "VERIFIED" in prompt

    def test_prompt_without_news(self):
        from app.ai_traders.base import BaseAITrader
        from app.llm.router import TaskComplexity

        class T(BaseAITrader):
            def get_system_prompt(self): return "Test"
            def get_complexity(self): return TaskComplexity.SIMPLE

        trader = T(name="T", slug="t", llm_provider="groq", llm_model="test")
        ctx = {
            "asset": {"symbol": "BTC"},
            "price": {"current": 65000},
            "indicators": {},
            "anomalies": [],
            "timestamp": "now",
        }
        prompt = trader.build_user_prompt(ctx)
        assert "Verified News" not in prompt
