"""News models — aggregated financial news with verification scoring."""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, Integer, Numeric, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.models import UUIDPrimaryKeyMixin
from app.database import Base


class NewsArticle(Base, UUIDPrimaryKeyMixin):
    """A single news article from any source."""
    __tablename__ = "news_articles"

    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    source: Mapped[str] = mapped_column(String(50), nullable=False)         # marketaux, cryptopanic, alphavantage, rss
    source_url: Mapped[str] = mapped_column(Text, nullable=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=True)
    content_snippet: Mapped[str] = mapped_column(Text, nullable=True)       # first 500 chars
    original_url: Mapped[str] = mapped_column(Text, nullable=True)

    # Asset matching
    symbols_mentioned: Mapped[list] = mapped_column(JSONB, nullable=False, server_default="[]")
    asset_class: Mapped[str] = mapped_column(String(10), nullable=True)     # crypto, stock, macro

    # Source-provided sentiment (if available)
    source_sentiment: Mapped[str] = mapped_column(String(20), nullable=True)    # positive, negative, neutral
    source_sentiment_score: Mapped[float] = mapped_column(Float, nullable=True) # -1.0 to 1.0

    # Our verification & scoring
    reliability_score: Mapped[float] = mapped_column(Float, nullable=False, server_default="0.5")
    cross_source_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    is_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    duplicate_of_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=True)

    # AI-computed sentiment (from our LLM analysis)
    ai_sentiment: Mapped[str] = mapped_column(String(20), nullable=True)
    ai_sentiment_score: Mapped[float] = mapped_column(Float, nullable=True)
    ai_impact_level: Mapped[str] = mapped_column(String(20), nullable=True)     # low, medium, high, critical
    ai_analysis: Mapped[str] = mapped_column(Text, nullable=True)

    # Metadata
    language: Mapped[str] = mapped_column(String(5), nullable=True, server_default="en")
    categories: Mapped[list] = mapped_column(JSONB, nullable=False, server_default="[]")
    raw_data: Mapped[dict] = mapped_column(JSONB, nullable=True)
