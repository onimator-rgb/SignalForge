"""Marketplace endpoints — publish, unpublish, list public, copy strategies."""

from __future__ import annotations

import copy
from uuid import uuid4

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


@router.post("/marketplace/{strategy_id}/copy")
def copy_strategy(strategy_id: str) -> Strategy:
    """Create a private copy of a public strategy."""
    original = store.get(strategy_id)
    if original is None:
        raise HTTPException(status_code=404, detail="Strategy not found")
    if not original.is_public:
        raise HTTPException(status_code=400, detail="Strategy is not public")

    copied = Strategy(
        id=uuid4().hex,
        name=f"Copy of {original.name}",
        description=original.description,
        rules=copy.deepcopy(original.rules),
        profile_name=original.profile_name,
        is_public=False,
        is_preset=False,
        copy_count=0,
    )
    original.copy_count += 1
    store.add(copied)
    return copied
