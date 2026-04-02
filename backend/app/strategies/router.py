"""Preset strategies API — list presets and generate rules."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from app.strategies.presets import generate_btd_rules, generate_dca_rules, generate_grid_rules
from app.strategies.schemas import (
    GenerateFromPresetRequest,
    GenerateFromPresetResponse,
    PresetInfo,
    PresetParamSchema,
)

router = APIRouter(prefix="/api/v1/strategies", tags=["strategies"])

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
