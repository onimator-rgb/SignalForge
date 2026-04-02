"""Webhook signal receiver — accepts external buy/sell signals and buffers them in-memory."""

from __future__ import annotations

from collections import deque
from datetime import datetime, timezone
from typing import Any, Literal
from uuid import uuid4

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class WebhookSignal(BaseModel):
    """Incoming webhook payload."""

    symbol: str
    action: Literal["buy", "sell"]
    source: str
    confidence: float = Field(ge=0.0, le=1.0)
    metadata: dict[str, Any] | None = None


class StoredSignal(BaseModel):
    """Signal enriched with server-side id and timestamp."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    received_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    symbol: str
    action: Literal["buy", "sell"]
    source: str
    confidence: float = Field(ge=0.0, le=1.0)
    metadata: dict[str, Any] | None = None


class WebhookResponse(BaseModel):
    """Response returned after accepting a signal."""

    id: str
    status: Literal["accepted"]


# ---------------------------------------------------------------------------
# In-memory buffer
# ---------------------------------------------------------------------------

_signal_buffer: deque[StoredSignal] = deque(maxlen=1000)

# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

router = APIRouter(prefix="/api/v1/signals", tags=["signals"])


@router.post("/webhook", response_model=WebhookResponse, status_code=201)
async def receive_signal(payload: WebhookSignal) -> WebhookResponse:
    """Accept an external trading signal and buffer it."""
    stored = StoredSignal(
        symbol=payload.symbol,
        action=payload.action,
        source=payload.source,
        confidence=payload.confidence,
        metadata=payload.metadata,
    )
    _signal_buffer.append(stored)
    return WebhookResponse(id=stored.id, status="accepted")


@router.get("/", response_model=list[StoredSignal])
async def list_signals(limit: int = Query(default=50, ge=1, le=1000)) -> list[StoredSignal]:
    """Return buffered signals, newest first."""
    return list(reversed(_signal_buffer))[:limit]
