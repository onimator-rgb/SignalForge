"""Strategies API — CRUD endpoints and preset helpers."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Response
from pydantic import ValidationError

from app.strategies.models import Strategy, StrategyRule
from app.strategies.presets import generate_btd_rules, generate_dca_rules, generate_grid_rules
from app.strategies.schemas import (
    CreateStrategyRequest,
    GenerateFromPresetRequest,
    GenerateFromPresetResponse,
    PresetInfo,
    PresetParamSchema,
    StrategyListResponse,
    StrategyResponse,
)

router = APIRouter(prefix="/api/v1/strategies", tags=["strategies"])

# ---------------------------------------------------------------------------
# In-memory store for custom strategies
# ---------------------------------------------------------------------------
_strategies_store: dict[str, Strategy] = {}

PRESETS_REGISTRY: dict[str, dict[str, Any]] = {
    "grid": {
        "display_name": "Grid Bot",
        "description": "Places buy orders below and sell orders above a midpoint at evenly-spaced price levels.",
        "params": [
            PresetParamSchema(name="lower_price", type="float", description="Lower bound of the grid price range"),
            PresetParamSchema(name="upper_price", type="float", description="Upper bound of the grid price range"),
            PresetParamSchema(name="num_grids", type="int", description="Number of grid levels"),
            PresetParamSchema(name="amount_per_grid", type="float", description="USD amount per grid order"),
        ],
        "generator": generate_grid_rules,
    },
    "dca": {
        "display_name": "DCA Bot",
        "description": "Periodic dollar-cost averaging with optional bonus buys on price dips.",
        "params": [
            PresetParamSchema(name="interval_hours", type="int", description="Hours between periodic buys"),
            PresetParamSchema(name="amount_per_buy", type="float", description="USD amount per buy"),
            PresetParamSchema(name="max_buys", type="int", description="Maximum number of total purchases"),
            PresetParamSchema(name="price_drop_bonus_pct", type="float", description="Bonus buy trigger on this % dip", default=0.0),
        ],
        "generator": generate_dca_rules,
    },
    "btd": {
        "display_name": "Buy The Dip Bot",
        "description": "Buys on price dips with optional recovery confirmation and take-profit exit.",
        "params": [
            PresetParamSchema(name="dip_pct", type="float", description="Percentage drop to trigger a buy"),
            PresetParamSchema(name="recovery_pct", type="float", description="Percentage recovery to confirm buy (0 to disable)"),
            PresetParamSchema(name="take_profit_pct", type="float", description="Percentage gain to trigger a sell"),
        ],
        "generator": generate_btd_rules,
    },
}


@router.get("/presets", response_model=list[PresetInfo])
async def list_presets() -> list[PresetInfo]:
    """Return available bot preset descriptors."""
    return [
        PresetInfo(
            preset_type=key,
            display_name=entry["display_name"],
            description=entry["description"],
            params=entry["params"],
        )
        for key, entry in PRESETS_REGISTRY.items()
    ]


@router.post("/from-preset", response_model=GenerateFromPresetResponse)
async def generate_from_preset(body: GenerateFromPresetRequest) -> GenerateFromPresetResponse:
    """Generate strategy rules from a preset type and parameters."""
    entry = PRESETS_REGISTRY.get(body.preset_type)
    if entry is None:
        raise HTTPException(
            status_code=422,
            detail=f"Unknown preset_type '{body.preset_type}'. Available: {list(PRESETS_REGISTRY)}",
        )

    generator = entry["generator"]

    # Cast int-typed params from float → int
    int_param_names = {p.name for p in entry["params"] if p.type == "int"}
    coerced_params: dict[str, int | float] = {}
    for k, v in body.params.items():
        coerced_params[k] = int(v) if k in int_param_names else v

    try:
        rules = generator(**coerced_params)
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return GenerateFromPresetResponse(
        preset_type=body.preset_type,
        rules=rules,
        num_rules=len(rules),
    )


# ---------------------------------------------------------------------------
# CRUD endpoints
# ---------------------------------------------------------------------------


def _strategy_to_response(s: Strategy) -> StrategyResponse:
    return StrategyResponse(
        id=s.id,
        name=s.name,
        description=s.description,
        rules=[r.model_dump() for r in s.rules],
        profile_name=s.profile_name,
        is_preset=s.is_preset,
        created_at=s.created_at,
        num_rules=len(s.rules),
    )


@router.post("", response_model=StrategyResponse, status_code=201)
async def create_strategy(body: CreateStrategyRequest) -> StrategyResponse:
    """Create a custom strategy from user-supplied rules."""
    # Validate each rule dict as a StrategyRule
    parsed_rules: list[StrategyRule] = []
    for idx, rule_dict in enumerate(body.rules):
        try:
            parsed_rules.append(StrategyRule(**rule_dict))
        except ValidationError as exc:
            raise HTTPException(
                status_code=422,
                detail=f"Invalid rule at index {idx}: {exc.error_count()} validation error(s)",
            ) from exc

    strategy = Strategy(
        name=body.name,
        description=body.description,
        rules=parsed_rules,
        profile_name=body.profile_name,
    )
    _strategies_store[strategy.id] = strategy
    return _strategy_to_response(strategy)


@router.get("", response_model=StrategyListResponse)
async def list_strategies() -> StrategyListResponse:
    """Return all custom strategies."""
    items = [_strategy_to_response(s) for s in _strategies_store.values()]
    return StrategyListResponse(strategies=items, count=len(items))


@router.get("/{strategy_id}", response_model=StrategyResponse)
async def get_strategy(strategy_id: str) -> StrategyResponse:
    """Get a single strategy by ID."""
    strategy = _strategies_store.get(strategy_id)
    if strategy is None:
        raise HTTPException(status_code=404, detail="Strategy not found")
    return _strategy_to_response(strategy)


@router.delete("/{strategy_id}", status_code=204)
async def delete_strategy(strategy_id: str) -> Response:
    """Delete a strategy by ID."""
    if _strategies_store.pop(strategy_id, None) is None:
        raise HTTPException(status_code=404, detail="Strategy not found")
    return Response(status_code=204)
