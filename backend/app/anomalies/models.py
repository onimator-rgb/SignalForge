"""AnomalyEvent model — detected market anomalies."""

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Numeric, String, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.models import TimestampMixin, UUIDPrimaryKeyMixin
from app.database import Base


class AnomalyEvent(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "anomaly_events"

    asset_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("assets.id"), nullable=False
    )
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    anomaly_type: Mapped[str] = mapped_column(String(30), nullable=False)
    severity: Mapped[str] = mapped_column(String(10), nullable=False)
    score: Mapped[float] = mapped_column(Numeric(5, 4), nullable=False)
    details: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    timeframe: Mapped[str] = mapped_column(String(5), nullable=False)
    is_resolved: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    asset = relationship("Asset", back_populates="anomaly_events", lazy="selectin")

    __table_args__ = (
        Index("idx_anomaly_asset_time", "asset_id", detected_at.desc()),
        Index("idx_anomaly_severity_time", "severity", detected_at.desc()),
        Index(
            "idx_anomaly_unresolved",
            "is_resolved",
            postgresql_where=text("is_resolved = false"),
        ),
    )

    def __repr__(self) -> str:
        return f"<AnomalyEvent {self.anomaly_type} {self.severity} {self.asset_id}>"
