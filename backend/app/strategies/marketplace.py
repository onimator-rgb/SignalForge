"""Marketplace endpoints — publish, unpublish, list public strategies, ranking."""

from __future__ import annotations

import hashlib
import struct
from typing import Literal

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.strategies.models import Strategy
from app.strategies.router import store

router = APIRouter(prefix="/api/v1", tags=["marketplace"])


# ---------------------------------------------------------------------------
# Ranked strategy schema
# ---------------------------------------------------------------------------


class RankedStrategy(BaseModel):
    """Public strategy with deterministic mock performance metrics."""

    strategy_id: str
    name: str
    profile_name: str
    total_return_pct: float
    max_drawdown_pct: float
    sharpe_ratio: float
    win_rate_pct: float
    copy_count: int
    rule_count: int


# ---------------------------------------------------------------------------
# Deterministic mock metric generator
# ---------------------------------------------------------------------------


def _hash_to_floats(strategy_id: str, count: int) -> list[float]:
    """Derive *count* deterministic floats in [0, 1) from a strategy id."""
    digest = hashlib.sha256(strategy_id.encode()).digest()
    # Unpack first *count* 4-byte unsigned ints from the 32-byte digest
    values: list[float] = []
    for i in range(count):
        raw = struct.unpack_from(">I", digest, i * 4)[0]
        values.append(raw / 0xFFFFFFFF)
    return values


def compute_mock_metrics(strategy: Strategy) -> RankedStrategy:
    """Derive deterministic fake metrics from the strategy id hash.

    Ranges:
        total_return_pct : [-20, 80]
        max_drawdown_pct : [-40, -2]
        sharpe_ratio     : [-0.5, 3.0]
        win_rate_pct     : [25, 75]
        copy_count       : [0, 500]
    """
    f = _hash_to_floats(strategy.id, 5)

    return RankedStrategy(
        strategy_id=strategy.id,
        name=strategy.name,
        profile_name=strategy.profile_name,
        total_return_pct=round(-20 + f[0] * 100, 2),       # [-20, 80]
        max_drawdown_pct=round(-40 + f[1] * 38, 2),        # [-40, -2]
        sharpe_ratio=round(-0.5 + f[2] * 3.5, 4),          # [-0.5, 3.0]
        win_rate_pct=round(25 + f[3] * 50, 2),             # [25, 75]
        copy_count=int(f[4] * 501),                         # [0, 500]
        rule_count=len(strategy.rules),
    )


# ---------------------------------------------------------------------------
# Publish / unpublish endpoints
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Ranking endpoint
# ---------------------------------------------------------------------------

SortField = Literal["sharpe_ratio", "total_return_pct", "copy_count"]


@router.get("/marketplace/ranking")
def marketplace_ranking(
    sort_by: SortField = Query(default="sharpe_ratio"),
    limit: int = Query(default=20, ge=1, le=100),
) -> list[RankedStrategy]:
    """Return public strategies ranked by performance metrics.

    Metrics are deterministic — same strategy id always produces the same
    numbers, generated from a SHA-256 hash of the id.
    """
    public = [s for s in store.list_all() if s.is_public]
    ranked = [compute_mock_metrics(s) for s in public]
    ranked.sort(key=lambda r: getattr(r, sort_by), reverse=True)
    return ranked[:limit]
