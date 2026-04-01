"""RSS feed fetcher for financial news headlines."""

from __future__ import annotations

import asyncio
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime
from email.utils import parsedate_to_datetime

import httpx

DEFAULT_FEEDS: list[str] = [
    "https://feeds.feedburner.com/CoinDesk",
    "https://cointelegraph.com/rss",
    "https://finance.yahoo.com/news/rssindex",
]


@dataclass
class Headline:
    title: str
    published: datetime | None
    source: str
    url: str | None


async def fetch_feed(url: str, client: httpx.AsyncClient) -> list[Headline]:
    """Fetch and parse an RSS feed, returning a list of Headlines."""
    try:
        response = await client.get(url, timeout=10.0)
        response.raise_for_status()
    except (httpx.HTTPError, httpx.TimeoutException):
        return []

    try:
        root = ET.fromstring(response.text)
    except ET.ParseError:
        return []

    headlines: list[Headline] = []
    for item in root.iter("item"):
        title_el = item.find("title")
        link_el = item.find("link")
        pub_date_el = item.find("pubDate")

        title = title_el.text.strip() if title_el is not None and title_el.text else ""
        if not title:
            continue

        published: datetime | None = None
        if pub_date_el is not None and pub_date_el.text:
            try:
                published = parsedate_to_datetime(pub_date_el.text.strip())
            except (ValueError, TypeError):
                published = None

        link = link_el.text.strip() if link_el is not None and link_el.text else None

        headlines.append(
            Headline(title=title, published=published, source=url, url=link)
        )

    return headlines


async def fetch_all_feeds(feeds: list[str] | None = None) -> list[Headline]:
    """Fetch multiple RSS feeds concurrently and return merged, sorted headlines."""
    urls = feeds if feeds is not None else DEFAULT_FEEDS

    async with httpx.AsyncClient() as client:
        results = await asyncio.gather(
            *(fetch_feed(url, client) for url in urls),
            return_exceptions=True,
        )

    all_headlines: list[Headline] = []
    for result in results:
        if isinstance(result, list):
            all_headlines.extend(result)

    all_headlines.sort(
        key=lambda h: h.published or datetime.min,
        reverse=True,
    )
    return all_headlines
