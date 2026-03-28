"""AnalysisReport model — AI-generated reports."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.models import TimestampMixin, UUIDPrimaryKeyMixin
from app.database import Base


class AnalysisReport(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "analysis_reports"

    report_type: Mapped[str] = mapped_column(String(30), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    asset_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("assets.id"), nullable=True
    )
    anomaly_event_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("anomaly_events.id"), nullable=True
    )
    title: Mapped[str | None] = mapped_column(String(300), nullable=True)
    content_md: Mapped[str | None] = mapped_column(Text, nullable=True)
    llm_provider: Mapped[str | None] = mapped_column(String(30), nullable=True)
    llm_model: Mapped[str | None] = mapped_column(String(50), nullable=True)
    prompt_version: Mapped[str | None] = mapped_column(String(20), nullable=True)
    token_usage: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    context_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        Index("idx_report_type_created", "report_type", "created_at"),
        Index("idx_report_status", "status"),
    )

    def __repr__(self) -> str:
        return f"<AnalysisReport {self.report_type} {self.status}>"
