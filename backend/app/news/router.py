"""REST API for news aggregation and retrieval."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db

from .aggregator import NewsAggregator, get_news_for_asset
from .models import NewsArticle

router = APIRouter(prefix="/news", tags=["news"])


@router.post("/fetch")
async def api_fetch_news(
    symbols: list[str] | None = None,
    limit: int = 15,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Fetch news from all sources, deduplicate, verify, and save."""
    aggregator = NewsAggregator()
    items = await aggregator.get_verified_news(symbols=symbols, limit=limit)
    saved = await aggregator.save_to_db(db, items)
    await db.commit()

    return {
        "fetched": len(items),
        "saved_new": saved,
        "top_stories": [
            {
                "title": item.title,
                "source": item.source,
                "sentiment": item.sentiment,
                "reliability": round(item.reliability, 2),
                "verified": item.raw_data.get("cross_source_count", 1) >= 2,
                "sources": item.raw_data.get("all_sources", [item.source]),
            }
            for item in items[:5]
        ],
    }


@router.get("/asset/{symbol}")
async def api_news_for_asset(
    symbol: str,
    hours: int = 24,
    limit: int = 10,
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    """Get recent verified news for a specific asset."""
    return await get_news_for_asset(db, symbol, hours=hours, limit=limit)


@router.get("/recent")
async def api_recent_news(
    hours: int = 24,
    limit: int = 20,
    min_reliability: float = 0.5,
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    """Get all recent news above reliability threshold."""
    since = datetime.now(timezone.utc) - timedelta(hours=hours)

    result = await db.execute(
        select(NewsArticle)
        .where(
            NewsArticle.fetched_at >= since,
            NewsArticle.reliability_score >= min_reliability,
        )
        .order_by(NewsArticle.reliability_score.desc())
        .limit(limit)
    )
    articles = result.scalars().all()

    return [
        {
            "id": str(a.id),
            "title": a.title,
            "source": a.source,
            "published_at": a.published_at.isoformat() if a.published_at else None,
            "symbols": a.symbols_mentioned,
            "sentiment": a.source_sentiment or "neutral",
            "sentiment_score": a.source_sentiment_score or 0,
            "reliability": a.reliability_score,
            "verified": a.is_verified,
            "sources_count": a.cross_source_count,
            "summary": (a.summary or a.title)[:300],
            "url": a.original_url,
        }
        for a in articles
    ]
