"""PriceBar model — OHLCV time-series data."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Index, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class PriceBar(Base):
    __tablename__ = "price_bars"

    # Composite primary key: (time, asset_id, interval)
    time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), primary_key=True, nullable=False
    )
    asset_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, nullable=False
    )
    interval: Mapped[str] = mapped_column(String(5), primary_key=True, nullable=False)

    open: Mapped[float] = mapped_column(Numeric(24, 8), nullable=False)
    high: Mapped[float] = mapped_column(Numeric(24, 8), nullable=False)
    low: Mapped[float] = mapped_column(Numeric(24, 8), nullable=False)
    close: Mapped[float] = mapped_column(Numeric(24, 8), nullable=False)
    volume: Mapped[float] = mapped_column(Numeric(24, 8), nullable=False)

    __table_args__ = (
        # Composite index for "last N bars for an asset" queries.
        Index("idx_price_bars_asset_interval_time", "asset_id", "interval", time.desc()),
    )

    def __repr__(self) -> str:
        return f"<PriceBar {self.asset_id} {self.interval} {self.time}>"
