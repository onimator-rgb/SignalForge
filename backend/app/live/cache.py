"""In-memory live price cache with SSE broadcast support.

Thread-safe dict holding latest prices per asset symbol.
Updated by background polling/WS tasks.
Read by API endpoints and pushed to SSE subscribers.
"""

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
from threading import Lock


@dataclass
class LivePrice:
    symbol: str
    asset_class: str
    price: float
    change_24h_pct: float | None
    source: str  # "binance_ws", "yahoo_poll", "db_snapshot"
    updated_at: datetime


_cache: dict[str, LivePrice] = {}
_lock = Lock()

# SSE subscribers: set of asyncio.Queue
_subscribers: set[asyncio.Queue] = set()
_sub_lock = Lock()


def set_price(symbol: str, price: LivePrice) -> None:
    with _lock:
        _cache[symbol] = price
    # Notify SSE subscribers (non-blocking)
    _broadcast(price)


def get_price(symbol: str) -> LivePrice | None:
    with _lock:
        return _cache.get(symbol)


def get_all_prices() -> dict[str, LivePrice]:
    with _lock:
        return dict(_cache)


def clear() -> None:
    with _lock:
        _cache.clear()


# ── SSE pub-sub ───────────────────────────────────

def subscribe() -> asyncio.Queue:
    """Register a new SSE subscriber. Returns a queue to read from."""
    q: asyncio.Queue = asyncio.Queue(maxsize=100)
    with _sub_lock:
        _subscribers.add(q)
    return q


def unsubscribe(q: asyncio.Queue) -> None:
    """Remove an SSE subscriber."""
    with _sub_lock:
        _subscribers.discard(q)


def _broadcast(price: LivePrice) -> None:
    """Push update to all subscribers (drop if queue full)."""
    with _sub_lock:
        for q in _subscribers:
            try:
                q.put_nowait(price)
            except asyncio.QueueFull:
                pass  # Drop oldest — subscriber is slow


def subscriber_count() -> int:
    with _sub_lock:
        return len(_subscribers)
