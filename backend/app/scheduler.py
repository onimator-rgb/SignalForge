"""APScheduler setup — periodic ingestion jobs.

Runs inside the FastAPI process. Disabled by default for safe local dev.
Enable via SCHEDULER_ENABLED=true in .env.
"""

import asyncio

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.config import settings
from app.database import async_session
from app.ingestion.providers.binance import BinanceProvider
from app.ingestion.service import run_ingestion
from app.logging_config import get_logger

log = get_logger(__name__)

scheduler = AsyncIOScheduler()


async def _scheduled_ingestion(interval: str) -> None:
    """Job callback: run ingestion for all active assets."""
    log.info("scheduled_ingestion_start", interval=interval)
    try:
        async with async_session() as db:
            provider = BinanceProvider()
            job = await run_ingestion(db=db, provider=provider, interval=interval)
            log.info(
                "scheduled_ingestion_done",
                interval=interval,
                status=job.status,
                assets_ok=job.assets_success,
                assets_fail=job.assets_failed,
                inserted=job.records_inserted,
                duration_ms=job.duration_ms,
            )
    except Exception as e:
        log.error("scheduled_ingestion_error", interval=interval, error=str(e), exc_info=True)


def start_scheduler() -> None:
    """Register scheduled jobs and start the scheduler."""
    if not settings.SCHEDULER_ENABLED:
        log.info(
            "scheduler_disabled",
            hint="Set SCHEDULER_ENABLED=true in .env to enable automatic ingestion",
        )
        return

    scheduler.add_job(
        lambda: asyncio.ensure_future(_scheduled_ingestion("1h")),
        trigger=IntervalTrigger(minutes=settings.INGESTION_INTERVAL_MINUTES),
        id="ingest_1h",
        name="Ingest 1h candles",
        replace_existing=True,
    )

    scheduler.start()
    log.info(
        "scheduler_started",
        interval_minutes=settings.INGESTION_INTERVAL_MINUTES,
        jobs=["ingest_1h"],
        next_run="immediately + every {m}m".format(m=settings.INGESTION_INTERVAL_MINUTES),
    )

    # Run once immediately on startup so data is fresh
    asyncio.ensure_future(_scheduled_ingestion("1h"))
    log.info("scheduler_initial_run_triggered")


def stop_scheduler() -> None:
    """Gracefully shut down the scheduler."""
    if scheduler.running:
        scheduler.shutdown(wait=False)
        log.info("scheduler_stopped")
