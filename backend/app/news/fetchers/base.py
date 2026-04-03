"""Base news fetcher interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class RawNewsItem:
    """Standardized news item from any source."""
    title: str
    source: str                              # provider name
    source_url: str = ""
    original_url: str = ""
    published_at: datetime | None = None
    summary: str = ""
    content_snippet: str = ""
    symbols: list[str] = field(default_factory=list)
    asset_class: str = ""                    # crypto, stock, macro
    sentiment: str = ""                      # positive, negative, neutral
    sentiment_score: float = 0.0             # -1.0 to 1.0
    categories: list[str] = field(default_factory=list)
    language: str = "en"
    reliability: float = 0.5                 # source reliability 0-1
    raw_data: dict = field(default_factory=dict)


class BaseNewsFetcher(ABC):
    """Abstract interface for news source fetchers."""

    @property
    @abstractmethod
    def source_name(self) -> str:
        """Unique source identifier."""

    @property
    @abstractmethod
    def source_reliability(self) -> float:
        """Base reliability score for this source (0-1)."""

    @abstractmethod
    async def fetch(self, symbols: list[str] | None = None, limit: int = 20) -> list[RawNewsItem]:
        """Fetch latest news, optionally filtered by asset symbols."""
