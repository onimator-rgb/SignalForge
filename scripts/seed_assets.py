"""Seed top 25 crypto assets from CoinGecko into the database.

Usage:
    cd backend && uv run python -m scripts.seed_assets

Or via Makefile:
    make seed
"""

import asyncio
import sys
from pathlib import Path

import httpx

# Add backend to path so we can import app modules
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from sqlalchemy import select

from app.config import settings
from app.database import async_session, engine
from app.assets.models import Asset
from app.anomalies.models import AnomalyEvent  # noqa: F401 — needed for relationship resolution


# Mapping: CoinGecko id → Binance trading pair
# Only coins that have a USDT pair on Binance
BINANCE_SYMBOL_MAP = {
    "bitcoin": "BTCUSDT",
    "ethereum": "ETHUSDT",
    "binancecoin": "BNBUSDT",
    "solana": "SOLUSDT",
    "ripple": "XRPUSDT",
    "cardano": "ADAUSDT",
    "dogecoin": "DOGEUSDT",
    "avalanche-2": "AVAXUSDT",
    "polkadot": "DOTUSDT",
    "chainlink": "LINKUSDT",
    "uniswap": "UNIUSDT",
    "shiba-inu": "SHIBUSDT",
    "litecoin": "LTCUSDT",
    "cosmos": "ATOMUSDT",
    "near": "NEARUSDT",
    "bitcoin-cash": "BCHUSDT",
    "aptos": "APTUSDT",
    "filecoin": "FILUSDT",
    "arbitrum": "ARBUSDT",
    "optimism": "OPUSDT",
    "immutable-x": "IMXUSDT",
    "injective-protocol": "INJUSDT",
    "stacks": "STXUSDT",
    "sei-network": "SEIUSDT",
    "sui": "SUIUSDT",
    "pepe": "PEPEUSDT",
    "render-token": "RENDERUSDT",
    "hedera-hashgraph": "HBARUSDT",
    "celestia": "TIAUSDT",
    "the-graph": "GRTUSDT",
}


async def fetch_top_coins_from_coingecko() -> list[dict]:
    """Fetch top coins by market cap from CoinGecko."""
    url = f"{settings.COINGECKO_BASE_URL}/coins/markets"
    params = {
        "vs_currency": "usd",
        "order": "market_cap_desc",
        "per_page": 50,  # Fetch extra to filter for Binance availability
        "page": 1,
        "sparkline": "false",
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        print(f"Fetching top coins from CoinGecko: {url}")
        resp = await client.get(url, params=params)
        resp.raise_for_status()
        return resp.json()


def filter_and_map_coins(coins: list[dict], limit: int = 25) -> list[dict]:
    """Filter coins that have Binance USDT pairs, map to our Asset format."""
    result = []
    for coin in coins:
        cg_id = coin["id"]
        binance_symbol = BINANCE_SYMBOL_MAP.get(cg_id)
        if not binance_symbol:
            continue

        result.append(
            {
                "symbol": coin["symbol"].upper(),
                "name": coin["name"],
                "binance_symbol": binance_symbol,
                "coingecko_id": cg_id,
                "market_cap_rank": coin.get("market_cap_rank"),
                "is_active": True,
                "metadata_": {
                    "image": coin.get("image"),
                    "market_cap": coin.get("market_cap"),
                    "current_price": coin.get("current_price"),
                },
            }
        )

        if len(result) >= limit:
            break

    return result


async def seed_assets() -> None:
    """Main seed function."""
    print("=== MarketPulse AI — Asset Seed ===\n")

    # Fetch from CoinGecko
    try:
        coins = await fetch_top_coins_from_coingecko()
        print(f"Fetched {len(coins)} coins from CoinGecko")
    except httpx.HTTPError as e:
        print(f"Error fetching from CoinGecko: {e}")
        print("Falling back to hardcoded list...")
        coins = []

    # If CoinGecko fails, use hardcoded fallback
    if not coins:
        mapped = [
            {
                "symbol": sym.replace("USDT", ""),
                "name": sym.replace("USDT", ""),
                "binance_symbol": sym,
                "coingecko_id": cg_id,
                "market_cap_rank": idx + 1,
                "is_active": True,
                "metadata_": {},
            }
            for idx, (cg_id, sym) in enumerate(list(BINANCE_SYMBOL_MAP.items())[:25])
        ]
    else:
        mapped = filter_and_map_coins(coins, limit=25)

    print(f"Mapped {len(mapped)} coins with Binance pairs\n")

    # Insert into database
    async with async_session() as session:
        inserted = 0
        skipped = 0

        for coin_data in mapped:
            # Check if already exists
            existing = await session.execute(
                select(Asset).where(Asset.symbol == coin_data["symbol"])
            )
            if existing.scalar_one_or_none():
                print(f"  SKIP {coin_data['symbol']:>8s} — already exists")
                skipped += 1
                continue

            asset = Asset(**coin_data)
            session.add(asset)
            print(
                f"  ADD  {coin_data['symbol']:>8s} — {coin_data['name']}"
                f" (Binance: {coin_data['binance_symbol']})"
            )
            inserted += 1

        await session.commit()

    print(f"\nDone: {inserted} inserted, {skipped} skipped")
    print(f"Total assets with Binance pairs: {inserted + skipped}")


if __name__ == "__main__":
    asyncio.run(seed_assets())
