"""Portfolio endpoints — summary, positions, transactions."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.portfolio.service import evaluate_portfolio, get_portfolio_summary

router = APIRouter(prefix="/api/v1/portfolio", tags=["portfolio"])


@router.get("")
async def portfolio_summary(db: AsyncSession = Depends(get_db)):
    """Get full demo portfolio: stats, positions, transactions."""
    return await get_portfolio_summary(db)


@router.post("/evaluate")
async def trigger_evaluation(db: AsyncSession = Depends(get_db)):
    """Manually trigger portfolio evaluation (check entries/exits)."""
    result = await evaluate_portfolio(db)
    return {"status": "ok", **result}
