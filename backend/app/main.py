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


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application startup and shutdown events."""
    setup_logging(settings.LOG_LEVEL)

    from app.logging_config import get_logger

    log = get_logger("app.main")
    log.info("app.starting", env=settings.APP_ENV, version="0.1.0")

    from app.scheduler import start_scheduler, stop_scheduler

    start_scheduler()

    yield

    stop_scheduler()
    log.info("app.shutdown_complete")


def create_app() -> FastAPI:
    app = FastAPI(
        title="MarketPulse AI",
        description="Crypto market anomaly detection platform",
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

    return app


app = create_app()
