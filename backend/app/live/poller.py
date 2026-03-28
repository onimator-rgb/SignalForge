"""Background price pollers for crypto (Binance) and stocks (Yahoo Finance).

Crypto: polls Binance /api/v3/ticker/price every 10 seconds (batch).
Stocks: polls Yahoo Finance every 60 seconds (during market hours).

Both run as asyncio tasks inside the FastAPI process.
"""

import asyncio
from datetime import datetime, timezone

import httpx

from app.config import settings
from app.live.cache import LivePrice, set_price
from app.logging_config import get_logger
from app.system.diagnostics import _is_us_market_expected_open

log = get_logger(__name__)

# Polling intervals
CRYPTO_POLL_SECONDS = 10
STOCK_POLL_SECONDS = 60

_tasks: list[asyncio.Task] = []


async def start_pollers(crypto_symbols: list[tuple[str, str]],
                        stock_symbols: list[tuple[str, str]]) -> None:
    """Start background polling tasks.

    Args:
        crypto_symbols: list of (symbol, provider_symbol) e.g. [("BTC", "BTCUSDT")]
        stock_symbols: list of (symbol, provider_symbol) e.g. [("AAPL", "AAPL")]
    """
    if crypto_symbols:
        task = asyncio.create_task(_crypto_poll_loop(crypto_symbols))
        _tasks.append(task)
        log.info("live_prices.stream_start", source="binance_poll", symbols=len(crypto_symbols))

    if stock_symbols:
        task = asyncio.create_task(_stock_poll_loop(stock_symbols))
        _tasks.append(task)
        log.info("live_prices.stream_start", source="yahoo_poll", symbols=len(stock_symbols))


def stop_pollers() -> None:
    for task in _tasks:
        task.cancel()
    _tasks.clear()
    log.info("live_prices.stream_stopped")


# ── Crypto poller (Binance REST) ─────────────────

async def _crypto_poll_loop(symbols: list[tuple[str, str]]) -> None:
    """Poll Binance ticker prices in a loop."""
    base_url = settings.BINANCE_BASE_URL.rstrip("/")
    provider_map = {ps: s for s, ps in symbols}  # BTCUSDT → BTC

    while True:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                # Batch: get all tickers at once
                resp = await client.get(f"{base_url}/api/v3/ticker/24hr")
                resp.raise_for_status()
                tickers = resp.json()

            now = datetime.now(timezone.utc)
            updated = 0
            for t in tickers:
                sym = t.get("symbol")
                if sym not in provider_map:
                    continue
                our_symbol = provider_map[sym]
                price = float(t.get("lastPrice", 0))
                change_pct = float(t.get("priceChangePercent", 0))
                if price > 0:
                    set_price(our_symbol, LivePrice(
                        symbol=our_symbol,
                        asset_class="crypto",
                        price=price,
                        change_24h_pct=round(change_pct, 2),
                        source="binance_poll",
                        updated_at=now,
                    ))
                    updated += 1

            if updated > 0:
                log.debug("live_prices.cache_update", source="binance", updated=updated)

        except asyncio.CancelledError:
            return
        except Exception as e:
            log.warning("live_prices.stream_error", source="binance", error=str(e))

        await asyncio.sleep(CRYPTO_POLL_SECONDS)


# ── Stock poller (Yahoo Finance) ─────────────────

async def _stock_poll_loop(symbols: list[tuple[str, str]]) -> None:
    """Poll Yahoo Finance for stock prices."""
    while True:
        try:
            now = datetime.now(timezone.utc)

            # Only poll during US market hours (skip weekends/nights)
            if not _is_us_market_expected_open(now):
                await asyncio.sleep(STOCK_POLL_SECONDS * 5)  # Slow poll outside hours
                continue

            # Use yfinance in thread
            tickers_str = " ".join(ps for _, ps in symbols)
            prices = await asyncio.to_thread(_fetch_stock_prices, tickers_str)

            now = datetime.now(timezone.utc)
            updated = 0
            symbol_map = {ps: s for s, ps in symbols}
            for ticker, data in prices.items():
                our_symbol = symbol_map.get(ticker)
                if our_symbol and data.get("price", 0) > 0:
                    set_price(our_symbol, LivePrice(
                        symbol=our_symbol,
                        asset_class="stock",
                        price=data["price"],
                        change_24h_pct=data.get("change_pct"),
                        source="yahoo_poll",
                        updated_at=now,
                    ))
                    updated += 1

            if updated > 0:
                log.debug("live_prices.cache_update", source="yahoo", updated=updated)

        except asyncio.CancelledError:
            return
        except Exception as e:
            log.warning("live_prices.stream_error", source="yahoo", error=str(e))

        await asyncio.sleep(STOCK_POLL_SECONDS)


def _fetch_stock_prices(tickers_str: str) -> dict:
    """Synchronous Yahoo Finance fetch (runs in thread)."""
    import yfinance as yf

    result = {}
    try:
        data = yf.download(tickers_str, period="1d", interval="1d", progress=False, threads=False)
        if data is not None and not data.empty:
            # For multiple tickers, columns are MultiIndex
            if hasattr(data.columns, "levels"):
                for ticker in data.columns.get_level_values(1).unique():
                    close = data[("Close", ticker)].dropna()
                    if len(close) > 0:
                        price = float(close.iloc[-1])
                        result[ticker] = {"price": price, "change_pct": None}
            else:
                # Single ticker
                if "Close" in data.columns and len(data) > 0:
                    price = float(data["Close"].iloc[-1])
                    result[tickers_str.strip()] = {"price": price, "change_pct": None}
    except Exception:
        pass
    return result
