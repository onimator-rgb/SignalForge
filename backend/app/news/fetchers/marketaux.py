"""MarketAux fetcher — free financial news API, 80+ global markets."""

from __future__ import annotations

from datetime import datetime, timezone

import httpx

from app.config import settings
from app.logging_config import get_logger

from .base import BaseNewsFetcher, RawNewsItem

log = get_logger(__name__)


class MarketAuxFetcher(BaseNewsFetcher):
    """MarketAux — free, no credit card, 80+ markets, 5000+ sources."""

    BASE_URL = "https://api.marketaux.com/v1/news/all"

    @property
    def source_name(self) -> str:
        return "marketaux"

    @property
    def source_reliability(self) -> float:
        return 0.7  # Aggregator — generally reliable but varies by source

    async def fetch(self, symbols: list[str] | None = None, limit: int = 20) -> list[RawNewsItem]:
        api_key = settings.MARKETAUX_API_KEY
        if not api_key:
            return []

        params = {
            "api_token": api_key,
            "limit": min(limit, 50),
            "language": "en",
        }
        if symbols:
            params["symbols"] = ",".join(symbols[:5])

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(self.BASE_URL, params=params)
                resp.raise_for_status()
                data = resp.json()
        except Exception as exc:
            log.warning("news.marketaux.fetch_failed", error=str(exc))
            return []

        items = []
        for article in data.get("data", []):
            published = None
            if article.get("published_at"):
                try:
                    published = datetime.fromisoformat(article["published_at"].replace("Z", "+00:00"))
                except (ValueError, TypeError):
                    pass

            # Extract symbols from entities
            syms = []
            for entity in article.get("entities", []):
                if entity.get("symbol"):
                    syms.append(entity["symbol"])

            items.append(RawNewsItem(
                title=article.get("title", ""),
                source=self.source_name,
                source_url=article.get("source", ""),
                original_url=article.get("url", ""),
                published_at=published,
                summary=article.get("description", "")[:500],
                content_snippet=article.get("snippet", "")[:500],
                symbols=syms or (symbols or []),
                asset_class="stock",
                sentiment=article.get("sentiment", ""),
                categories=[article.get("category", "")],
                reliability=self.source_reliability,
                raw_data={"source_domain": article.get("source", "")},
            ))

        log.info("news.marketaux.fetched", count=len(items))
        return items
