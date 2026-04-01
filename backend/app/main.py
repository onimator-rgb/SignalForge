"""MarketPulse AI — FastAPI application entry point."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.core.exceptions import register_exception_handlers
from app.core.middleware import RequestTraceMiddleware
from app.logging_config import setup_logging
from app.system.router import router as system_router
from app.system.diagnostics import router as diagnostics_router
from app.assets.router import router as assets_router
from app.ingestion.router import router as ingestion_router
from app.market_data.router import router as market_data_router
from app.indicators.router import router as indicators_router
from app.anomalies.router import router as anomalies_router
from app.reports.router import router as reports_router
from app.alerts.router import router as alerts_router
from app.watchlists.router import router as watchlists_router
from app.recommendations.router import router as recommendations_router
from app.portfolio.router import router as portfolio_router
from app.live.router import router as live_router
from app.strategy.router import router as strategy_router
from app.backtest.router import router as backtest_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application startup and shutdown events."""
    setup_logging(settings.LOG_LEVEL)

    from app.logging_config import get_logger

    log = get_logger("app.main")
    log.info("app.starting", env=settings.APP_ENV, version="0.1.0")

    from app.scheduler import start_scheduler, stop_scheduler

    await start_scheduler()

    # Start live price pollers
    try:
        from app.live.poller import start_pollers, stop_pollers
        from app.database import async_session
        from sqlalchemy import select
        from app.assets.models import Asset

        async with async_session() as db:
            result = await db.execute(
                select(Asset.symbol, Asset.provider_symbol, Asset.asset_class)
                .where(Asset.is_active.is_(True))
            )
            rows = result.all()
            crypto = [(r.symbol, r.provider_symbol) for r in rows if r.asset_class == "crypto"]
            stocks = [(r.symbol, r.provider_symbol) for r in rows if r.asset_class == "stock"]

        await start_pollers(crypto, stocks)
    except Exception as e:
        log.error("live_prices.init_error", error=str(e))

    # Start runtime jobs (independent evaluation + watchdog)
    runtime_tasks = []
    try:
        from app.system.runtime import start_runtime_jobs, heartbeat_quick
        runtime_tasks = await start_runtime_jobs()
        await heartbeat_quick("backend_app")
        # Run initial evaluation for any pending recs from previous run
        from app.system.runtime import run_pending_evaluation
        async with async_session() as db:
            await run_pending_evaluation(db)
    except Exception as e:
        log.error("runtime.init_error", error=str(e))

    yield

    try:
        stop_pollers()
    except Exception:
        pass
    try:
        from app.system.runtime import stop_runtime_jobs
        stop_runtime_jobs(runtime_tasks)
    except Exception:
        pass
    stop_scheduler()
    log.info("app.shutdown_complete")


def create_app() -> FastAPI:
    app = FastAPI(
        title="MarketPulse AI",
        description="Multi-asset market intelligence platform",
        version="0.1.0",
        lifespan=lifespan,
    )

    # Middleware (order matters: first added = outermost)
    app.add_middleware(RequestTraceMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://localhost:3000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID"],
    )

    register_exception_handlers(app)

    # Routers
    app.include_router(system_router)
    app.include_router(diagnostics_router)
    app.include_router(assets_router)
    app.include_router(ingestion_router)
    app.include_router(market_data_router)
    app.include_router(indicators_router)
    app.include_router(anomalies_router)
    app.include_router(reports_router)
    app.include_router(alerts_router)
    app.include_router(watchlists_router)
    app.include_router(recommendations_router)
    app.include_router(portfolio_router)
    app.include_router(live_router)
    app.include_router(strategy_router)
    app.include_router(backtest_router)

    return app


app = create_app()
