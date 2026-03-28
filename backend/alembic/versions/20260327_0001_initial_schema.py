"""Initial schema — assets, price_bars, anomaly_events,
ingestion_jobs, provider_sync_states.

Revision ID: 0001
Revises:
Create Date: 2026-03-27
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- assets ---
    op.create_table(
        "assets",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("symbol", sa.String(20), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("binance_symbol", sa.String(20), nullable=False),
        sa.Column("coingecko_id", sa.String(100), nullable=True),
        sa.Column("market_cap_rank", sa.Integer(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column(
            "metadata",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("symbol"),
    )
    op.create_index("idx_assets_active_rank", "assets", ["is_active", "market_cap_rank"])

    # --- price_bars (OHLCV time-series) ---
    op.create_table(
        "price_bars",
        sa.Column("time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("asset_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("interval", sa.String(5), nullable=False),
        sa.Column("open", sa.Numeric(24, 8), nullable=False),
        sa.Column("high", sa.Numeric(24, 8), nullable=False),
        sa.Column("low", sa.Numeric(24, 8), nullable=False),
        sa.Column("close", sa.Numeric(24, 8), nullable=False),
        sa.Column("volume", sa.Numeric(24, 8), nullable=False),
        sa.PrimaryKeyConstraint("time", "asset_id", "interval"),
    )
    # Note: No FK from price_bars.asset_id to assets.id — skipped for bulk insert
    # performance. Referential integrity enforced at application layer.

    # Composite index for "last N bars for asset+interval" queries
    op.create_index(
        "idx_price_bars_asset_interval_time",
        "price_bars",
        ["asset_id", "interval", sa.text("time DESC")],
    )

    # --- anomaly_events ---
    op.create_table(
        "anomaly_events",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "asset_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("assets.id"),
            nullable=False,
        ),
        sa.Column("detected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("anomaly_type", sa.String(30), nullable=False),
        sa.Column("severity", sa.String(10), nullable=False),
        sa.Column("score", sa.Numeric(5, 4), nullable=False),
        sa.Column(
            "details",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("timeframe", sa.String(5), nullable=False),
        sa.Column(
            "is_resolved", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_anomaly_asset_time", "anomaly_events", ["asset_id", sa.text("detected_at DESC")]
    )
    op.create_index(
        "idx_anomaly_severity_time",
        "anomaly_events",
        ["severity", sa.text("detected_at DESC")],
    )
    op.execute(
        "CREATE INDEX idx_anomaly_unresolved ON anomaly_events (is_resolved) "
        "WHERE is_resolved = false;"
    )

    # --- ingestion_jobs ---
    op.create_table(
        "ingestion_jobs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("provider", sa.String(30), nullable=False),
        sa.Column("job_type", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default=sa.text("'running'")),
        sa.Column("assets_total", sa.Integer(), server_default=sa.text("0")),
        sa.Column("assets_success", sa.Integer(), server_default=sa.text("0")),
        sa.Column("assets_failed", sa.Integer(), server_default=sa.text("0")),
        sa.Column("records_inserted", sa.Integer(), server_default=sa.text("0")),
        sa.Column("error_summary", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_ingestion_status_time",
        "ingestion_jobs",
        ["status", sa.text("started_at DESC")],
    )

    # --- provider_sync_states ---
    op.create_table(
        "provider_sync_states",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("provider", sa.String(30), nullable=False),
        sa.Column(
            "asset_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("assets.id"),
            nullable=False,
        ),
        sa.Column("interval", sa.String(5), nullable=False),
        sa.Column("last_bar_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "sync_status",
            sa.String(10),
            nullable=False,
            server_default=sa.text("'pending'"),
        ),
        sa.Column(
            "consecutive_errors", sa.Integer(), nullable=False, server_default=sa.text("0")
        ),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "provider", "asset_id", "interval", name="uq_provider_asset_interval"
        ),
    )


def downgrade() -> None:
    op.drop_table("provider_sync_states")
    op.drop_table("ingestion_jobs")
    op.drop_table("anomaly_events")
    op.drop_table("price_bars")
    op.drop_table("assets")
