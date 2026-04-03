"""Base class for all AI assistant agents."""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from sqlalchemy.ext.asyncio import AsyncSession

from app.llm.router import TaskComplexity, routed_complete
from app.logging_config import get_logger

log = get_logger(__name__)


@dataclass
class ParsedIntent:
    """Result of intent detection."""
    agent_type: str
    asset_symbols: list[str] = field(default_factory=list)
    topic: str = ""
    raw_message: str = ""
    confidence: float = 1.0


@dataclass
class AgentResponse:
    """Response from an agent."""
    content: str
    agent_type: str
    context_used: dict | None = None
    model: str = ""
    provider: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    latency_ms: int = 0


class BaseAssistantAgent(ABC):
    """Abstract base for all assistant agents."""

    name: str = ""
    description: str = ""
    complexity: TaskComplexity = TaskComplexity.MODERATE

    @abstractmethod
    def get_system_prompt(self, user_profile: dict | None = None) -> str:
        """Return the system prompt for this agent."""
        ...

    @abstractmethod
    async def build_context(self, db: AsyncSession, intent: ParsedIntent) -> dict:
        """Build context dict from DB for the current query."""
        ...

    def format_user_prompt(
        self,
        message: str,
        context: dict,
        conversation_history: list[dict],
    ) -> str:
        """Assemble the user prompt from message + context + history."""
        parts: list[str] = []

        # Conversation history (sliding window)
        if conversation_history:
            parts.append("=== HISTORIA ROZMOWY ===")
            for msg in conversation_history[-10:]:
                role = "Uzytkownik" if msg["role"] == "user" else "Asystent"
                parts.append(f"{role}: {msg['content']}")
            parts.append("")

        # Context
        if context:
            parts.append("=== DANE RYNKOWE ===")
            parts.append(_format_context(context))
            parts.append("")

        # Current message
        parts.append(f"=== AKTUALNE PYTANIE ===\n{message}")

        return "\n".join(parts)

    async def respond(
        self,
        db: AsyncSession,
        intent: ParsedIntent,
        conversation_history: list[dict],
        user_profile: dict | None = None,
    ) -> AgentResponse:
        """Orchestrate: build context -> format prompt -> call LLM -> return response."""
        t_start = time.monotonic()

        context = await self.build_context(db, intent)
        system_prompt = self.get_system_prompt(user_profile)
        user_prompt = self.format_user_prompt(
            intent.raw_message, context, conversation_history
        )

        llm_response = await routed_complete(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            complexity=self.complexity,
            agent_name=self.name,
            task_type="chat",
            temperature=0.4,
            max_tokens=3000,
        )

        latency_ms = int((time.monotonic() - t_start) * 1000)

        log.info(
            "agent.respond_done",
            agent=self.name,
            model=llm_response.model,
            provider=llm_response.provider,
            input_tokens=llm_response.input_tokens,
            output_tokens=llm_response.output_tokens,
            latency_ms=latency_ms,
        )

        return AgentResponse(
            content=llm_response.content,
            agent_type=self.name,
            context_used=context if context else None,
            model=llm_response.model,
            provider=llm_response.provider,
            input_tokens=llm_response.input_tokens,
            output_tokens=llm_response.output_tokens,
            latency_ms=latency_ms,
        )


def _format_context(ctx: dict, indent: int = 0) -> str:
    """Recursively format context dict for LLM prompt."""
    lines: list[str] = []
    prefix = "  " * indent
    for key, value in ctx.items():
        if isinstance(value, dict):
            lines.append(f"{prefix}{key}:")
            lines.append(_format_context(value, indent + 1))
        elif isinstance(value, list):
            lines.append(f"{prefix}{key}: [{len(value)} items]")
            for i, item in enumerate(value[:5]):  # Cap at 5 items
                if isinstance(item, dict):
                    lines.append(f"{prefix}  [{i}]:")
                    lines.append(_format_context(item, indent + 2))
                else:
                    lines.append(f"{prefix}  - {item}")
        else:
            lines.append(f"{prefix}{key}: {value}")
    return "\n".join(lines)
