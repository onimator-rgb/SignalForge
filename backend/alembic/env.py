"""Alembic environment configuration — async support for SQLAlchemy."""

import asyncio
import sys
from pathlib import Path
from logging.config import fileConfig

# Ensure backend root is on sys.path so 'app' package is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from alembic import context
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config

from app.config import settings
from app.database import Base

# Import all models so Alembic detects them for autogenerate
from app.assets.models import Asset  # noqa: F401
from app.market_data.models import PriceBar  # noqa: F401
from app.anomalies.models import AnomalyEvent  # noqa: F401
from app.ingestion.models import IngestionJob, ProviderSyncState  # noqa: F401
from app.reports.models import AnalysisReport  # noqa: F401
from app.alerts.models import AlertRule, AlertEvent  # noqa: F401
from app.llm.cost_tracker import LLMUsageLog  # noqa: F401
from app.ai_traders.models import AITrader, AITraderDecision, AITraderSnapshot  # noqa: F401

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

# Override sqlalchemy.url from app settings
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Run migrations in 'online' mode with async engine."""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
