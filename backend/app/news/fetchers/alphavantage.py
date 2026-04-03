"""Alpha Vantage News Sentiment — AI-powered sentiment for stocks and crypto."""

from __future__ import annotations

from datetime import datetime

import httpx

from app.config import settings
from app.logging_config import get_logger

from .base import BaseNewsFetcher, RawNewsItem

log = get_logger(__name__)


class AlphaVantageFetcher(BaseNewsFetcher):
    """Alpha Vantage — AI sentiment analysis, 25 free requests/day."""

    BASE_URL = "https://www.alphavantage.co/query"

    @property
    def source_name(self) -> str:
        return "alphavantage"

    @property
    def source_reliability(self) -> float:
        return 0.8  # Professional data provider with AI sentiment

    async def fetch(self, symbols: list[str] | None = None, limit: int = 20) -> list[RawNewsItem]:
        api_key = settings.ALPHAVANTAGE_API_KEY
        if not api_key:
            return []

        params = {
            "function": "NEWS_SENTIMENT",
            "apikey": api_key,
            "limit": min(limit, 50),
            "sort": "LATEST",
        }
        if symbols:
            # Alpha Vantage uses CRYPTO:BTC or AAPL format
            tickers = []
            for s in symbols[:3]:
                clean = s.replace("USDT", "").replace("USD", "")
                if len(clean) <= 5 and clean.isalpha():
                    tickers.append(f"CRYPTO:{clean}" if len(clean) <= 4 else clean)
            if tickers:
                params["tickers"] = ",".join(tickers)

        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                resp = await client.get(self.BASE_URL, params=params)
                resp.raise_for_status()
                data = resp.json()
        except Exception as exc:
            log.warning("news.alphavantage.fetch_failed", error=str(exc))
            return []

        if "feed" not in data:
            log.warning("news.alphavantage.no_feed", response_keys=list(data.keys()))
            return []

        items = []
        for article in data["feed"][:limit]:
            published = None
            time_str = article.get("time_published", "")
            if time_str:
                try:
                    published = datetime.strptime(time_str[:15], "%Y%m%dT%H%M%S")
                except (ValueError, TypeError):
                    pass

            # Extract sentiment
            sentiment_score = float(article.get("overall_sentiment_score", 0))
            sentiment_label = article.get("overall_sentiment_label", "Neutral")
            sentiment_map = {
                "Bullish": "positive", "Somewhat-Bullish": "positive",
                "Bearish": "negative", "Somewhat-Bearish": "negative",
                "Neutral": "neutral",
            }
            sentiment = sentiment_map.get(sentiment_label, "neutral")

            # Extract ticker symbols
            syms = []
            for ticker in article.get("ticker_sentiment", []):
                if ticker.get("ticker"):
                    sym = ticker["ticker"].replace("CRYPTO:", "")
                    syms.append(sym)

            items.append(RawNewsItem(
                title=article.get("title", ""),
                source=self.source_name,
                source_url=article.get("source", ""),
                original_url=article.get("url", ""),
                published_at=published,
                summary=article.get("summary", "")[:500],
                symbols=syms or (symbols or []),
                asset_class="stock",
                sentiment=sentiment,
                sentiment_score=sentiment_score,
                categories=article.get("topics", []),
                reliability=self.source_reliability,
                raw_data={
                    "source_domain": article.get("source_domain", ""),
                    "banner_image": article.get("banner_image", ""),
                },
            ))

        log.info("news.alphavantage.fetched", count=len(items))
        return items
