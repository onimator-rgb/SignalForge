"""Diagnostics endpoints — sync freshness, config view, recent errors."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.error_buffer import error_count, get_recent_errors
from app.database import get_db

router = APIRouter(prefix="/api/v1/diagnostics", tags=["diagnostics"])

# Freshness thresholds: how many minutes before a sync is considered stale
STALE_THRESHOLDS = {
    "5m": 15,
    "1h": 120,
    "1d": 1500,  # ~25 hours
}

# US market hours (Eastern Time = UTC-4 / UTC-5 depending on DST)
# Simplified: Mon-Fri 13:30-20:00 UTC (covers both EST and EDT)
US_MARKET_OPEN_UTC_HOUR = 13   # 9:00 AM ET (conservative, covers EDT)
US_MARKET_CLOSE_UTC_HOUR = 21  # 5:00 PM ET (with buffer after close)


def _is_us_market_expected_open(now_utc: datetime) -> bool:
    """Check if US stock market is expected to have fresh data right now.

    Returns True during trading hours (Mon-Fri ~9:30-16:00 ET) plus a buffer.
    Returns False on weekends and outside hours — stocks are NOT stale then.
    """
    weekday = now_utc.weekday()  # 0=Mon, 6=Sun
    if weekday >= 5:  # Saturday or Sunday
        return False
    hour = now_utc.hour
    return US_MARKET_OPEN_UTC_HOUR <= hour < US_MARKET_CLOSE_UTC_HOUR


@router.get("/sync")
async def sync_freshness(db: AsyncSession = Depends(get_db)):
    """Per-asset, per-interval sync freshness. Answers: 'which assets have stale data?'"""
    now_utc = datetime.now(timezone.utc)

    result = await db.execute(
        text("""
            SELECT
                a.symbol,
                a.asset_class,
                ps.interval,
                ps.last_bar_time,
                ps.sync_status,
                ps.consecutive_errors,
                ps.last_error,
                EXTRACT(EPOCH FROM (now() AT TIME ZONE 'UTC' - ps.last_bar_time)) / 60
                    AS minutes_ago
            FROM provider_sync_states ps
            JOIN assets a ON a.id = ps.asset_id
            WHERE a.is_active = true
            ORDER BY a.asset_class, a.market_cap_rank ASC NULLS LAST, ps.interval
        """)
    )
    rows = result.fetchall()

    items = []
    for r in rows:
        minutes_ago = round(r.minutes_ago, 1) if r.minutes_ago is not None else None
        threshold = STALE_THRESHOLDS.get(r.interval, 120)

        if r.last_bar_time is None:
            status = "no_data"
        elif r.sync_status == "error":
            status = "error"
        elif minutes_ago is not None and minutes_ago > threshold:
            # For stocks: don't mark stale outside market hours
            if r.asset_class == "stock" and not _is_us_market_expected_open(now_utc):
                status = "fresh"  # Market closed — gap is expected
            else:
                status = "stale"
        else:
            status = "fresh"

        items.append({
            "symbol": r.symbol,
            "asset_class": r.asset_class,
            "interval": r.interval,
            "last_bar_time": r.last_bar_time.isoformat() if r.last_bar_time else None,
            "minutes_ago": minutes_ago,
            "status": status,
            "consecutive_errors": r.consecutive_errors,
            "last_error": r.last_error,
        })

    fresh = sum(1 for i in items if i["status"] == "fresh")
    stale = sum(1 for i in items if i["status"] == "stale")
    no_data = sum(1 for i in items if i["status"] == "no_data")
    errors = sum(1 for i in items if i["status"] == "error")

    return {
        "summary": {"fresh": fresh, "stale": stale, "no_data": no_data, "error": errors},
        "items": items,
    }


@router.get("/config")
async def config_view(db: AsyncSession = Depends(get_db)):
    """Safe config subset — no secrets. Answers: 'what are the current settings?'"""
    db_ok = False
    try:
        r = await db.execute(text("SELECT 1"))
        db_ok = r.scalar() == 1
    except Exception:
        pass

    return {
        "app_env": settings.APP_ENV,
        "version": "0.1.0",
        "scheduler_enabled": settings.SCHEDULER_ENABLED,
        "ingestion_interval_minutes": settings.INGESTION_INTERVAL_MINUTES,
        "ingestion_backfill_days": settings.INGESTION_BACKFILL_DAYS,
        "anomaly_thresholds": {
            "price_zscore": settings.ANOMALY_PRICE_ZSCORE_THRESHOLD,
            "volume_zscore": settings.ANOMALY_VOLUME_ZSCORE_THRESHOLD,
            "rsi_upper": settings.ANOMALY_RSI_UPPER,
            "rsi_lower": settings.ANOMALY_RSI_LOWER,
        },
        "database_connected": db_ok,
        "log_level": settings.LOG_LEVEL,
    }


@router.get("/errors")
async def recent_errors(limit: int = 50):
    """Recent errors from in-memory buffer. Answers: 'what broke recently?'"""
    items = get_recent_errors(limit)
    return {
        "total_buffered": error_count(),
        "items": items,
    }
