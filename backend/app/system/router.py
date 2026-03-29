"""System endpoints — health check and status."""

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.schemas import HealthResponse
from app.database import get_db
from app.logging_config import get_logger

log = get_logger(__name__)

router = APIRouter(prefix="/api/v1", tags=["system"])


@router.get("/health", response_model=HealthResponse)
async def health_check(db: AsyncSession = Depends(get_db)) -> HealthResponse:
    """Check system health: database connection and app version."""
    db_status = "disconnected"
    try:
        result = await db.execute(text("SELECT 1"))
        if result.scalar() == 1:
            db_status = "connected"
    except Exception as e:
        log.error("health_check_db_error", error=str(e))
        db_status = f"error: {e}"

    return HealthResponse(
        status="ok" if db_status == "connected" else "degraded",
        database=db_status,
        version="0.1.0",
    )


@router.get("/dashboard/overview")
async def dashboard_overview(db: AsyncSession = Depends(get_db)):
    """Aggregate dashboard data: portfolio, signals, alerts, watchlists."""
    from app.system.dashboard import get_dashboard_overview
    return await get_dashboard_overview(db)


@router.get("/runtime-summary")
async def runtime_summary(db: AsyncSession = Depends(get_db)):
    """Operational summary: is the system alive and doing its job?"""
    from sqlalchemy import func, select
    from app.config import settings
    from app.ingestion.models import IngestionJob
    from app.recommendations.models import Recommendation
    from app.alerts.models import AlertEvent
    from app.anomalies.models import AnomalyEvent
    from app.portfolio.models import PortfolioPosition
    from app.live.cache import get_stats as live_stats, subscriber_count

    # Last ingestion per provider
    last_crypto = (await db.execute(
        select(func.max(IngestionJob.started_at)).where(IngestionJob.provider == "binance")
    )).scalar_one()
    last_stock = (await db.execute(
        select(func.max(IngestionJob.started_at)).where(IngestionJob.provider == "yahoo_finance")
    )).scalar_one()
    total_jobs = (await db.execute(select(func.count(IngestionJob.id)))).scalar_one()

    # Last recommendation batch
    last_rec = (await db.execute(select(func.max(Recommendation.generated_at)))).scalar_one()
    active_recs = (await db.execute(
        select(func.count()).where(Recommendation.status == "active")
    )).scalar_one()
    buy_signals = (await db.execute(
        select(func.count()).where(
            Recommendation.status == "active",
            Recommendation.recommendation_type == "candidate_buy",
        )
    )).scalar_one()

    # Evaluation
    eval_24h = (await db.execute(
        select(func.count()).where(Recommendation.evaluated_at_24h.isnot(None))
    )).scalar_one()
    last_eval = (await db.execute(
        select(func.max(Recommendation.evaluated_at_24h))
    )).scalar_one()

    # Portfolio
    open_pos = (await db.execute(
        select(func.count()).where(PortfolioPosition.status == "open")
    )).scalar_one()
    closed_pos = (await db.execute(
        select(func.count()).where(PortfolioPosition.status == "closed")
    )).scalar_one()

    # Alerts / anomalies
    unread = (await db.execute(
        select(func.count()).where(AlertEvent.is_read.is_(False))
    )).scalar_one()
    unresolved = (await db.execute(
        select(func.count()).where(AnomalyEvent.is_resolved.is_(False))
    )).scalar_one()

    # Live
    ls = live_stats()

    return {
        "scheduler": {
            "enabled": settings.SCHEDULER_ENABLED,
            "total_jobs": total_jobs,
            "last_crypto_ingestion": last_crypto.isoformat() if last_crypto else None,
            "last_stock_ingestion": last_stock.isoformat() if last_stock else None,
        },
        "recommendations": {
            "active": active_recs,
            "buy_signals": buy_signals,
            "last_generated": last_rec.isoformat() if last_rec else None,
        },
        "evaluation": {
            "evaluated_24h": eval_24h,
            "last_evaluated_at": last_eval.isoformat() if last_eval else None,
        },
        "portfolio": {
            "open": open_pos,
            "closed": closed_pos,
        },
        "alerts": {"unread": unread, "unresolved_anomalies": unresolved},
        "live": {
            "ws_connected": ls.get("ws_connected", False),
            "sse_subscribers": subscriber_count(),
            "batches_sent": ls.get("batches_sent", 0),
        },
    }
