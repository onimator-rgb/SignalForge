"""LLM cost tracking — records usage per provider/model/agent.

Stores usage in PostgreSQL (llm_usage_log table) and provides
aggregation queries for cost monitoring and budget enforcement.
"""

from __future__ import annotations

import datetime
from decimal import Decimal

from sqlalchemy import Column, DateTime, Integer, Numeric, String, Text, Boolean, func, select
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from app.database import Base, async_session
from app.logging_config import get_logger

log = get_logger(__name__)

# ---------------------------------------------------------------------------
# Pricing lookup (per 1M tokens)
# ---------------------------------------------------------------------------

_PRICING: dict[str, tuple[float, float]] = {
    # Gemini (2.5 series)
    "gemini-2.5-flash": (0.075, 0.30),
    "gemini-2.5-flash-lite": (0.02, 0.075),
    "gemini-2.0-flash": (0.075, 0.30),
    "gemini-2.0-flash-lite": (0.02, 0.075),
    "gemini-1.5-pro": (1.25, 5.00),
    # Groq
    "llama-3.3-70b-versatile": (0.59, 0.79),
    "llama-3.1-8b-instant": (0.05, 0.08),
    "mixtral-8x7b-32768": (0.24, 0.24),
    # Mistral
    "mistral-small-latest": (0.10, 0.30),
    "mistral-large-latest": (2.00, 6.00),
    "open-mistral-nemo": (0.15, 0.15),
    # Claude
    "claude-haiku-4-5-20251001": (0.80, 4.00),
    "claude-sonnet-4-20250514": (3.00, 15.00),
    # Cerebras (free 1M tokens/day)
    "llama-3.3-70b": (0.0, 0.0),
    "llama-3.1-8b": (0.0, 0.0),
    "llama-3.1-70b": (0.0, 0.0),
    # SambaNova (free tier)
    "Meta-Llama-3.3-70B-Instruct": (0.0, 0.0),
    "Meta-Llama-3.1-8B-Instruct": (0.0, 0.0),
    "DeepSeek-R1": (0.0, 0.0),
    # OpenRouter free
    "google/gemini-2.5-flash-preview:free": (0.0, 0.0),
    "meta-llama/llama-3.3-70b-instruct:free": (0.0, 0.0),
    "mistralai/mistral-small-3.1-24b-instruct:free": (0.0, 0.0),
    # Local
    "local-template-v1": (0.0, 0.0),
}


def calculate_cost(model: str, input_tokens: int, output_tokens: int) -> Decimal:
    """Calculate USD cost for a single request."""
    input_price, output_price = _PRICING.get(model, (0.10, 0.30))
    cost = (input_tokens * input_price + output_tokens * output_price) / 1_000_000
    return Decimal(str(round(cost, 6)))


# ---------------------------------------------------------------------------
# ORM Model
# ---------------------------------------------------------------------------

class LLMUsageLog(Base):
    __tablename__ = "llm_usage_log"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    provider = Column(String(50), nullable=False)
    model = Column(String(100), nullable=False)
    agent_name = Column(String(50), nullable=True)
    task_type = Column(String(50), nullable=True)
    input_tokens = Column(Integer, nullable=False, default=0)
    output_tokens = Column(Integer, nullable=False, default=0)
    cost_usd = Column(Numeric(10, 6), nullable=False, default=0)
    latency_ms = Column(Integer, nullable=True)
    success = Column(Boolean, nullable=False, default=True)
    error_message = Column(Text, nullable=True)


# ---------------------------------------------------------------------------
# Cost Tracker
# ---------------------------------------------------------------------------

