"""Ingestion service — orchestrates data fetching, persistence, and sync state."""

import time as _time
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.assets.models import Asset
from app.ingestion.models import IngestionJob, ProviderSyncState
from app.ingestion.providers.base import BaseProvider, RawBar
from app.logging_config import get_logger
from app.market_data.models import PriceBar

log = get_logger(__name__)

# How far back to look on the very first sync for an asset+interval
DEFAULT_BACKFILL_DAYS = 7


async def run_ingestion(
    db: AsyncSession,
    provider: BaseProvider,
    interval: str,
    asset_symbols: list[str] | None = None,
    asset_class: str | None = None,
    backfill_days: int = DEFAULT_BACKFILL_DAYS,
) -> IngestionJob:
    """Run a full ingestion cycle for all (or selected) active assets.

    Steps:
      1. Create IngestionJob audit record
      2. Load active assets
      3. For each asset:
         a. Determine start time from sync state (or backfill window)
         b. Fetch bars from provider
         c. Bulk-insert into price_bars (ON CONFLICT DO NOTHING)
         d. Update provider_sync_state
      4. Finalize IngestionJob with results

    Returns the completed IngestionJob.
    """
    t_start = _time.monotonic()
    now = datetime.now(timezone.utc)

    # 1. Create job record
    job = IngestionJob(
        id=uuid.uuid4(),
        provider=provider.name,
        job_type="ohlcv",
        status="running",
        started_at=now,
    )
    db.add(job)
    await db.flush()

    log.info(
        "ingestion.start",
        job_id=str(job.id),
        provider=provider.name,
        interval=interval,
        assets_requested=len(asset_symbols) if asset_symbols else "all",
    )

    # 2. Load assets
    assets = await _load_assets(db, asset_symbols, asset_class)
    job.assets_total = len(assets)

    if not assets:
        job.status = "completed"
        job.completed_at = datetime.now(timezone.utc)
        job.duration_ms = int((_time.monotonic() - t_start) * 1000)
        await db.commit()
        log.warning("ingestion.no_assets", job_id=str(job.id))
        return job

    # 3. Process each asset
    total_inserted = 0
    errors: list[str] = []
    ingested_assets: list[tuple] = []  # (asset_id, symbol) for post-ingestion hooks

    for asset in assets:
        try:
            inserted = await _ingest_asset(
                db=db,
                provider=provider,
                asset=asset,
                interval=interval,
                backfill_days=backfill_days,
                now=now,
            )
            total_inserted += inserted
            job.assets_success += 1
            ingested_assets.append((asset.id, asset.symbol))
            log.debug(
                "ingestion.asset_done",
                symbol=asset.symbol,
                interval=interval,
                inserted=inserted,
            )
        except Exception as e:
            job.assets_failed += 1
            error_msg = f"{asset.symbol}: {type(e).__name__}: {e}"
            errors.append(error_msg)
            log.warning(
                "ingestion.asset_error",
                symbol=asset.symbol,
                interval=interval,
                error=str(e),
            )
            # Update sync state to reflect error
            await _mark_sync_error(db, provider.name, asset.id, interval, str(e))

    # 3b. Post-ingestion: run anomaly detection on successfully ingested assets
    anomaly_count = 0
    if ingested_assets:
        try:
            from app.anomalies.service import run_anomaly_detection_batch

            anomaly_count = await run_anomaly_detection_batch(db, ingested_assets, interval)
            log.info("ingestion.anomaly_scan_done", new_anomalies=anomaly_count)
        except Exception as e:
            log.error("ingestion.anomaly_scan_error", error=str(e))

    # 3c. Post-ingestion: evaluate alert rules
    alert_count = 0
    if ingested_assets:
        try:
            from app.alerts.service import evaluate_alerts_after_ingestion

            asset_ids = [aid for aid, _ in ingested_assets]
            # Collect new anomaly events for anomaly-based rules
            from app.anomalies.models import AnomalyEvent as AE
            new_anomalies_result = await db.execute(
                select(AE).where(
                    AE.asset_id.in_(asset_ids),
                    AE.is_resolved.is_(False),
                ).order_by(AE.detected_at.desc()).limit(50)
            )
            new_anomalies = list(new_anomalies_result.scalars().all())

            alert_count = await evaluate_alerts_after_ingestion(
                db, asset_ids, new_anomalies
            )
            if alert_count:
                log.info("ingestion.alerts_triggered", count=alert_count)
        except Exception as e:
            log.error("ingestion.alerts_error", error=str(e))

    # 4. Finalize job
    job.records_inserted = total_inserted
    job.status = "completed" if not errors else ("completed" if job.assets_success > 0 else "failed")
    job.completed_at = datetime.now(timezone.utc)
    job.duration_ms = int((_time.monotonic() - t_start) * 1000)
    if errors:
        job.error_summary = "; ".join(errors[:10])  # cap at 10

    await db.commit()

    log.info(
        "ingestion.done",
        job_id=str(job.id),
        status=job.status,
        assets_ok=job.assets_success,
        assets_fail=job.assets_failed,
        rows_inserted=total_inserted,
        anomalies_created=anomaly_count,
        duration_ms=job.duration_ms,
    )
    return job


