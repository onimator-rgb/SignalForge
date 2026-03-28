"""In-memory live price cache.

Thread-safe dict holding latest prices per asset symbol.
Updated by background polling tasks.
Read by API endpoints.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from threading import Lock


@dataclass
class LivePrice:
    symbol: str
    asset_class: str
    price: float
    change_24h_pct: float | None
    source: str  # "binance_poll", "yahoo_poll", "db_snapshot"
    updated_at: datetime


_cache: dict[str, LivePrice] = {}
_lock = Lock()


def set_price(symbol: str, price: LivePrice) -> None:
    with _lock:
        _cache[symbol] = price


def get_price(symbol: str) -> LivePrice | None:
    with _lock:
        return _cache.get(symbol)


def get_all_prices() -> dict[str, LivePrice]:
    with _lock:
        return dict(_cache)


def clear() -> None:
    with _lock:
        _cache.clear()
