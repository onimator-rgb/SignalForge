"""Background price feeds for crypto (Binance WebSocket) and stocks (Yahoo polling).

Crypto: Binance combined mini-ticker WebSocket stream — real-time price updates.
Stocks: Yahoo Finance REST polling every 60s (during market hours).

Both run as asyncio tasks inside the FastAPI process.
"""

import asyncio
import json
from datetime import datetime, timezone

import httpx

from app.config import settings
from app.live.cache import LivePrice, set_price
from app.logging_config import get_logger
from app.system.diagnostics import _is_us_market_expected_open

log = get_logger(__name__)

STOCK_POLL_SECONDS = 60
WS_RECONNECT_DELAY = 5  # seconds before reconnect attempt
WS_MAX_RECONNECT_DELAY = 60

_tasks: list[asyncio.Task] = []


async def start_pollers(crypto_symbols: list[tuple[str, str]],
                        stock_symbols: list[tuple[str, str]]) -> None:
    """Start background feed tasks."""
    if crypto_symbols:
        task = asyncio.create_task(_crypto_ws_loop(crypto_symbols))
        _tasks.append(task)
        log.info("live.ws_connect_start", symbols=len(crypto_symbols))

    if stock_symbols:
        task = asyncio.create_task(_stock_poll_loop(stock_symbols))
        _tasks.append(task)
        log.info("live_prices.stream_start", source="yahoo_poll", symbols=len(stock_symbols))


def stop_pollers() -> None:
    for task in _tasks:
        task.cancel()
    _tasks.clear()
    log.info("live_prices.stream_stopped")


# ── Crypto WebSocket (Binance) ────────────────────

async def _crypto_ws_loop(symbols: list[tuple[str, str]]) -> None:
    """Maintain Binance WebSocket connection with auto-reconnect."""
    import websockets

    # Build stream URL: wss://stream.binance.com:9443/stream?streams=btcusdt@miniTicker/ethusdt@miniTicker/...
    provider_map = {ps.lower(): s for s, ps in symbols}  # btcusdt → BTC
    streams = "/".join(f"{ps.lower()}@miniTicker" for _, ps in symbols)
    ws_url = f"wss://stream.binance.com:9443/stream?streams={streams}"

    reconnect_delay = WS_RECONNECT_DELAY
    update_count = 0

    while True:
        try:
            async with websockets.connect(ws_url, ping_interval=20, ping_timeout=10) as ws:
                log.info("live.ws_connect_done", symbols=len(symbols), url="stream.binance.com")
                reconnect_delay = WS_RECONNECT_DELAY  # reset on success
                update_count = 0

                async for raw_msg in ws:
                    try:
                        msg = json.loads(raw_msg)
                        data = msg.get("data", {})
                        stream_symbol = data.get("s", "").lower()  # e.g. "btcusdt"

                        our_symbol = provider_map.get(stream_symbol)
                        if not our_symbol:
                            continue

                        price = float(data.get("c", 0))  # close price
                        if price <= 0:
                            continue

                        # miniTicker fields: s=symbol, c=close, o=open, h=high, l=low, v=volume
                        open_price = float(data.get("o", 0))
                        change_pct = None
                        if open_price > 0:
                            change_pct = round((price - open_price) / open_price * 100, 2)

                        set_price(our_symbol, LivePrice(
                            symbol=our_symbol,
                            asset_class="crypto",
                            price=price,
                            change_24h_pct=change_pct,
                            source="binance_ws",
                            updated_at=datetime.now(timezone.utc),
                        ))

                        update_count += 1
                        if update_count % 500 == 0:
                            log.debug("live.cache_update", source="binance_ws", total_updates=update_count)

                    except (json.JSONDecodeError, KeyError, ValueError) as e:
                        log.debug("live.ws_message_error", error=str(e))

        except asyncio.CancelledError:
            log.info("live.ws_disconnect", reason="cancelled")
            return
        except Exception as e:
            log.warning("live.ws_reconnect", error=str(e), delay=reconnect_delay)
            await asyncio.sleep(reconnect_delay)
            reconnect_delay = min(reconnect_delay * 2, WS_MAX_RECONNECT_DELAY)


# ── Stock poller (Yahoo Finance) — unchanged ──────

async def _stock_poll_loop(symbols: list[tuple[str, str]]) -> None:
    """Poll Yahoo Finance for stock prices."""
    while True:
        try:
            now = datetime.now(timezone.utc)

            if not _is_us_market_expected_open(now):
                await asyncio.sleep(STOCK_POLL_SECONDS * 5)
                continue

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
            if hasattr(data.columns, "levels"):
                for ticker in data.columns.get_level_values(1).unique():
                    close = data[("Close", ticker)].dropna()
                    if len(close) > 0:
                        result[ticker] = {"price": float(close.iloc[-1]), "change_pct": None}
            else:
                if "Close" in data.columns and len(data) > 0:
                    result[tickers_str.strip()] = {"price": float(data["Close"].iloc[-1]), "change_pct": None}
    except Exception:
        pass
    return result
