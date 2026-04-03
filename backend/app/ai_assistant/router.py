"""AI Assistant API — chat, sessions, feedback, portfolio report, strategy suggestions."""

from __future__ import annotations

import asyncio
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai_assistant.schemas import (
    AgentInfo,
    ChatRequest,
    ChatResponse,
    FeedbackRequest,
    MessageOut,
    SessionDetailOut,
    SessionOut,
)
from app.database import get_db
from app.logging_config import get_logger

log = get_logger(__name__)

router = APIRouter(prefix="/api/v1/ai", tags=["ai"])


# ── Chat endpoints ─────────────────────────────────────────────────


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest, db: AsyncSession = Depends(get_db)) -> ChatResponse:
    """Send a message and get a response from the AI assistant."""
    from app.ai_assistant.chat_service import handle_chat_message

    session, assistant_msg, response = await handle_chat_message(
        db=db,
        message=request.message,
        session_id=request.session_id,
    )

    return ChatResponse(
        session_id=str(session.id),
        message_id=str(assistant_msg.id),
        content=response.content,
        agent_type=response.agent_type,
        model=response.model,
        provider=response.provider,
        input_tokens=response.input_tokens,
        output_tokens=response.output_tokens,
        latency_ms=response.latency_ms,
    )


@router.get("/chat/stream")
async def chat_stream(
    message: str = Query(..., min_length=1, max_length=5000),
    session_id: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """SSE streaming chat — simulated word-by-word delivery."""
    from app.ai_assistant.chat_service import handle_chat_message

    # Process the full message first
    session, assistant_msg, response = await handle_chat_message(
        db=db,
        message=message,
        session_id=session_id,
    )

    async def event_generator():
        # Split response into word chunks for streaming effect
        words = response.content.split(" ")
        chunk_size = 3
        for i in range(0, len(words), chunk_size):
            chunk = " ".join(words[i:i + chunk_size])
            if i > 0:
                chunk = " " + chunk
            yield f"data: {chunk}\n\n"
            await asyncio.sleep(0.03)

        # Final metadata event
        import json
        meta = json.dumps({
            "type": "done",
            "session_id": str(session.id),
            "message_id": str(assistant_msg.id),
            "agent_type": response.agent_type,
            "model": response.model,
            "provider": response.provider,
            "input_tokens": response.input_tokens,
            "output_tokens": response.output_tokens,
            "latency_ms": response.latency_ms,
        })
        yield f"event: meta\ndata: {meta}\n\n"
        yield "event: done\ndata: \n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ── Session endpoints ──────────────────────────────────────────────


@router.get("/sessions", response_model=list[SessionOut])
async def list_sessions(db: AsyncSession = Depends(get_db)) -> list[SessionOut]:
    """List all active chat sessions."""
    from app.ai_assistant.chat_service import list_sessions as _list

    sessions = await _list(db)
    return [
        SessionOut(
            id=str(s.id),
            title=s.title,
            agent_type=s.agent_type,
            message_count=s.message_count,
            created_at=s.created_at,
            updated_at=s.updated_at,
        )
        for s in sessions
    ]


@router.get("/sessions/{session_id}", response_model=SessionDetailOut)
async def get_session(
    session_id: str,
    db: AsyncSession = Depends(get_db),
) -> SessionDetailOut:
    """Get session details with all messages."""
    from app.ai_assistant.chat_service import get_session_with_messages

    try:
        sid = uuid.UUID(session_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid session ID")

    session, messages = await get_session_with_messages(db, sid)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    return SessionDetailOut(
        id=str(session.id),
        title=session.title,
        agent_type=session.agent_type,
        message_count=session.message_count,
        created_at=session.created_at,
        updated_at=session.updated_at,
        messages=[
            MessageOut(
                id=str(m.id),
                role=m.role,
                content=m.content,
                agent_type=m.agent_type,
                llm_model=m.llm_model,
                created_at=m.created_at,
                feedback_score=m.feedback_score,
            )
            for m in messages
        ],
    )


@router.delete("/sessions/{session_id}")
async def delete_session(
    session_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Delete (deactivate) a chat session."""
    from app.ai_assistant.chat_service import delete_session as _delete

    try:
        sid = uuid.UUID(session_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid session ID")

    ok = await _delete(db, sid)
    if not ok:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"deleted": True}


# ── Feedback ───────────────────────────────────────────────────────


@router.post("/feedback")
async def submit_feedback(
    request: FeedbackRequest,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Submit feedback for an assistant message."""
    from app.ai_assistant.chat_service import submit_feedback as _feedback

    try:
        mid = uuid.UUID(request.message_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid message ID")

    ok = await _feedback(db, mid, request.score)
    if not ok:
        raise HTTPException(status_code=404, detail="Message not found")
    return {"ok": True}


# ── Agents info ────────────────────────────────────────────────────


@router.get("/agents", response_model=list[AgentInfo])
async def list_agents() -> list[AgentInfo]:
    """List available AI assistant agents."""
    from app.ai_assistant.agents.registry import get_all_agents

    return [
        AgentInfo(
            name=a.name,
            description=a.description,
            complexity=a.complexity.value,
        )
        for a in get_all_agents()
    ]


# ── Legacy endpoints (preserved) ──────────────────────────────────


@router.get("/portfolio-report")
async def portfolio_report(db: AsyncSession = Depends(get_db)) -> dict:
    """Generate a plain-text portfolio analysis report."""
    from app.ai_assistant.portfolio_report import (
        PositionSummary,
        RiskSnapshot,
        TradeSummary,
        generate_portfolio_report,
    )
    from app.assets.models import Asset
    from app.portfolio.models import Portfolio, PortfolioPosition, PortfolioTransaction

    result = await db.execute(
        select(Portfolio).where(Portfolio.is_active.is_(True)).limit(1)
    )
    portfolio = result.scalar_one_or_none()

    if portfolio is None:
        report = generate_portfolio_report(
            positions=[],
            risk=RiskSnapshot(
                sharpe_ratio=None, sortino_ratio=None, max_drawdown_pct=0.0,
                profit_factor=None, win_rate=None, total_closed=0, wins=0,
                losses=0, avg_hold_hours=0.0,
            ),
            recent_trades=[], regime="neutral", current_cash=0.0, initial_capital=0.0,
        )
        return {"report": report}

    pos_rows = await db.execute(
        select(PortfolioPosition, Asset.symbol)
        .join(Asset, PortfolioPosition.asset_id == Asset.id)
        .where(PortfolioPosition.portfolio_id == portfolio.id)
    )
    positions: list[PositionSummary] = []
    closed_positions_data: list[PortfolioPosition] = []
    for row in pos_rows.all():
        pos = row.PortfolioPosition
        symbol = row.symbol
        unrealized_pnl_pct: float | None = None
        if pos.status == "open" and pos.entry_price and pos.entry_price > 0:
            current = float(pos.peak_price) if pos.peak_price else float(pos.entry_price)
            unrealized_pnl_pct = (current - float(pos.entry_price)) / float(pos.entry_price) * 100
        if pos.status != "open":
            closed_positions_data.append(pos)
        positions.append(
            PositionSummary(
                symbol=symbol, entry_price=float(pos.entry_price),
                current_price=float(pos.peak_price) if pos.peak_price else None,
                quantity=float(pos.quantity), unrealized_pnl_pct=unrealized_pnl_pct,
                status=pos.status, close_reason=pos.close_reason,
                realized_pnl_pct=float(pos.realized_pnl_pct) if pos.realized_pnl_pct is not None else None,
            )
        )

    wins = sum(1 for p in closed_positions_data if p.realized_pnl_pct is not None and float(p.realized_pnl_pct) > 0)
    losses = sum(1 for p in closed_positions_data if p.realized_pnl_pct is not None and float(p.realized_pnl_pct) <= 0)
    total_closed = len(closed_positions_data)
    win_rate = (wins / total_closed * 100) if total_closed > 0 else None
    realized_pcts = [float(p.realized_pnl_pct) for p in closed_positions_data if p.realized_pnl_pct is not None]
    best_trade = max(realized_pcts) if realized_pcts else None
    worst_trade = min(realized_pcts) if realized_pcts else None

    risk = RiskSnapshot(
        sharpe_ratio=None, sortino_ratio=None,
        max_drawdown_pct=abs(worst_trade) if worst_trade and worst_trade < 0 else 0.0,
        profit_factor=None, win_rate=win_rate, total_closed=total_closed,
        wins=wins, losses=losses, avg_hold_hours=0.0,
        best_trade_pct=best_trade, worst_trade_pct=worst_trade,
    )

    tx_rows = await db.execute(
        select(PortfolioTransaction, Asset.symbol)
        .join(Asset, PortfolioTransaction.asset_id == Asset.id)
        .where(PortfolioTransaction.portfolio_id == portfolio.id)
        .order_by(PortfolioTransaction.executed_at.desc())
        .limit(5)
    )
    recent_trades: list[TradeSummary] = []
    for tx_row in tx_rows.all():
        tx = tx_row.PortfolioTransaction
        recent_trades.append(
            TradeSummary(
                symbol=tx_row.symbol, action=tx.tx_type, price=float(tx.price),
                quantity=float(tx.quantity), value_usd=float(tx.value_usd),
            )
        )

    regime = "neutral"
    try:
        from app.strategy.regime import calculate_regime
        regime_data = await calculate_regime(db)
        regime = regime_data.get("regime", "neutral")
    except Exception:
        log.warning("ai.regime_unavailable", fallback="neutral")

    report = generate_portfolio_report(
        positions=positions, risk=risk, recent_trades=recent_trades,
        regime=regime, current_cash=float(portfolio.current_cash),
        initial_capital=float(portfolio.initial_capital),
    )
    log.info("ai.portfolio_report_generated", positions=len(positions), regime=regime)
    return {"report": report}


@router.get("/strategy-suggestions/{strategy_id}")
async def strategy_suggestions(
    strategy_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Return improvement suggestions for a strategy."""
    log.info("ai.strategy_suggestions_requested", strategy_id=strategy_id)
    return {
        "suggestions": [],
        "strategy_id": strategy_id,
        "message": "Strategy CRUD not yet available — suggestions will be enabled once strategy management endpoints are merged.",
    }
