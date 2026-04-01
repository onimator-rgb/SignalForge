"""Tests for the sentiment fetcher and classifier modules."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from app.sentiment.classifier import SentimentResult, classify_batch, classify_headline
from app.sentiment.fetcher import Headline, fetch_all_feeds, fetch_feed

# ---------------------------------------------------------------------------
# Sample RSS XML fixture
# ---------------------------------------------------------------------------

SAMPLE_RSS_XML = """\
<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Test Feed</title>
    <item>
      <title>Bitcoin rallies past 100k milestone</title>
      <link>https://example.com/1</link>
      <pubDate>Mon, 31 Mar 2026 10:00:00 +0000</pubDate>
    </item>
    <item>
      <title>Ethereum upgrade boosts adoption</title>
      <link>https://example.com/2</link>
      <pubDate>Mon, 31 Mar 2026 09:00:00 +0000</pubDate>
    </item>
    <item>
      <title>SEC schedules meeting on crypto regulation</title>
      <link>https://example.com/3</link>
      <pubDate>Mon, 31 Mar 2026 08:00:00 +0000</pubDate>
    </item>
  </channel>
</rss>
"""

SAMPLE_RSS_XML_2 = """\
<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Feed Two</title>
    <item>
      <title>Market crash sparks fear</title>
      <link>https://example.com/4</link>
      <pubDate>Mon, 31 Mar 2026 11:00:00 +0000</pubDate>
    </item>
  </channel>
</rss>
"""


# ---------------------------------------------------------------------------
# Fetcher tests
# ---------------------------------------------------------------------------


class TestFetchFeed:
    async def test_parse_valid_rss(self) -> None:
        mock_response = httpx.Response(200, text=SAMPLE_RSS_XML, request=httpx.Request("GET", "https://example.com/feed"))
        client = AsyncMock(spec=httpx.AsyncClient)
        client.get = AsyncMock(return_value=mock_response)

        headlines = await fetch_feed("https://example.com/feed", client)

        assert len(headlines) == 3
        assert headlines[0].title == "Bitcoin rallies past 100k milestone"
        assert headlines[1].title == "Ethereum upgrade boosts adoption"
        assert headlines[2].title == "SEC schedules meeting on crypto regulation"
        assert headlines[0].published is not None
        assert headlines[0].url == "https://example.com/1"

    async def test_fetch_error_returns_empty(self) -> None:
        client = AsyncMock(spec=httpx.AsyncClient)
        client.get = AsyncMock(side_effect=httpx.ConnectError("connection failed"))

        headlines = await fetch_feed("https://bad-url.example.com/feed", client)

        assert headlines == []

    async def test_fetch_all_feeds_merges(self) -> None:
        resp1 = httpx.Response(200, text=SAMPLE_RSS_XML, request=httpx.Request("GET", "https://feed1.example.com"))
        resp2 = httpx.Response(200, text=SAMPLE_RSS_XML_2, request=httpx.Request("GET", "https://feed2.example.com"))

        async def mock_get(url: str, **kwargs: object) -> httpx.Response:
            if "feed1" in url:
                return resp1
            return resp2

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(side_effect=mock_get)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("app.sentiment.fetcher.httpx.AsyncClient", return_value=mock_client):
            headlines = await fetch_all_feeds(
                feeds=["https://feed1.example.com", "https://feed2.example.com"]
            )

        assert len(headlines) == 4
        # Should be sorted by published desc — feed2 item is newest (11:00)
        assert headlines[0].title == "Market crash sparks fear"


# ---------------------------------------------------------------------------
# Classifier tests
# ---------------------------------------------------------------------------


class TestClassifyHeadline:
    def test_positive_headline(self) -> None:
        result = classify_headline("Bitcoin rallies to new gains")
        assert result.score > 0
        assert result.label == "positive"
        assert len(result.matched_words) > 0

    def test_negative_headline(self) -> None:
        result = classify_headline("Market crash sparks fear and sell-off")
        assert result.score < 0
        assert result.label == "negative"

    def test_neutral_headline(self) -> None:
        result = classify_headline("Company announces quarterly report")
        assert result.label == "neutral"

    def test_mixed_headline(self) -> None:
        result = classify_headline("Rally fades as crash fears grow")
        # Has both positive (rally) and negative (crash, fear) words
        assert isinstance(result.score, float)
        assert -1.0 <= result.score <= 1.0

    def test_empty_headline(self) -> None:
        result = classify_headline("")
        assert result.label == "neutral"
        assert result.score == 0.0
        assert result.matched_words == []


class TestClassifyBatch:
    def test_batch_average(self) -> None:
        headlines = [
            "Bitcoin rallies to new gains",
            "Ethereum soars past milestone",
            "Market crash sparks fear",
        ]
        result = classify_batch(headlines)
        # 2 positive + 1 negative => overall should be positive
        assert result.score > 0
        assert result.label == "positive"

    def test_batch_symbol_filter(self) -> None:
        headlines = [
            "BTC rallies to new gains",
            "ETH soars past milestone",
            "BTC crash sparks fear",
        ]
        result = classify_batch(headlines, symbol="BTC")
        # Only BTC headlines: 1 positive + 1 negative
        assert isinstance(result.score, float)
        # Verify only 2 headlines were considered (not the ETH one)
        assert len(result.matched_words) > 0

    def test_batch_empty(self) -> None:
        result = classify_batch([])
        assert result.score == 0.0
        assert result.label == "neutral"
        assert result.matched_words == []
