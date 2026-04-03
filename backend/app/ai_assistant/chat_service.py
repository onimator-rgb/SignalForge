"""Chat service — orchestrates intent detection, agent dispatch, persistence."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai_assistant.agents.base import AgentResponse, ParsedIntent
from app.ai_assistant.agents.intent_router import detect_intent
from app.ai_assistant.agents.registry import get_agent
from app.ai_assistant.models import ChatMessage, ChatSession
from app.logging_config import get_logger

log = get_logger(__name__)


async def handle_chat_message(
    db: AsyncSession,
    message: str,
    session_id: str | None = None,
) -> tuple[ChatSession, ChatMessage, AgentResponse]:
    """Full chat flow: session -> save user msg -> intent -> agent -> save response."""

    # 1. Get or create session
    session = await _get_or_create_session(db, session_id)

    # 2. Save user message
    user_msg = ChatMessage(
        session_id=session.id,
        role="user",
        content=message,
    )
    db.add(user_msg)
    await db.flush()

    # 3. Load conversation history
    history = await get_conversation_history(db, session.id, limit=10)

    # 4. Detect intent
    intent = await detect_intent(message, db)

    # 5. Get agent
    agent = get_agent(intent.agent_type)
    if agent is None:
        # Fallback to market_analyst
        agent = get_agent("market_analyst")
        intent.agent_type = "market_analyst"

    # 6. Get user profile (singleton)
    user_profile = await _get_user_profile(db)

    # 7. Call agent
    response = await agent.respond(
        db=db,
        intent=intent,
        conversation_history=history,
        user_profile=user_profile,
    )

    # 8. Save assistant message
    assistant_msg = ChatMessage(
        session_id=session.id,
        role="assistant",
        content=response.content,
        agent_type=response.agent_type,
        llm_provider=response.provider,
        llm_model=response.model,
        input_tokens=response.input_tokens,
        output_tokens=response.output_tokens,
        latency_ms=response.latency_ms,
    )
    db.add(assistant_msg)

    # 9. Update session
    title = session.title
    if not title:
        title = _auto_title(message)

    total_tokens = response.input_tokens + response.output_tokens
    await db.execute(
        update(ChatSession)
        .where(ChatSession.id == session.id)
        .values(
            title=title,
            agent_type=response.agent_type,
            message_count=ChatSession.message_count + 2,
            total_tokens=ChatSession.total_tokens + total_tokens,
            updated_at=datetime.now(timezone.utc),
        )
    )

    # 10. Increment user interaction count
    await _increment_interaction(db)

    await db.commit()

    # Refresh to get updated values
    await db.refresh(session)

    log.info(
        "chat.message_handled",
        session_id=str(session.id),
        agent=response.agent_type,
        model=response.model,
        latency_ms=response.latency_ms,
    )

    return session, assistant_msg, response


async def get_conversation_history(
    db: AsyncSession,
    session_id: uuid.UUID,
    limit: int = 10,
) -> list[dict]:
    """Load last N messages as simple dicts for prompt context."""
    result = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at.desc())
        .limit(limit)
    )
    messages = result.scalars().all()

    # Reverse to chronological order, skip the just-saved user message
    history = []
    for msg in reversed(messages):
        history.append({"role": msg.role, "content": msg.content})

    # Cap history text at ~8000 chars
    total_chars = 0
    trimmed: list[dict] = []
    for msg in reversed(history):
        total_chars += len(msg["content"])
        if total_chars > 8000:
            break
        trimmed.insert(0, msg)

    return trimmed


async def list_sessions(db: AsyncSession, limit: int = 50) -> list[ChatSession]:
    """List chat sessions, most recent first."""
    result = await db.execute(
        select(ChatSession)
        .where(ChatSession.is_active.is_(True))
        .order_by(ChatSession.updated_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())


async def get_session_with_messages(
    db: AsyncSession,
    session_id: uuid.UUID,
) -> tuple[ChatSession | None, list[ChatMessage]]:
    """Load a session and all its messages."""
    session = await db.get(ChatSession, session_id)
    if not session:
        return None, []

    result = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at.asc())
    )
    messages = list(result.scalars().all())
    return session, messages


async def delete_session(db: AsyncSession, session_id: uuid.UUID) -> bool:
    """Soft-delete a session."""
    session = await db.get(ChatSession, session_id)
    if not session:
        return False
    session.is_active = False
    await db.commit()
    return True


async def submit_feedback(
    db: AsyncSession,
    message_id: uuid.UUID,
    score: int,
) -> bool:
    """Set feedback score on a message."""
    result = await db.execute(
        update(ChatMessage)
        .where(ChatMessage.id == message_id)
        .values(feedback_score=score)
    )
    await db.commit()
    return result.rowcount > 0


# ── Private helpers ────────────────────────────────────────────────

async def _get_or_create_session(
    db: AsyncSession,
    session_id: str | None,
) -> ChatSession:
    """Get existing session or create new one."""
    if session_id:
        try:
            sid = uuid.UUID(session_id)
            session = await db.get(ChatSession, sid)
            if session and session.is_active:
                return session
        except ValueError:
            pass  # Invalid UUID — create new

    session = ChatSession()
    db.add(session)
    await db.flush()
    return session


def _auto_title(message: str) -> str:
    """Generate title from first user message."""
    title = message.strip().replace("\n", " ")
    if len(title) > 60:
        title = title[:57] + "..."
    return title


async def _get_user_profile(db: AsyncSession) -> dict | None:
    """Load singleton user AI profile."""
    from app.ai_assistant.models import UserAIProfile

    result = await db.execute(select(UserAIProfile).limit(1))
    profile = result.scalar_one_or_none()
    if not profile:
        return None
    return {
        "experience_level": profile.experience_level,
        "preferred_language": profile.preferred_language,
        "preferred_assets": profile.preferred_assets,
    }


async def _increment_interaction(db: AsyncSession) -> None:
    """Increment user interaction count."""
    from app.ai_assistant.models import UserAIProfile

    result = await db.execute(select(UserAIProfile).limit(1))
    profile = result.scalar_one_or_none()
    if profile:
        profile.interaction_count += 1
