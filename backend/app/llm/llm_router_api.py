"""REST API for LLM provider management and cost monitoring."""

from __future__ import annotations

from fastapi import APIRouter

from .cost_tracker import CostTracker
from .router import get_router

router = APIRouter(prefix="/llm", tags=["llm"])


@router.get("/providers")
async def list_providers() -> list[dict]:
    """List all configured LLM providers and their models."""
    llm_router = get_router()
    return llm_router.get_available_providers()


@router.get("/costs")
async def get_costs() -> dict:
    """Get budget status and cost overview."""
    tracker = CostTracker()
    return await tracker.get_budget_status()


@router.get("/costs/by-agent")
async def get_costs_by_agent(days: int = 30) -> list[dict]:
    """Cost breakdown per AI agent."""
    tracker = CostTracker()
    return await tracker.get_cost_by_agent(days=days)


@router.get("/costs/by-provider")
async def get_costs_by_provider(days: int = 30) -> list[dict]:
    """Cost breakdown per LLM provider and model."""
    tracker = CostTracker()
    return await tracker.get_cost_by_provider(days=days)
