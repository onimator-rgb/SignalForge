"""Runtime resilience — heartbeat, watchdog, recovery.

Components tracked:
  backend_app, scheduler, ingestion_crypto, ingestion_stock,
  evaluation, live_crypto_ws, live_stock_poller
"""

import asyncio
from datetime import datetime, timedelta, timezone

from sqlalchemy import text, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.database import async_session
from app.logging_config import get_logger

log = get_logger(__name__)

# Watchdog thresholds (seconds)
THRESHOLDS = {
    "backend_app": 600,
    "scheduler": 600,
    "ingestion_crypto": 1200,
    "ingestion_stock": 2700,
    "evaluation": 3600,
    "live_crypto_ws": 60,
    "live_stock_poller": 600,
}

_watchdog_task = None


async def heartbeat(db: AsyncSession, component: str, meta: dict | None = None) -> None:
    """Update heartbeat for a component (upsert)."""
    now = datetime.now(timezone.utc)
    await db.execute(text(
        "INSERT INTO runtime_heartbeats (component, status, last_seen_at, meta, updated_at) "
        "VALUES (:c, 'ok', :now, :meta, :now) "
        "ON CONFLICT (component) DO UPDATE SET "
        "status = 'ok', last_seen_at = :now, meta = :meta, updated_at = :now"
    ), {"c": component, "now": now, "meta": meta})
    await db.commit()


async def heartbeat_quick(component: str, meta: dict | None = None) -> None:
    """Fire-and-forget heartbeat (creates own session)."""
    try:
        async with async_session() as db:
            await heartbeat(db, component, meta)
    except Exception:
        pass  # Never block caller


async def get_runtime_status(db: AsyncSession) -> dict:
    """Compute overall runtime status from heartbeats."""
    now = datetime.now(timezone.utc)
    result = await db.execute(text("SELECT component, status, last_seen_at, meta FROM runtime_heartbeats"))
    rows = result.fetchall()

    components = {}
    overall = "ok"

    for row in rows:
        age_sec = (now - row.last_seen_at).total_seconds()
        threshold = THRESHOLDS.get(row.component, 600)

        if age_sec > threshold * 3:
            status = "down"
        elif age_sec > threshold:
            status = "stale"
        else:
            status = "ok"

        if status == "down":
            overall = "down"
        elif status == "stale" and overall != "down":
            overall = "degraded"

        components[row.component] = {
            "status": status,
            "last_seen_at": row.last_seen_at.isoformat(),
            "age_sec": round(age_sec, 1),
            "threshold_sec": threshold,
            "meta": row.meta,
        }

    # Check for missing expected components
    for comp in THRESHOLDS:
        if comp not in components:
            components[comp] = {"status": "missing", "last_seen_at": None, "age_sec": None}
            if overall == "ok":
                overall = "degraded"

    return {"overall": overall, "components": components, "checked_at": now.isoformat()}


async def run_watchdog(db: AsyncSession) -> dict:
    """Run watchdog check — update heartbeat statuses, log warnings."""
    log.debug("runtime.watchdog_start")
    status = await get_runtime_status(db)

    warnings = []
    for comp, info in status["components"].items():
        if info["status"] in ("stale", "down", "missing"):
            warnings.append(f"{comp}: {info['status']} (age={info.get('age_sec')}s)")
            log.warning("runtime.watchdog_warn", component=comp, status=info["status"],
                        age_sec=info.get("age_sec"))

    # Update own heartbeat
    await heartbeat(db, "backend_app")

    log.debug("runtime.watchdog_done", overall=status["overall"], warnings=len(warnings))
    return {**status, "warnings": warnings}


async def run_pending_evaluation(db: AsyncSession) -> dict:
    """Recovery: run evaluation for pending recommendations."""
    log.info("runtime.recovery_evaluate_pending_start")
    from app.recommendations.evaluation import evaluate_recommendations
    result = await evaluate_recommendations(db)
    log.info("runtime.recovery_evaluate_pending_done", **result)
    await heartbeat(db, "evaluation", meta=result)
    return result


# ── Independent scheduled jobs ────────────────────

async def start_runtime_jobs() -> None:
    """Start independent evaluation + watchdog periodic tasks."""
    global _watchdog_task

    async def _eval_loop():
        """Independent evaluation every 15 min."""
        while True:
            try:
                await asyncio.sleep(900)  # 15 min
                async with async_session() as db:
                    result = await run_pending_evaluation(db)
            except asyncio.CancelledError:
                return
            except Exception as e:
                log.error("runtime.eval_loop_error", error=str(e))

    async def _watchdog_loop():
        """Watchdog every 5 min."""
        while True:
            try:
                await asyncio.sleep(300)  # 5 min
                async with async_session() as db:
                    await run_watchdog(db)
            except asyncio.CancelledError:
                return
            except Exception as e:
                log.error("runtime.watchdog_loop_error", error=str(e))

    _tasks = [
        asyncio.create_task(_eval_loop()),
        asyncio.create_task(_watchdog_loop()),
    ]
    log.info("runtime.jobs_started", jobs=["eval_15m", "watchdog_5m"])
    return _tasks


def stop_runtime_jobs(tasks: list) -> None:
    for t in tasks:
        t.cancel()
