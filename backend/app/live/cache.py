"""In-memory live price cache with SSE batch broadcast.

Thread-safe dict holding latest prices per asset symbol.
Updated by Binance WS / Yahoo polling.
Broadcasts batched updates to SSE subscribers every BATCH_INTERVAL_MS.
"""

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
from threading import Lock

BATCH_INTERVAL_MS = 800  # Coalesce updates over this window


@dataclass
class LivePrice:
    symbol: str
    asset_class: str
    price: float
    change_24h_pct: float | None
    source: str
    updated_at: datetime


# ── Cache ───────���─────────────────────────────────

_cache: dict[str, LivePrice] = {}
_lock = Lock()

# Pending updates buffer (symbol → latest price, coalesced)
_pending: dict[str, LivePrice] = {}
_pending_lock = Lock()


def set_price(symbol: str, price: LivePrice) -> None:
    with _lock:
        _cache[symbol] = price
    with _pending_lock:
        _pending[symbol] = price


def get_price(symbol: str) -> LivePrice | None:
    with _lock:
        return _cache.get(symbol)


def get_all_prices() -> dict[str, LivePrice]:
    with _lock:
        return dict(_cache)


def clear() -> None:
    with _lock:
        _cache.clear()


# ── SSE Subscribers ───────���───────────────────────

_subscribers: set[asyncio.Queue] = set()
_sub_lock = Lock()

# Diagnostics counters
_stats = {
    "batches_sent": 0,
    "events_dropped": 0,
    "ws_reconnect_count": 0,
    "ws_last_message_at": None,
    "ws_connected": False,
    "stock_poller_last_run": None,
}
_stats_lock = Lock()


def subscribe() -> asyncio.Queue:
    q: asyncio.Queue = asyncio.Queue(maxsize=50)
    with _sub_lock:
        _subscribers.add(q)
    return q


def unsubscribe(q: asyncio.Queue) -> None:
    with _sub_lock:
        _subscribers.discard(q)


def subscriber_count() -> int:
    with _sub_lock:
        return len(_subscribers)


def update_stat(key: str, value) -> None:
    with _stats_lock:
        _stats[key] = value


def increment_stat(key: str, amount: int = 1) -> None:
    with _stats_lock:
        _stats[key] = _stats.get(key, 0) + amount


def get_stats() -> dict:
    with _stats_lock:
        return dict(_stats)


# ── Batch broadcaster (runs as asyncio task) ──────

async def batch_broadcaster() -> None:
    """Flush pending updates to subscribers as batched SSE events."""
    import json
    from app.logging_config import get_logger
    log = get_logger("live.broadcaster")

    while True:
        await asyncio.sleep(BATCH_INTERVAL_MS / 1000.0)

        # Drain pending buffer
        with _pending_lock:
            if not _pending:
                continue
            batch = dict(_pending)
            _pending.clear()

        # Build batch payload
        now = datetime.now(timezone.utc)
        items = []
        for p in batch.values():
            age = (now - p.updated_at).total_seconds()
            freshness = "live" if age < 30 else "recent" if age < 120 else "delayed"
            items.append({
                "symbol": p.symbol,
                "asset_class": p.asset_class,
                "price": p.price,
                "change_24h_pct": p.change_24h_pct,
                "source": p.source,
                "freshness": freshness,
                "updated_at": p.updated_at.isoformat(),
            })

        payload = json.dumps({"type": "price_batch", "items": items})
        sse_data = f"data: {payload}\n\n"

        # Publish to subscribers
        dropped = 0
        with _sub_lock:
            for q in _subscribers:
                try:
                    q.put_nowait(sse_data)
                except asyncio.QueueFull:
                    # Slow subscriber — drop and count
                    dropped += 1

        increment_stat("batches_sent")
        if dropped:
            increment_stat("events_dropped", dropped)
            log.debug("live.sse_drop_warn", dropped=dropped, subscribers=subscriber_count())
