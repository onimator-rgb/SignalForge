"""Strategies router — parameter optimization endpoint."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, field_validator

from app.strategies.optimizer import OptimizationResult, ParamRange, optimize_params
from app.strategy.profiles import PROFILES

router = APIRouter(prefix="/api/v1/strategies", tags=["strategies"])


class OptimizeResultItem(BaseModel):
    params: dict[str, float]
    sharpe_ratio: float
    total_return_pct: float
    max_drawdown_pct: float
    win_rate: float
    profit_factor: float
    total_trades: int


class OptimizeResponse(BaseModel):
    results: list[OptimizeResultItem]


class OptimizeRequest(BaseModel):
    profile_name: str
    param_ranges: dict[str, list[float]]
    prices: list[float]
    top_n: int = 5
    initial_capital: float = 1000.0

    @field_validator("prices")
    @classmethod
    def prices_min_length(cls, v: list[float]) -> list[float]:
        if len(v) < 10:
            raise ValueError("At least 10 price data points are required.")
        return v


@router.post("/optimize", response_model=OptimizeResponse)
async def optimize_strategy(body: OptimizeRequest) -> OptimizeResponse:
    """Run grid-search optimization over strategy parameters."""
    if body.profile_name not in PROFILES:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid profile_name '{body.profile_name}'. "
            f"Must be one of: {', '.join(sorted(PROFILES))}",
        )

    base_profile = PROFILES[body.profile_name]
    ranges = [
        ParamRange(field_name=k, values=v) for k, v in body.param_ranges.items()
    ]

    try:
        results = optimize_params(
            base_profile,
            body.prices,
            ranges,
            body.top_n,
            body.initial_capital,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return OptimizeResponse(
        results=[_result_to_item(r) for r in results],
    )


def _result_to_item(r: OptimizationResult) -> OptimizeResultItem:
    return OptimizeResultItem(
        params=r.params,
        sharpe_ratio=r.sharpe_ratio,
        total_return_pct=r.total_return_pct,
        max_drawdown_pct=r.max_drawdown_pct,
        win_rate=r.win_rate,
        profit_factor=r.profit_factor,
        total_trades=r.total_trades,
    )
