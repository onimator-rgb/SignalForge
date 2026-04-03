"""Market Analyst agent — analyzes assets using indicators, anomalies, prices."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai_assistant.agents.base import BaseAssistantAgent, ParsedIntent
from app.ai_assistant.prompts import MARKET_ANALYST_SYSTEM
from app.llm.router import TaskComplexity
from app.logging_config import get_logger

log = get_logger(__name__)


class MarketAnalystAgent(BaseAssistantAgent):
    name = "market_analyst"
    description = "Analyzes assets using technical indicators, anomalies, and recommendations"
    complexity = TaskComplexity.MODERATE

    def get_system_prompt(self, user_profile: dict | None = None) -> str:
        return MARKET_ANALYST_SYSTEM

    async def build_context(self, db: AsyncSession, intent: ParsedIntent) -> dict:
        """Build market context for requested assets."""
        from app.ai_traders.context import build_asset_context
        from app.assets.models import Asset

        if not intent.asset_symbols:
            return await self._build_market_overview(db)

        context: dict = {"assets": {}}

        for symbol in intent.asset_symbols[:3]:  # Cap at 3 assets
            # Resolve symbol to asset_id
            result = await db.execute(
                select(Asset).where(Asset.symbol == symbol)
            )
            asset = result.scalar_one_or_none()
            if not asset:
                context["assets"][symbol] = {"error": f"Asset {symbol} not found in database"}
                continue

            asset_ctx = await build_asset_context(db, asset.id)
            context["assets"][symbol] = asset_ctx

        return context

    async def _build_market_overview(self, db: AsyncSession) -> dict:
        """Build general market overview when no specific asset requested."""
        from app.assets.models import Asset
        from app.recommendations.models import Recommendation
        from app.anomalies.models import AnomalyEvent
        from datetime import datetime, timedelta, timezone

        now = datetime.now(timezone.utc)
        overview: dict = {}

        # Top recommendations
        recs = await db.execute(
            select(Recommendation, Asset.symbol)
            .join(Asset, Recommendation.asset_id == Asset.id)
            .where(Recommendation.generated_at >= now - timedelta(hours=24))
            .order_by(Recommendation.score.desc())
            .limit(5)
        )
        top_recs = []
        for row in recs.all():
            rec, symbol = row.Recommendation, row.symbol
            top_recs.append({
                "symbol": symbol,
                "score": float(rec.score) if rec.score else None,
                "type": rec.recommendation_type,
                "confidence": rec.confidence,
            })
        overview["top_recommendations"] = top_recs

        # Recent anomalies
        anoms = await db.execute(
            select(AnomalyEvent, Asset.symbol)
            .join(Asset, AnomalyEvent.asset_id == Asset.id)
            .where(AnomalyEvent.detected_at >= now - timedelta(hours=24))
            .order_by(AnomalyEvent.detected_at.desc())
            .limit(5)
        )
        recent_anomalies = []
        for row in anoms.all():
            anom, symbol = row.AnomalyEvent, row.symbol
            recent_anomalies.append({
                "symbol": symbol,
                "type": anom.anomaly_type,
                "severity": anom.severity,
                "score": float(anom.score),
            })
        overview["recent_anomalies"] = recent_anomalies

        return overview
