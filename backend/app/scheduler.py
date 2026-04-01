"""Periodic scheduler — asyncio task-based ingestion jobs.

Replaces APScheduler with simple asyncio.create_task loops.
This avoids event loop ownership issues between APScheduler and uvicorn.

Jobs:
  - crypto ingestion 1h: every INGESTION_INTERVAL_MINUTES (default 5min)
  - stock ingestion 1h: every 15min
  - crypto ingestion 4h: every 4 hours
  - stock ingestion 4h: every 4 hours
  - crypto ingestion 1d: every 24 hours
  - stock ingestion 1d: every 24 hours
"""

import asyncio
import time as _time
from datetime import datetime, timezone

from app.config import settings
from app.database import async_session
from app.ingestion.service import run_ingestion
from app.logging_config import get_logger

log = get_logger(__name__)

_tasks: list[asyncio.Task] = []
_job_stats: dict[str, dict] = {}


def _get_provider(asset_class: str):
    """Return the appropriate provider for an asset class."""
    if asset_class == "stock":
        from app.ingestion.providers.yahoo import YahooFinanceProvider
        return YahooFinanceProvider()
    else:
        from app.ingestion.providers.binance import BinanceProvider
        return BinanceProvider()


async def _run_job(job_name: str, interval: str, asset_class: str) -> None:
    """Execute one ingestion cycle with heartbeat + stats tracking."""
    stats = _job_stats.setdefault(job_name, {"run_count": 0, "error_count": 0, "last_started_at": None, "last_completed_at": None})
    stats["last_started_at"] = datetime.now(timezone.utc)
    stats["run_count"] += 1

    log.info("scheduler.job_started", job=job_name, asset_class=asset_class, run_count=stats["run_count"])
    t_start = _time.monotonic()

    try:
        from app.system.runtime import heartbeat_quick
        await heartbeat_quick("scheduler", {"job": job_name})

        async with async_session() as db:
            provider = _get_provider(asset_class)
            job = await run_ingestion(
                db=db,
                provider=provider,
                interval=interval,
                asset_class=asset_class,
            )

            duration_ms = int((_time.monotonic() - t_start) * 1000)
            stats["last_completed_at"] = datetime.now(timezone.utc)

            log.info(
                "scheduler.job_done",
                job=job_name,
                asset_class=asset_class,
                status=job.status,
                assets_ok=job.assets_success,
                assets_fail=job.assets_failed,
                inserted=job.records_inserted,
                duration_ms=duration_ms,
                run_count=stats["run_count"],
            )

            comp = f"ingestion_{asset_class}"
            await heartbeat_quick(comp, {"status": job.status, "ok": job.assets_success})

    except Exception as e:
        stats["error_count"] += 1
        duration_ms = int((_time.monotonic() - t_start) * 1000)
        log.error("scheduler.job_error", job=job_name, error=str(e), duration_ms=duration_ms)


async def _periodic_loop(job_name: str, interval_str: str, asset_class: str, interval_seconds: int) -> None:
    """Run a job periodically forever."""
    # Initial run immediately
    await _run_job(job_name, interval_str, asset_class)

    while True:
        try:
            _job_stats.setdefault(job_name, {})["next_run_at"] = (
                datetime.now(timezone.utc).isoformat()
            )
            await asyncio.sleep(interval_seconds)
            await _run_job(job_name, interval_str, asset_class)
        except asyncio.CancelledError:
            log.info("scheduler.job_cancelled", job=job_name)
            return
        except Exception as e:
            log.error("scheduler.loop_error", job=job_name, error=str(e))
            await asyncio.sleep(30)  # Brief pause on error before retry


async def start_scheduler() -> None:
    """Start periodic ingestion tasks. Call from async context (lifespan)."""
    if not settings.SCHEDULER_ENABLED:
        log.info("scheduler_disabled", hint="Set SCHEDULER_ENABLED=true in .env")
        return

    interval_sec = settings.INGESTION_INTERVAL_MINUTES * 60

    # Crypto: every N minutes
    task = asyncio.create_task(
        _periodic_loop("ingest_crypto_1h", "1h", "crypto", interval_sec)
    )
    _tasks.append(task)

    # Stocks: every 15 minutes
    task = asyncio.create_task(
        _periodic_loop("ingest_stock_1h", "1h", "stock", 15 * 60)
    )
    _tasks.append(task)

    # Crypto 4h: every 4 hours
    task = asyncio.create_task(
        _periodic_loop("ingest_crypto_4h", "4h", "crypto", 4 * 3600)
    )
    _tasks.append(task)

    # Stocks 4h: every 4 hours
    task = asyncio.create_task(
        _periodic_loop("ingest_stock_4h", "4h", "stock", 4 * 3600)
    )
    _tasks.append(task)

    # Crypto 1d: every 24 hours
    task = asyncio.create_task(
        _periodic_loop("ingest_crypto_1d", "1d", "crypto", 24 * 3600)
    )
    _tasks.append(task)

    # Stocks 1d: every 24 hours
    task = asyncio.create_task(
        _periodic_loop("ingest_stock_1d", "1d", "stock", 24 * 3600)
    )
    _tasks.append(task)

    log.info(
        "scheduler_started",
        crypto_interval_sec=interval_sec,
        stock_interval_sec=15 * 60,
        jobs=[
            "ingest_crypto_1h", "ingest_stock_1h",
            "ingest_crypto_4h", "ingest_stock_4h",
            "ingest_crypto_1d", "ingest_stock_1d",
        ],
    )


def stop_scheduler() -> None:
    """Cancel all periodic tasks."""
    for task in _tasks:
        task.cancel()
    _tasks.clear()
    log.info("scheduler_stopped")


def get_scheduler_status() -> dict:
    """Get scheduler job stats for diagnostics."""
    now = datetime.now(timezone.utc)
    jobs = {}
    for name, stats in _job_stats.items():
        last = stats.get("last_completed_at")
        age_sec = round((now - last).total_seconds(), 1) if last else None
        jobs[name] = {
            "run_count": stats.get("run_count", 0),
            "error_count": stats.get("error_count", 0),
            "last_started_at": stats.get("last_started_at", "").isoformat() if stats.get("last_started_at") else None,
            "last_completed_at": last.isoformat() if last else None,
            "age_sec": age_sec,
            "healthy": age_sec is not None and age_sec < 1200,
        }
    return {
        "running": len(_tasks) > 0,
        "task_count": len(_tasks),
        "jobs": jobs,
    }
