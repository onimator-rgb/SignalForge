"""Portfolio endpoints — summary, positions, transactions, manual close."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.portfolio.service import evaluate_portfolio, get_portfolio_summary, manual_close_position

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


@router.post("/positions/{position_id}/close")
async def close_position(position_id: UUID, db: AsyncSession = Depends(get_db)):
    """Manually close a demo position at current market price."""
    try:
        result = await manual_close_position(db, position_id)
        return result
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