async def _load_assets(
    db: AsyncSession,
    symbols: list[str] | None,
    asset_class: str | None = None,
) -> list[Asset]:
    """Load active assets, optionally filtered by symbol list and/or asset_class."""
    stmt = select(Asset).where(Asset.is_active.is_(True))
    if symbols:
        stmt = stmt.where(Asset.symbol.in_([s.upper() for s in symbols]))
    if asset_class:
        stmt = stmt.where(Asset.asset_class == asset_class)
    stmt = stmt.order_by(Asset.market_cap_rank.asc().nulls_last())
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def _ingest_asset(
    db: AsyncSession,
    provider: BaseProvider,
    asset: Asset,
    interval: str,
    backfill_days: int,
    now: datetime,
) -> int:
    """Fetch and persist bars for a single asset. Returns rows inserted."""
    # Determine start time
    sync_state = await _get_or_create_sync_state(db, provider.name, asset.id, interval)

    if sync_state.last_bar_time:
        # Incremental: start from last known bar (re-fetch last bar for safety)
        start_time = sync_state.last_bar_time
    else:
        # Initial backfill
        start_time = now - timedelta(days=backfill_days)

    # Fetch from provider
    bars = await provider.fetch_ohlcv(
        symbol=asset.provider_symbol,
        interval=interval,
        start_time=start_time,
        end_time=now,
        limit=1000,
    )

    if not bars:
        log.debug("no_bars_returned", symbol=asset.symbol, interval=interval)
        # Still mark as synced with current time
        sync_state.sync_status = "ok"
        sync_state.consecutive_errors = 0
        sync_state.updated_at = now
        await db.flush()
        return 0

    # Bulk insert with ON CONFLICT DO NOTHING
    inserted = await _bulk_insert_bars(db, asset.id, interval, bars)

    # Update sync state
    latest_bar_time = max(b.time for b in bars)
    sync_state.last_bar_time = latest_bar_time
    sync_state.sync_status = "ok"
    sync_state.consecutive_errors = 0
    sync_state.last_error = None
    sync_state.updated_at = datetime.now(timezone.utc)
    await db.flush()

    return inserted


async def _bulk_insert_bars(
    db: AsyncSession,
    asset_id: uuid.UUID,
    interval: str,
    bars: list[RawBar],
) -> int:
    """Insert bars using raw SQL for performance. Returns count of new rows."""
    if not bars:
        return 0

    # Build values for bulk insert
    values = [
        {
            "time": bar.time,
            "asset_id": asset_id,
            "interval": interval,
            "open": bar.open,
            "high": bar.high,
            "low": bar.low,
            "close": bar.close,
            "volume": bar.volume,
        }
        for bar in bars
    ]

    # ON CONFLICT DO NOTHING handles deduplication on (time, asset_id, interval) PK
    stmt = text("""
        INSERT INTO price_bars (time, asset_id, interval, open, high, low, close, volume)
        VALUES (:time, :asset_id, :interval, :open, :high, :low, :close, :volume)
        ON CONFLICT (time, asset_id, interval) DO NOTHING
    """)

    result = await db.execute(stmt, values)
    return result.rowcount


async def _get_or_create_sync_state(
    db: AsyncSession,
    provider_name: str,
    asset_id: uuid.UUID,
    interval: str,
) -> ProviderSyncState:
    """Get existing sync state or create a new one."""
    stmt = select(ProviderSyncState).where(
        ProviderSyncState.provider == provider_name,
        ProviderSyncState.asset_id == asset_id,
        ProviderSyncState.interval == interval,
    )
    result = await db.execute(stmt)
    state = result.scalar_one_or_none()

    if state is None:
        state = ProviderSyncState(
            provider=provider_name,
            asset_id=asset_id,
            interval=interval,
            sync_status="pending",
        )
        db.add(state)
        await db.flush()

    return state


async def _mark_sync_error(
    db: AsyncSession,
    provider_name: str,
    asset_id: uuid.UUID,
    interval: str,
    error: str,
) -> None:
    """Mark a sync state as errored."""
    state = await _get_or_create_sync_state(db, provider_name, asset_id, interval)
    state.sync_status = "error"
    state.consecutive_errors += 1
    state.last_error = error[:500]  # cap length
    state.updated_at = datetime.now(timezone.utc)
    await db.flush()
