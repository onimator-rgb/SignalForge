"""CryptoPanic fetcher — crypto news aggregator with community sentiment."""

from __future__ import annotations

from datetime import datetime, timezone

import httpx

from app.config import settings
from app.logging_config import get_logger

from .base import BaseNewsFetcher, RawNewsItem

log = get_logger(__name__)


class CryptoPanicFetcher(BaseNewsFetcher):
    """CryptoPanic — crypto-focused news with community votes/sentiment."""

    BASE_URL = "https://cryptopanic.com/api/free/v1/posts/"

    @property
    def source_name(self) -> str:
        return "cryptopanic"

    @property
    def source_reliability(self) -> float:
        return 0.65  # Community-driven, fast but noisy

    async def fetch(self, symbols: list[str] | None = None, limit: int = 20) -> list[RawNewsItem]:
        api_key = settings.CRYPTOPANIC_API_KEY
        if not api_key:
            return []

        params = {
            "auth_token": api_key,
            "public": "true",
            "kind": "news",
        }
        if symbols:
            # CryptoPanic uses currency codes (BTC, ETH, etc.)
            currencies = [s.replace("USDT", "").replace("USD", "") for s in symbols[:5]]
            params["currencies"] = ",".join(currencies)

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(self.BASE_URL, params=params)
                resp.raise_for_status()
                data = resp.json()
        except Exception as exc:
            log.warning("news.cryptopanic.fetch_failed", error=str(exc))
            return []

        items = []
        for post in data.get("results", [])[:limit]:
            published = None
            if post.get("published_at"):
                try:
                    published = datetime.fromisoformat(post["published_at"].replace("Z", "+00:00"))
                except (ValueError, TypeError):
                    pass

            # Extract sentiment from votes
            votes = post.get("votes", {})
            positive = votes.get("positive", 0)
            negative = votes.get("negative", 0)
            total_votes = positive + negative
            sentiment = "neutral"
            sentiment_score = 0.0
            if total_votes > 0:
                sentiment_score = (positive - negative) / total_votes
                if sentiment_score > 0.3:
                    sentiment = "positive"
                elif sentiment_score < -0.3:
                    sentiment = "negative"

            # Extract currency symbols
            syms = []
            for currency in post.get("currencies", []):
                if currency.get("code"):
                    syms.append(currency["code"])

            items.append(RawNewsItem(
                title=post.get("title", ""),
                source=self.source_name,
                source_url=post.get("domain", ""),
                original_url=post.get("url", ""),
                published_at=published,
                summary=post.get("title", ""),  # CryptoPanic has title only
                symbols=syms or (symbols or []),
                asset_class="crypto",
                sentiment=sentiment,
                sentiment_score=sentiment_score,
                categories=[post.get("kind", "news")],
                reliability=self.source_reliability,
                raw_data={"votes": votes, "source_domain": post.get("domain", "")},
            ))

        log.info("news.cryptopanic.fetched", count=len(items))
        return items
