"""Ingestion API endpoints — trigger, status, inspection."""

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.assets.models import Asset
from app.database import get_db
from app.ingestion.models import IngestionJob, ProviderSyncState
from app.ingestion.schemas import (
    IngestionJobOut,
    IngestionStatusResponse,
    SyncStateOut,
    TriggerIngestionRequest,
    TriggerIngestionResponse,
)
from app.ingestion.service import run_ingestion
from app.logging_config import get_logger

log = get_logger(__name__)

router = APIRouter(prefix="/api/v1/ingestion", tags=["ingestion"])


@router.post("/trigger", response_model=TriggerIngestionResponse)
async def trigger_ingestion(
    req: TriggerIngestionRequest,
    db: AsyncSession = Depends(get_db),
):
    """Manually trigger an ingestion cycle.

    Runs synchronously — waits for completion and returns the result.
    Examples:
      {"asset_class": "crypto", "interval": "1h"}
      {"asset_class": "stock", "interval": "1h"}
      {"asset_class": "crypto", "asset_symbols": ["BTC"], "interval": "1h"}
    """
    from app.scheduler import _get_provider

    provider = _get_provider(req.asset_class)
    job = await run_ingestion(
        db=db,
        provider=provider,
        interval=req.interval,
        asset_symbols=req.asset_symbols,
        asset_class=req.asset_class,
    )
    return TriggerIngestionResponse(
        job_id=job.id,
        status=job.status,
        message=(
            f"Ingested {job.assets_success}/{job.assets_total} assets, "
            f"{job.records_inserted} bars inserted"
        ),
    )


@router.get("/status", response_model=IngestionStatusResponse)
async def ingestion_status(
    limit: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
):
    """Get recent ingestion jobs and current sync states."""
    # Recent jobs
    jobs_result = await db.execute(
        select(IngestionJob)
        .order_by(IngestionJob.started_at.desc())
        .limit(limit)
    )
    jobs = jobs_result.scalars().all()

    # Sync states with asset symbol
    states_result = await db.execute(
        select(ProviderSyncState, Asset.symbol)
        .join(Asset, ProviderSyncState.asset_id == Asset.id)
        .order_by(Asset.market_cap_rank.asc().nulls_last())
    )
    sync_states = [
        SyncStateOut(
            id=state.id,
            provider=state.provider,
            asset_id=state.asset_id,
            asset_symbol=symbol,
            interval=state.interval,
            last_bar_time=state.last_bar_time,
            sync_status=state.sync_status,
            consecutive_errors=state.consecutive_errors,
            last_error=state.last_error,
            updated_at=state.updated_at,
        )
        for state, symbol in states_result.all()
    ]

    return IngestionStatusResponse(
        recent_jobs=[IngestionJobOut.model_validate(j) for j in jobs],
        sync_states=sync_states,
    )


@router.get("/jobs", response_model=list[IngestionJobOut])
async def list_ingestion_jobs(
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """List recent ingestion jobs."""
    result = await db.execute(
        select(IngestionJob)
        .order_by(IngestionJob.started_at.desc())
        .limit(limit)
    )
    return [IngestionJobOut.model_validate(j) for j in result.scalars().all()]
