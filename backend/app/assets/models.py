"""Asset model — tracked financial instruments (crypto, stocks)."""

import uuid

from sqlalchemy import Boolean, Index, Integer, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.models import TimestampMixin, UUIDPrimaryKeyMixin
from app.database import Base


class Asset(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "assets"

    symbol: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    provider_symbol: Mapped[str] = mapped_column(String(20), nullable=False)
    coingecko_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    market_cap_rank: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    asset_class: Mapped[str] = mapped_column(String(10), nullable=False, default="crypto")
    exchange: Mapped[str | None] = mapped_column(String(20), nullable=True)
    currency: Mapped[str] = mapped_column(String(5), nullable=False, default="USD")
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, nullable=False, default=dict)

    # Relationships (lazy-loaded, defined for ORM convenience)
    anomaly_events = relationship("AnomalyEvent", back_populates="asset", lazy="selectin")

    __table_args__ = (
        Index("idx_assets_active_rank", "is_active", "market_cap_rank"),
        Index("idx_assets_class", "asset_class", "is_active"),
    )

    def __repr__(self) -> str:
        return f"<Asset {self.symbol} ({self.asset_class})>"
