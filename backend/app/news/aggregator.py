"""News Aggregator — fetches from all sources, deduplicates, cross-verifies.

Anti-fake-news pipeline:
1. Fetch from multiple sources in parallel
2. Deduplicate (same story from different sources)
3. Cross-verify (news in 2+ sources = higher reliability)
4. Score reliability based on source quality + cross-references
5. Optional: LLM sentiment analysis for top stories
"""

from __future__ import annotations

import asyncio
import hashlib
import re
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.logging_config import get_logger

from .fetchers.base import RawNewsItem
from .fetchers.finnhub import FinnhubFetcher
from .fetchers.marketaux import MarketAuxFetcher
from .fetchers.alphavantage import AlphaVantageFetcher
from .models import NewsArticle

log = get_logger(__name__)

# Source reliability tiers
SOURCE_RELIABILITY = {
    "finnhub": 0.82,         # Professional, AI sentiment, most generous free tier
    "alphavantage": 0.80,    # Professional, AI sentiment
    "marketaux": 0.70,       # Multi-source aggregator
}

# Domains known to be high/low quality
TRUSTED_DOMAINS = {
    "reuters.com", "bloomberg.com", "cnbc.com", "wsj.com",
    "ft.com", "coindesk.com", "cointelegraph.com", "theblock.co",
    "decrypt.co", "techcrunch.com", "marketwatch.com",
}
LOW_QUALITY_DOMAINS = {
    "clickbait", "satire", "parody",  # placeholder patterns
}


def _normalize_title(title: str) -> str:
    """Normalize title for deduplication comparison."""
    t = title.lower().strip()
    t = re.sub(r'[^\w\s]', '', t)
    t = re.sub(r'\s+', ' ', t)
    return t


def _title_hash(title: str) -> str:
    """Create a hash of normalized title for fast dedup."""
    return hashlib.md5(_normalize_title(title).encode()).hexdigest()[:16]


def _titles_similar(a: str, b: str, threshold: float = 0.6) -> bool:
    """Check if two titles are about the same story (word overlap)."""
    words_a = set(_normalize_title(a).split())
    words_b = set(_normalize_title(b).split())
    if not words_a or not words_b:
        return False
    overlap = len(words_a & words_b)
    smaller = min(len(words_a), len(words_b))
    return (overlap / smaller) >= threshold if smaller > 0 else False


def _domain_reliability_boost(source_url: str) -> float:
    """Boost reliability for trusted domains."""
    for domain in TRUSTED_DOMAINS:
        if domain in source_url.lower():
            return 0.15
    return 0.0


