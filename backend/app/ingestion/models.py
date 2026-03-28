"""Ingestion models — job tracking and provider sync state."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.models import UUIDPrimaryKeyMixin
from app.database import Base


class IngestionJob(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "ingestion_jobs"

    provider: Mapped[str] = mapped_column(String(30), nullable=False)
    job_type: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="running")
    assets_total: Mapped[int] = mapped_column(Integer, default=0)
    assets_success: Mapped[int] = mapped_column(Integer, default=0)
    assets_failed: Mapped[int] = mapped_column(Integer, default=0)
    records_inserted: Mapped[int] = mapped_column(Integer, default=0)
    error_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    def __repr__(self) -> str:
        return f"<IngestionJob {self.provider} {self.job_type} {self.status}>"


class ProviderSyncState(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "provider_sync_states"

    provider: Mapped[str] = mapped_column(String(30), nullable=False)
    asset_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("assets.id"), nullable=False
    )
    interval: Mapped[str] = mapped_column(String(5), nullable=False)
    last_bar_time: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    sync_status: Mapped[str] = mapped_column(String(10), nullable=False, default="pending")
    consecutive_errors: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default="now()",
        onupdate=datetime.now,
    )

    __table_args__ = (
        UniqueConstraint("provider", "asset_id", "interval", name="uq_provider_asset_interval"),
    )

    def __repr__(self) -> str:
        return f"<ProviderSyncState {self.provider} {self.asset_id} {self.interval}>"
