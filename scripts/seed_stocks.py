"""Seed 15 US blue chip stocks into the database.

Usage:
    cd backend && uv run python -m scripts.seed_stocks

Or:
    python scripts/seed_stocks.py
"""

import asyncio
import sys
from pathlib import Path

# Add backend to path so we can import app modules
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from sqlalchemy import select

from app.database import async_session
from app.assets.models import Asset
from app.anomalies.models import AnomalyEvent  # noqa: F401 — relationship resolution


STOCK_UNIVERSE = [
    {"symbol": "AAPL",  "name": "Apple Inc.",           "exchange": "NASDAQ"},
    {"symbol": "MSFT",  "name": "Microsoft Corp.",      "exchange": "NASDAQ"},
    {"symbol": "GOOGL", "name": "Alphabet Inc.",        "exchange": "NASDAQ"},
    {"symbol": "AMZN",  "name": "Amazon.com Inc.",      "exchange": "NASDAQ"},
    {"symbol": "NVDA",  "name": "NVIDIA Corp.",         "exchange": "NASDAQ"},
    {"symbol": "TSLA",  "name": "Tesla Inc.",           "exchange": "NASDAQ"},
    {"symbol": "META",  "name": "Meta Platforms Inc.",   "exchange": "NASDAQ"},
    {"symbol": "JPM",   "name": "JPMorgan Chase & Co.", "exchange": "NYSE"},
    {"symbol": "V",     "name": "Visa Inc.",            "exchange": "NYSE"},
    {"symbol": "JNJ",   "name": "Johnson & Johnson",    "exchange": "NYSE"},
    {"symbol": "WMT",   "name": "Walmart Inc.",         "exchange": "NYSE"},
    {"symbol": "MA",    "name": "Mastercard Inc.",       "exchange": "NYSE"},
    {"symbol": "DIS",   "name": "Walt Disney Co.",      "exchange": "NYSE"},
    {"symbol": "NFLX",  "name": "Netflix Inc.",         "exchange": "NASDAQ"},
    {"symbol": "AMD",   "name": "Advanced Micro Devices", "exchange": "NASDAQ"},
]


async def seed_stocks() -> None:
    """Insert stock assets into the database."""
    print("=== MarketPulse AI — Stock Asset Seed ===\n")

    async with async_session() as session:
        inserted = 0
        skipped = 0

        for stock in STOCK_UNIVERSE:
            existing = await session.execute(
                select(Asset).where(Asset.symbol == stock["symbol"])
            )
            if existing.scalar_one_or_none():
                print(f"  SKIP {stock['symbol']:>6s} — already exists")
                skipped += 1
                continue

            asset = Asset(
                symbol=stock["symbol"],
                name=stock["name"],
                provider_symbol=stock["symbol"],  # For Yahoo Finance, ticker = symbol
                asset_class="stock",
                exchange=stock["exchange"],
                currency="USD",
                is_active=True,
                metadata_={},
            )
            session.add(asset)
            print(f"  ADD  {stock['symbol']:>6s} — {stock['name']} ({stock['exchange']})")
            inserted += 1

        await session.commit()

    print(f"\nDone: {inserted} inserted, {skipped} skipped")
    print(f"Total stock universe: {len(STOCK_UNIVERSE)}")


if __name__ == "__main__":
    asyncio.run(seed_stocks())
