"""Finnhub fetcher — 60 req/min FREE, AI sentiment, stocks + crypto + forex.

Best free financial news API available. Provides:
- News articles with sentiment (bullish/bearish %)
- Sector-level sentiment comparison
- Company news + market news
- Crypto news
- 60 requests/minute on free tier (~86,400/day)
"""

from __future__ import annotations

from datetime import datetime, timezone

import httpx

from app.config import settings
from app.logging_config import get_logger

from .base import BaseNewsFetcher, RawNewsItem

log = get_logger(__name__)


class FinnhubFetcher(BaseNewsFetcher):
    """Finnhub — most generous free tier, AI-powered sentiment."""

    BASE_URL = "https://finnhub.io/api/v1"

    @property
    def source_name(self) -> str:
        return "finnhub"

    @property
    def source_reliability(self) -> float:
        return 0.80  # Professional API, AI sentiment

    async def fetch(self, symbols: list[str] | None = None, limit: int = 20) -> list[RawNewsItem]:
        api_key = settings.FINNHUB_API_KEY
        if not api_key:
            return []

        items: list[RawNewsItem] = []

        # Fetch general market news
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(
                    f"{self.BASE_URL}/news",
                    params={"category": "general", "token": api_key},
                )
                resp.raise_for_status()
                articles = resp.json()

            for article in articles[:limit]:
                published = None
                ts = article.get("datetime")
                if ts:
                    try:
                        published = datetime.fromtimestamp(ts, tz=timezone.utc)
                    except (ValueError, OSError):
                        pass

                items.append(RawNewsItem(
                    title=article.get("headline", ""),
                    source=self.source_name,
                    source_url=article.get("source", ""),
                    original_url=article.get("url", ""),
                    published_at=published,
                    summary=article.get("summary", "")[:500],
                    symbols=article.get("related", "").split(",") if article.get("related") else [],
                    asset_class="stock",
                    categories=[article.get("category", "general")],
                    reliability=self.source_reliability,
                    raw_data={
                        "source_domain": article.get("source", ""),
                        "image": article.get("image", ""),
                        "finnhub_id": article.get("id"),
                    },
                ))
        except Exception as exc:
            log.warning("news.finnhub.general_failed", error=str(exc))

        # Fetch crypto news
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(
                    f"{self.BASE_URL}/news",
                    params={"category": "crypto", "token": api_key},
                )
                resp.raise_for_status()
                articles = resp.json()

            for article in articles[:limit]:
                published = None
                ts = article.get("datetime")
                if ts:
                    try:
                        published = datetime.fromtimestamp(ts, tz=timezone.utc)
                    except (ValueError, OSError):
                        pass

                items.append(RawNewsItem(
                    title=article.get("headline", ""),
                    source=self.source_name,
                    source_url=article.get("source", ""),
                    original_url=article.get("url", ""),
                    published_at=published,
                    summary=article.get("summary", "")[:500],
                    symbols=article.get("related", "").split(",") if article.get("related") else [],
                    asset_class="crypto",
                    categories=["crypto", article.get("category", "")],
                    reliability=self.source_reliability,
                    raw_data={
                        "source_domain": article.get("source", ""),
                        "finnhub_id": article.get("id"),
                    },
                ))
        except Exception as exc:
            log.warning("news.finnhub.crypto_failed", error=str(exc))

        # Fetch sentiment for specific symbols (if provided)
        if symbols:
            for symbol in symbols[:5]:
                try:
                    await self._fetch_symbol_sentiment(api_key, symbol, items)
                except Exception as exc:
                    log.warning("news.finnhub.sentiment_failed", symbol=symbol, error=str(exc))

        log.info("news.finnhub.fetched", count=len(items))
        return items

    async def _fetch_symbol_sentiment(
        self,
        api_key: str,
        symbol: str,
        items: list[RawNewsItem],
    ) -> None:
        """Fetch news sentiment for a specific symbol."""
        # Clean symbol for Finnhub format
        clean = symbol.upper().replace("USDT", "").replace("USD", "")

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{self.BASE_URL}/news-sentiment",
                params={"symbol": clean, "token": api_key},
            )
            if resp.status_code != 200:
                return
            data = resp.json()

        sentiment_data = data.get("sentiment", {})
        bullish = sentiment_data.get("bullishPercent", 0)
        bearish = sentiment_data.get("bearishPercent", 0)

        # Convert to our -1 to 1 scale
        sentiment_score = (bullish - bearish) / 100 if (bullish + bearish) > 0 else 0
        sentiment = "neutral"
        if sentiment_score > 0.2:
            sentiment = "positive"
        elif sentiment_score < -0.2:
            sentiment = "negative"

        # Add company news from buzz data
        buzz = data.get("buzz", {})
        if buzz.get("articlesInLastWeek", 0) > 0:
            items.append(RawNewsItem(
                title=f"{clean} sentiment: {bullish:.0f}% bullish, {bearish:.0f}% bearish ({buzz.get('articlesInLastWeek', 0)} articles/week)",
                source=self.source_name,
                source_url="finnhub.io",
                symbols=[clean],
                asset_class="stock",
                sentiment=sentiment,
                sentiment_score=sentiment_score,
                categories=["sentiment_aggregate"],
                reliability=0.85,  # Aggregated sentiment is more reliable
                raw_data={
                    "buzz": buzz,
                    "sector_sentiment": data.get("sectorAverageBullishPercent", 0),
                    "company_news_score": data.get("companyNewsScore", 0),
                },
            ))
