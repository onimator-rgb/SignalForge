"""Agent registry — manages available assistant agents."""

from __future__ import annotations

from app.ai_assistant.agents.base import BaseAssistantAgent
from app.ai_assistant.agents.market_analyst import MarketAnalystAgent
from app.ai_assistant.agents.education_coach import EducationCoachAgent


_AGENTS: dict[str, BaseAssistantAgent] = {}


def _ensure_registered() -> None:
    """Register built-in agents on first access."""
    if _AGENTS:
        return
    for agent in [MarketAnalystAgent(), EducationCoachAgent()]:
        _AGENTS[agent.name] = agent


def get_agent(agent_type: str) -> BaseAssistantAgent | None:
    """Get agent by type name."""
    _ensure_registered()
    return _AGENTS.get(agent_type)


def get_all_agents() -> list[BaseAssistantAgent]:
    """Return all registered agents."""
    _ensure_registered()
    return list(_AGENTS.values())