class NewsAggregator:
    """Fetches, deduplicates, and cross-verifies news from multiple sources."""

    def __init__(self):
        self._fetchers = [
            FinnhubFetcher(),        # Primary: 60 req/min FREE, AI sentiment
            MarketAuxFetcher(),      # Secondary: 100 req/day, 80+ markets
            AlphaVantageFetcher(),   # Tertiary: 25 req/day, deep sentiment
        ]

    async def fetch_all(
        self,
        symbols: list[str] | None = None,
        limit_per_source: int = 15,
    ) -> list[RawNewsItem]:
        """Fetch from all configured sources concurrently."""
        tasks = [
            fetcher.fetch(symbols=symbols, limit=limit_per_source)
            for fetcher in self._fetchers
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        all_items: list[RawNewsItem] = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                log.warning(
                    "news.fetch_error",
                    source=self._fetchers[i].source_name,
                    error=str(result),
                )
                continue
            all_items.extend(result)

        log.info("news.fetch_all_done", total=len(all_items))
        return all_items

    def deduplicate(self, items: list[RawNewsItem]) -> list[RawNewsItem]:
        """Remove duplicate stories, keeping the one from the most reliable source.

        Also marks cross-source articles for reliability boost.
        """
        # Group by title similarity
        groups: list[list[RawNewsItem]] = []
        used = set()

        for i, item in enumerate(items):
            if i in used:
                continue
            group = [item]
            used.add(i)

            for j, other in enumerate(items):
                if j in used or j <= i:
                    continue
                if _titles_similar(item.title, other.title):
                    group.append(other)
                    used.add(j)

            groups.append(group)

        # Pick best from each group and annotate cross-source count
        deduplicated: list[RawNewsItem] = []
        for group in groups:
            # Sort by reliability (highest first)
            group.sort(key=lambda x: x.reliability, reverse=True)
            best = group[0]

            # Cross-source count
            unique_sources = len({item.source for item in group})
            best.raw_data["cross_source_count"] = unique_sources
            best.raw_data["all_sources"] = [item.source for item in group]

            # Boost reliability if confirmed by multiple sources
            if unique_sources >= 3:
                best.reliability = min(1.0, best.reliability + 0.20)
            elif unique_sources >= 2:
                best.reliability = min(1.0, best.reliability + 0.10)

            # Domain reliability boost
            best.reliability = min(1.0, best.reliability + _domain_reliability_boost(best.source_url))

            deduplicated.append(best)

        log.info(
            "news.deduplicated",
            before=len(items),
            after=len(deduplicated),
            cross_verified=sum(1 for d in deduplicated if d.raw_data.get("cross_source_count", 1) >= 2),
        )
        return deduplicated

    def score_and_rank(self, items: list[RawNewsItem]) -> list[RawNewsItem]:
        """Score and rank news by importance and reliability."""
        for item in items:
            score = item.reliability

            # Boost for recent news (< 4h old gets +0.1)
            if item.published_at:
                age = datetime.now(timezone.utc) - item.published_at.replace(tzinfo=timezone.utc) if item.published_at.tzinfo is None else datetime.now(timezone.utc) - item.published_at
                if age < timedelta(hours=4):
                    score += 0.10
                elif age > timedelta(hours=48):
                    score -= 0.15

            # Boost for strong sentiment (more tradeable)
            if abs(item.sentiment_score) > 0.5:
                score += 0.05

            # Boost for cross-source verification
            cross = item.raw_data.get("cross_source_count", 1)
            if cross >= 2:
                score += 0.05 * (cross - 1)

            item.reliability = min(1.0, max(0.0, score))

        # Sort by reliability score descending
        items.sort(key=lambda x: x.reliability, reverse=True)
        return items

    async def get_verified_news(
        self,
        symbols: list[str] | None = None,
        limit: int = 10,
        min_reliability: float = 0.5,
    ) -> list[RawNewsItem]:
        """Full pipeline: fetch → deduplicate → verify → rank → filter."""
        raw = await self.fetch_all(symbols=symbols)
        deduped = self.deduplicate(raw)
        ranked = self.score_and_rank(deduped)
        filtered = [item for item in ranked if item.reliability >= min_reliability]
        return filtered[:limit]

    async def save_to_db(
        self,
        db: AsyncSession,
        items: list[RawNewsItem],
    ) -> int:
        """Save verified news articles to database, skipping duplicates."""
        saved = 0
        for item in items:
            # Check for existing article with same title hash
            title_h = _title_hash(item.title)
            existing = await db.execute(
                select(func.count()).where(
                    NewsArticle.title.ilike(f"%{item.title[:50]}%"),
                    NewsArticle.fetched_at >= datetime.now(timezone.utc) - timedelta(hours=24),
                )
            )
            if existing.scalar_one() > 0:
                continue

            article = NewsArticle(
                source=item.source,
                source_url=item.source_url,
                title=item.title,
                summary=item.summary,
                content_snippet=item.content_snippet,
                original_url=item.original_url,
                published_at=item.published_at,
                symbols_mentioned=item.symbols,
                asset_class=item.asset_class,
                source_sentiment=item.sentiment,
                source_sentiment_score=item.sentiment_score,
                reliability_score=item.reliability,
                cross_source_count=item.raw_data.get("cross_source_count", 1),
                is_verified=item.raw_data.get("cross_source_count", 1) >= 2,
                categories=item.categories,
                language=item.language,
                raw_data=item.raw_data,
            )
            db.add(article)
            saved += 1

        if saved > 0:
            await db.flush()
            log.info("news.saved_to_db", count=saved)

        return saved


async def get_news_for_asset(
    db: AsyncSession,
    symbol: str,
    hours: int = 24,
    limit: int = 5,
) -> list[dict]:
    """Get recent verified news for a specific asset (for trader context)."""
    since = datetime.now(timezone.utc) - timedelta(hours=hours)

    result = await db.execute(
        select(NewsArticle)
        .where(
            NewsArticle.fetched_at >= since,
            NewsArticle.reliability_score >= 0.5,
        )
        .order_by(NewsArticle.reliability_score.desc())
        .limit(limit * 3)  # fetch more, filter by symbol after
    )
    articles = result.scalars().all()

    # Filter by symbol (case-insensitive, partial match)
    symbol_clean = symbol.upper().replace("USDT", "").replace("USD", "")
    relevant = []
    for a in articles:
        mentioned = [s.upper().replace("USDT", "").replace("USD", "") for s in (a.symbols_mentioned or [])]
        if symbol_clean in mentioned or any(symbol_clean in m for m in mentioned):
            relevant.append(a)

    return [
        {
            "title": a.title,
            "source": a.source,
            "published_at": a.published_at.isoformat() if a.published_at else None,
            "sentiment": a.source_sentiment or a.ai_sentiment or "neutral",
            "sentiment_score": a.source_sentiment_score or a.ai_sentiment_score or 0.0,
            "reliability": a.reliability_score,
            "verified": a.is_verified,
            "sources_count": a.cross_source_count,
            "summary": (a.summary or a.title)[:200],
        }
        for a in relevant[:limit]
    ]