class CostTracker:
    """Records LLM usage and provides cost aggregation."""

    async def record(
        self,
        *,
        provider: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
        agent_name: str = "",
        task_type: str = "",
        latency_ms: int = 0,
        success: bool = True,
        error_message: str = "",
    ) -> Decimal:
        """Record a single LLM call. Returns the computed cost."""
        cost = calculate_cost(model, input_tokens, output_tokens)

        try:
            async with async_session() as session:
                entry = LLMUsageLog(
                    provider=provider,
                    model=model,
                    agent_name=agent_name or None,
                    task_type=task_type or None,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    cost_usd=cost,
                    latency_ms=latency_ms,
                    success=success,
                    error_message=error_message or None,
                )
                session.add(entry)
                await session.commit()
        except Exception as exc:
            # Cost tracking should never break the main flow
            log.warning("cost_tracker.record_failed", error=str(exc))

        return cost

    async def get_daily_cost(self, date: datetime.date | None = None) -> Decimal:
        """Total cost for a given day (default: today)."""
        target = date or datetime.date.today()
        start = datetime.datetime.combine(target, datetime.time.min)
        end = start + datetime.timedelta(days=1)

        async with async_session() as session:
            result = await session.execute(
                select(func.coalesce(func.sum(LLMUsageLog.cost_usd), 0)).where(
                    LLMUsageLog.created_at >= start,
                    LLMUsageLog.created_at < end,
                    LLMUsageLog.success.is_(True),
                )
            )
            return Decimal(str(result.scalar_one()))

    async def get_monthly_cost(self, year: int | None = None, month: int | None = None) -> Decimal:
        """Total cost for a given month (default: current month)."""
        now = datetime.date.today()
        y = year or now.year
        m = month or now.month
        start = datetime.datetime(y, m, 1)
        if m == 12:
            end = datetime.datetime(y + 1, 1, 1)
        else:
            end = datetime.datetime(y, m + 1, 1)

        async with async_session() as session:
            result = await session.execute(
                select(func.coalesce(func.sum(LLMUsageLog.cost_usd), 0)).where(
                    LLMUsageLog.created_at >= start,
                    LLMUsageLog.created_at < end,
                    LLMUsageLog.success.is_(True),
                )
            )
            return Decimal(str(result.scalar_one()))

    async def get_cost_by_agent(
        self, days: int = 30
    ) -> list[dict]:
        """Cost breakdown per agent for last N days."""
        since = datetime.datetime.now() - datetime.timedelta(days=days)

        async with async_session() as session:
            result = await session.execute(
                select(
                    LLMUsageLog.agent_name,
                    func.count().label("request_count"),
                    func.sum(LLMUsageLog.cost_usd).label("total_cost"),
                    func.sum(LLMUsageLog.input_tokens).label("total_input"),
                    func.sum(LLMUsageLog.output_tokens).label("total_output"),
                    func.avg(LLMUsageLog.latency_ms).label("avg_latency"),
                )
                .where(
                    LLMUsageLog.created_at >= since,
                    LLMUsageLog.success.is_(True),
                )
                .group_by(LLMUsageLog.agent_name)
                .order_by(func.sum(LLMUsageLog.cost_usd).desc())
            )
            rows = result.all()

        return [
            {
                "agent_name": row.agent_name or "unknown",
                "request_count": row.request_count,
                "total_cost_usd": float(row.total_cost or 0),
                "total_input_tokens": row.total_input or 0,
                "total_output_tokens": row.total_output or 0,
                "avg_latency_ms": round(float(row.avg_latency or 0)),
            }
            for row in rows
        ]

    async def get_cost_by_provider(
        self, days: int = 30
    ) -> list[dict]:
        """Cost breakdown per provider for last N days."""
        since = datetime.datetime.now() - datetime.timedelta(days=days)

        async with async_session() as session:
            result = await session.execute(
                select(
                    LLMUsageLog.provider,
                    LLMUsageLog.model,
                    func.count().label("request_count"),
                    func.sum(LLMUsageLog.cost_usd).label("total_cost"),
                    func.sum(LLMUsageLog.input_tokens).label("total_input"),
                    func.sum(LLMUsageLog.output_tokens).label("total_output"),
                )
                .where(
                    LLMUsageLog.created_at >= since,
                    LLMUsageLog.success.is_(True),
                )
                .group_by(LLMUsageLog.provider, LLMUsageLog.model)
                .order_by(func.sum(LLMUsageLog.cost_usd).desc())
            )
            rows = result.all()

        return [
            {
                "provider": row.provider,
                "model": row.model,
                "request_count": row.request_count,
                "total_cost_usd": float(row.total_cost or 0),
                "total_input_tokens": row.total_input or 0,
                "total_output_tokens": row.total_output or 0,
            }
            for row in rows
        ]

    async def is_budget_exceeded(self) -> bool:
        """Check if monthly budget is exceeded."""
        monthly = await self.get_monthly_cost()
        return float(monthly) >= settings.LLM_MONTHLY_BUDGET_USD

    async def get_budget_status(self) -> dict:
        """Return current budget utilization."""
        monthly_cost = await self.get_monthly_cost()
        daily_cost = await self.get_daily_cost()
        budget = settings.LLM_MONTHLY_BUDGET_USD
        return {
            "monthly_cost_usd": float(monthly_cost),
            "daily_cost_usd": float(daily_cost),
            "monthly_budget_usd": budget,
            "utilization_pct": round(float(monthly_cost) / budget * 100, 1) if budget > 0 else 0,
            "budget_exceeded": float(monthly_cost) >= budget,
        }
