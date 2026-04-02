"""Marketplace endpoints — publish, unpublish, list public strategies."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.strategies.models import Strategy
from app.strategies.router import store

router = APIRouter(prefix="/api/v1", tags=["marketplace"])


@router.post("/strategies/{strategy_id}/publish")
def publish_strategy(strategy_id: str) -> Strategy:
    """Set a strategy's is_public flag to True."""
    strategy = store.get(strategy_id)
    if strategy is None:
        raise HTTPException(status_code=404, detail="Strategy not found")
    strategy.is_public = True
    return strategy


@router.post("/strategies/{strategy_id}/unpublish")
def unpublish_strategy(strategy_id: str) -> Strategy:
    """Set a strategy's is_public flag to False."""
    strategy = store.get(strategy_id)
    if strategy is None:
        raise HTTPException(status_code=404, detail="Strategy not found")
    strategy.is_public = False
    return strategy


@router.get("/marketplace")
def list_marketplace() -> list[Strategy]:
    """Return all public strategies, sorted by created_at descending."""
    public = [s for s in store.list_all() if s.is_public]
    public.sort(key=lambda s: s.created_at, reverse=True)
    return public
