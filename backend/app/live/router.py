"""Live prices endpoints — REST snapshot + SSE push stream + diagnostics."""

import asyncio
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.assets.models import Asset
from app.assets.service import get_latest_price
from app.database import get_db
from app.live.cache import (
    get_all_prices, get_stats,
    subscribe, unsubscribe, subscriber_count,
)
from app.logging_config import get_logger

log = get_logger(__name__)

router = APIRouter(prefix="/api/v1/live", tags=["live"])

SSE_HEARTBEAT_SECONDS = 20


def _freshness(updated_at: datetime) -> str:
    age_sec = (datetime.now(timezone.utc) - updated_at).total_seconds()
    if age_sec < 30:
        return "live"
    if age_sec < 120:
        return "recent"
    if age_sec < 600:
        return "delayed"
    return "stale"


# ── SSE stream (batched) ─────────────────────────

@router.get("/stream")
async def live_stream():
    """SSE stream of batched live price updates. Connect via EventSource."""

    async def event_generator():
        q = subscribe()
        log.info("live.sse_client_connect", subscribers=subscriber_count())
        try:
            while True:
                try:
                    # Queue now contains pre-formatted SSE strings from batch_broadcaster
                    sse_data = await asyncio.wait_for(q.get(), timeout=SSE_HEARTBEAT_SECONDS)
                    yield sse_data
                except asyncio.TimeoutError:
                    yield ": heartbeat\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            unsubscribe(q)
            log.info("live.sse_client_disconnect", subscribers=subscriber_count())

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ── REST snapshot ─────────────────────────────────

@router.get("/prices")
async def live_prices(db: AsyncSession = Depends(get_db)):
    """REST snapshot of latest prices (cache + DB fallback)."""
    result = await db.execute(
        select(Asset.id, Asset.symbol, Asset.asset_class)
        .where(Asset.is_active.is_(True))
        .order_by(Asset.asset_class, Asset.symbol)
    )
    assets = result.all()
    now = datetime.now(timezone.utc)

    cache = get_all_prices()
    items = []
    live_count = 0
    fallback_count = 0

    for asset_id, symbol, asset_class in assets:
        cached = cache.get(symbol)
        if cached and (now - cached.updated_at).total_seconds() < 600:
            items.append({
                "asset_id": str(asset_id),
                "symbol": symbol,
                "asset_class": asset_class,
                "price": cached.price,
                "change_24h_pct": cached.change_24h_pct,
                "source": cached.source,
                "updated_at": cached.updated_at.isoformat(),
                "freshness": _freshness(cached.updated_at),
            })
            live_count += 1
        else:
            price_data = await get_latest_price(db, asset_id)
            if price_data:
                items.append({
                    "asset_id": str(asset_id),
                    "symbol": symbol,
                    "asset_class": asset_class,
                    "price": price_data.close,
                    "change_24h_pct": price_data.change_24h_pct,
                    "source": "db_snapshot",
                    "updated_at": price_data.bar_time.isoformat(),
                    "freshness": "delayed",
                })
                fallback_count += 1
            else:
                items.append({
                    "asset_id": str(asset_id),
                    "symbol": symbol,
                    "asset_class": asset_class,
                    "price": None,
                    "change_24h_pct": None,
                    "source": "none",
                    "updated_at": None,
                    "freshness": "unavailable",
                })

    return {
        "count": len(items),
        "live": live_count,
        "fallback": fallback_count,
        "items": items,
    }


# ── Live diagnostics ─────────────────────────────

@router.get("/diagnostics")
async def live_diagnostics():
    """Live layer health: WS status, SSE subscribers, cache quality, broadcast stats."""
    now = datetime.now(timezone.utc)
    cache = get_all_prices()
    stats = get_stats()

    # Cache quality breakdown
    by_source: dict[str, int] = {}
    by_freshness: dict[str, int] = {}
    oldest_age = 0.0
    latest_age = float("inf") if cache else 0.0

    for p in cache.values():
        by_source[p.source] = by_source.get(p.source, 0) + 1
        f = _freshness(p.updated_at)
        by_freshness[f] = by_freshness.get(f, 0) + 1
        age = (now - p.updated_at).total_seconds()
        oldest_age = max(oldest_age, age)
        latest_age = min(latest_age, age) if age < latest_age else latest_age

    ws_last = stats.get("ws_last_message_at")

    return {
        "websocket": {
            "connected": stats.get("ws_connected", False),
            "last_message_at": ws_last.isoformat() if ws_last else None,
            "last_message_age_sec": round((now - ws_last).total_seconds(), 1) if ws_last else None,
            "reconnect_count": stats.get("ws_reconnect_count", 0),
        },
        "sse": {
            "subscribers": subscriber_count(),
            "batches_sent": stats.get("batches_sent", 0),
            "events_dropped": stats.get("events_dropped", 0),
        },
        "cache": {
            "size": len(cache),
            "by_source": by_source,
            "by_freshness": by_freshness,
            "oldest_age_sec": round(oldest_age, 1),
            "latest_age_sec": round(latest_age, 1) if cache else None,
        },
        "stock_poller": {
            "last_run": stats.get("stock_poller_last_run"),
        },
    }
