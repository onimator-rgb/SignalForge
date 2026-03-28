"""APScheduler setup — periodic ingestion jobs for crypto and stocks.

Runs inside the FastAPI process. Disabled by default for safe local dev.
Enable via SCHEDULER_ENABLED=true in .env.
"""

import asyncio

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.config import settings
from app.database import async_session
from app.ingestion.service import run_ingestion
from app.logging_config import get_logger

log = get_logger(__name__)

scheduler = AsyncIOScheduler()


def _get_provider(asset_class: str):
    """Return the appropriate provider for an asset class."""
    if asset_class == "stock":
        from app.ingestion.providers.yahoo import YahooFinanceProvider
        return YahooFinanceProvider()
    else:
        from app.ingestion.providers.binance import BinanceProvider
        return BinanceProvider()


async def _scheduled_ingestion(interval: str, asset_class: str) -> None:
    """Job callback: run ingestion for active assets of a given class."""
    log.info("scheduled_ingestion_start", interval=interval, asset_class=asset_class)
    try:
        async with async_session() as db:
            provider = _get_provider(asset_class)
            job = await run_ingestion(
                db=db,
                provider=provider,
                interval=interval,
                asset_class=asset_class,
            )
            log.info(
                "scheduled_ingestion_done",
                interval=interval,
                asset_class=asset_class,
                status=job.status,
                assets_ok=job.assets_success,
                assets_fail=job.assets_failed,
                inserted=job.records_inserted,
                duration_ms=job.duration_ms,
            )
    except Exception as e:
        log.error(
            "scheduled_ingestion_error",
            interval=interval,
            asset_class=asset_class,
            error=str(e),
            exc_info=True,
        )


def start_scheduler() -> None:
    """Register scheduled jobs and start the scheduler."""
    if not settings.SCHEDULER_ENABLED:
        log.info(
            "scheduler_disabled",
            hint="Set SCHEDULER_ENABLED=true in .env to enable automatic ingestion",
        )
        return

    interval_min = settings.INGESTION_INTERVAL_MINUTES

    # Crypto: every N minutes (24/7 market)
    scheduler.add_job(
        lambda: asyncio.ensure_future(_scheduled_ingestion("1h", "crypto")),
        trigger=IntervalTrigger(minutes=interval_min),
        id="ingest_crypto_1h",
        name="Ingest crypto 1h candles",
        replace_existing=True,
    )

    # Stocks: every 15 minutes (data is delayed anyway)
    scheduler.add_job(
        lambda: asyncio.ensure_future(_scheduled_ingestion("1h", "stock")),
        trigger=IntervalTrigger(minutes=15),
        id="ingest_stock_1h",
        name="Ingest stock 1h candles",
        replace_existing=True,
    )

    scheduler.start()
    log.info(
        "scheduler_started",
        crypto_interval_minutes=interval_min,
        stock_interval_minutes=15,
        jobs=["ingest_crypto_1h", "ingest_stock_1h"],
    )

    # Run once immediately on startup
    asyncio.ensure_future(_scheduled_ingestion("1h", "crypto"))
    asyncio.ensure_future(_scheduled_ingestion("1h", "stock"))
    log.info("scheduler_initial_run_triggered")


def stop_scheduler() -> None:
    """Gracefully shut down the scheduler."""
    if scheduler.running:
        scheduler.shutdown(wait=False)
        log.info("scheduler_stopped")
