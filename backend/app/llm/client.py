"""LLM client facade — selects provider, handles errors."""

from app.config import settings
from app.logging_config import get_logger

from .providers.base import BaseLLMProvider, LLMResponse
from .providers.claude import ClaudeProvider

log = get_logger(__name__)


def get_llm_provider() -> BaseLLMProvider:
    """Get the configured LLM provider. Currently Claude only."""
    provider_name = settings.LLM_PROVIDER
    if provider_name == "claude":
        return ClaudeProvider()
    raise ValueError(f"Unknown LLM provider: {provider_name}")


async def llm_complete(
    system_prompt: str,
    user_prompt: str,
    temperature: float = 0.3,
    max_tokens: int = 4000,
) -> LLMResponse:
    """Convenience function: get provider and call complete."""
    provider = get_llm_provider()
    return await provider.complete(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        temperature=temperature,
        max_tokens=max_tokens,
    )
