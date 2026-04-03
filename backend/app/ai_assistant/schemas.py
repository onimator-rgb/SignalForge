"""Pydantic schemas for AI Assistant chat API."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=5000)
    session_id: str | None = None


class ChatResponse(BaseModel):
    session_id: str
    message_id: str
    content: str
    agent_type: str
    model: str = ""
    provider: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    latency_ms: int = 0


class MessageOut(BaseModel):
    id: str
    role: str
    content: str
    agent_type: str | None = None
    llm_model: str | None = None
    created_at: datetime
    feedback_score: int | None = None


class SessionOut(BaseModel):
    id: str
    title: str | None = None
    agent_type: str = "general"
    message_count: int = 0
    created_at: datetime
    updated_at: datetime


class SessionDetailOut(SessionOut):
    messages: list[MessageOut] = []


class FeedbackRequest(BaseModel):
    message_id: str
    score: int = Field(..., ge=-1, le=1)  # -1 bad, 0 neutral, 1 good


class AgentInfo(BaseModel):
    name: str
    description: str
    complexity: str
