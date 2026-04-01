"""Strategy CRUD endpoints — create, list, get, delete."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.strategies.models import (
    Strategy,
    StrategyAction,
    StrategyCondition,
    StrategyRule,
    StrategyStore,
)

router = APIRouter(prefix="/api/v1/strategies", tags=["strategies"])

store = StrategyStore()


# ---------------------------------------------------------------------------
# Request schema
# ---------------------------------------------------------------------------


class RuleInput(BaseModel):
    condition: StrategyCondition
    action: StrategyAction
    description: str = ""


class CreateStrategyRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str = ""
    rules: list[RuleInput] = Field(min_length=1)
    profile_name: str = "balanced"


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/")
def create_strategy(body: CreateStrategyRequest) -> Strategy:
    rules = [
        StrategyRule(
            condition=r.condition,
            action=r.action,
            description=r.description,
        )
        for r in body.rules
    ]
    strategy = Strategy(
        name=body.name,
        description=body.description,
        rules=rules,
        profile_name=body.profile_name,
    )
    return store.add(strategy)


@router.get("/")
def list_strategies() -> list[Strategy]:
    return store.list_all()


@router.get("/{strategy_id}")
def get_strategy(strategy_id: str) -> Strategy:
    result = store.get(strategy_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Strategy not found")
    return result


@router.delete("/{strategy_id}")
def delete_strategy(strategy_id: str) -> dict[str, bool]:
    if not store.delete(strategy_id):
        raise HTTPException(status_code=404, detail="Strategy not found")
    return {"deleted": True}
