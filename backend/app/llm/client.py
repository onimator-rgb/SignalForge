"""LLM client facade — selects provider, handles errors.

Supports two modes:
1. Legacy: direct provider selection via LLM_PROVIDER setting
2. Router: intelligent routing via LLMRouter (recommended for new code)

New code should use `routed_complete()` from `app.llm.router` or the
`llm_complete()` function here with `use_router=True`.
"""

from __future__ import annotations

from app.config import settings
from app.logging_config import get_logger

from .providers.base import BaseLLMProvider, LLMResponse
from .providers.local import LocalTemplateProvider
from .router import TaskComplexity, routed_complete

log = get_logger(__name__)


def get_llm_provider() -> BaseLLMProvider:
    """Get the configured LLM provider (legacy mode). Defaults to local templates."""
    provider_name = settings.LLM_PROVIDER
    if provider_name == "local":
        return LocalTemplateProvider()
    if provider_name == "claude":
        from .providers.claude import ClaudeProvider
        return ClaudeProvider()
    if provider_name == "gemini":
        from .providers.gemini import GeminiProvider
        return GeminiProvider()
    if provider_name == "groq":
        from .providers.groq import GroqProvider
        return GroqProvider()
    if provider_name == "mistral":
        from .providers.mistral import MistralProvider
        return MistralProvider()
    if provider_name == "openrouter":
        from .providers.openrouter import OpenRouterProvider
        return OpenRouterProvider()
    if provider_name == "ollama":
        from .providers.ollama import OllamaProvider
        return OllamaProvider()
    raise ValueError(f"Unknown LLM provider: {provider_name}")


async def llm_complete(
    system_prompt: str,
    user_prompt: str,
    temperature: float = 0.3,
    max_tokens: int = 4000,
    *,
    report_type: str = "",
    context: dict | None = None,
    use_router: bool = False,
    complexity: TaskComplexity = TaskComplexity.MODERATE,
    agent_name: str = "",
    task_type: str = "",
) -> LLMResponse:
    """Convenience function: get provider and call complete.

    Set ``use_router=True`` to use the intelligent multi-provider router
    with automatic fallback and cost tracking.
    """
    # New path: intelligent routing
    if use_router:
        return await routed_complete(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            complexity=complexity,
            agent_name=agent_name,
            task_type=task_type,
            temperature=temperature,
            max_tokens=max_tokens,
        )

    # Legacy path: direct provider
    provider = get_llm_provider()
    if isinstance(provider, LocalTemplateProvider):
        return await provider.complete(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            report_type=report_type,
            context=context,
        )
    return await provider.complete(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        temperature=temperature,
        max_tokens=max_tokens,
    )
