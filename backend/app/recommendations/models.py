"""Recommendation model — scored asset signals."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Numeric, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.models import UUIDPrimaryKeyMixin
from app.database import Base


class Recommendation(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "recommendations"

    asset_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("assets.id"), nullable=False
    )
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )
    recommendation_type: Mapped[str] = mapped_column(String(30), nullable=False)
    score: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    confidence: Mapped[str] = mapped_column(String(10), nullable=False)
    risk_level: Mapped[str] = mapped_column(String(10), nullable=False)
    rationale_summary: Mapped[str] = mapped_column(Text, nullable=False)
    signal_breakdown: Mapped[dict] = mapped_column(JSONB, nullable=False)
    entry_price_snapshot: Mapped[float | None] = mapped_column(Numeric(24, 8), nullable=True)
    time_horizon: Mapped[str] = mapped_column(String(20), nullable=False, default="24h-72h")
    valid_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    invalidation_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    scoring_version: Mapped[str | None] = mapped_column(String(10), nullable=True)
    # Forward-return evaluation
    price_after_24h: Mapped[float | None] = mapped_column(Numeric(24, 8), nullable=True)
    price_after_72h: Mapped[float | None] = mapped_column(Numeric(24, 8), nullable=True)
    return_24h_pct: Mapped[float | None] = mapped_column(Numeric(8, 4), nullable=True)
    return_72h_pct: Mapped[float | None] = mapped_column(Numeric(8, 4), nullable=True)
    evaluated_at_24h: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    evaluated_at_72h: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )

    def __repr__(self) -> str:
        return f"<Recommendation {self.recommendation_type} score={self.score} asset={self.asset_id}>"
