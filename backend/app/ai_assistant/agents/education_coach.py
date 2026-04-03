"""Education Coach agent — trading education using free/cheap models."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai_assistant.agents.base import BaseAssistantAgent, ParsedIntent
from app.ai_assistant.prompts import get_education_system_prompt
from app.llm.router import TaskComplexity


class EducationCoachAgent(BaseAssistantAgent):
    name = "education_coach"
    description = "Answers trading education questions — indicators, strategies, risk management, terminology"
    complexity = TaskComplexity.SIMPLE  # Routes to free/cheap models

    def get_system_prompt(self, user_profile: dict | None = None) -> str:
        return get_education_system_prompt(user_profile)

    async def build_context(self, db: AsyncSession, intent: ParsedIntent) -> dict:
        # Education agent uses pure knowledge — no DB context needed
        return {}
