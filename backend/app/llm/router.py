"""Intelligent LLM Router — selects cheapest capable model with fallback chain.

Routes requests to the optimal model based on task complexity, available
providers, and cost budget. Implements automatic fallback when a provider
fails (timeout, rate-limit, error).
"""

from __future__ import annotations

import time
from enum import Enum

from app.config import settings
from app.logging_config import get_logger

from .cost_tracker import CostTracker
from .providers.base import BaseLLMProvider, LLMResponse

log = get_logger(__name__)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class TaskComplexity(str, Enum):
    """How hard is the task — drives model selection."""
    TRIVIAL = "trivial"      # intent detection, classification
    SIMPLE = "simple"        # FAQ, education, simple lookups
    MODERATE = "moderate"    # market analysis, portfolio review
    COMPLEX = "complex"      # risk assessment, multi-factor analysis
    CRITICAL = "critical"    # trading decisions, anomaly deep-dive


class ModelTier(str, Enum):
    FREE = "free"
    CHEAP = "cheap"
    STANDARD = "standard"
    PREMIUM = "premium"


# ---------------------------------------------------------------------------
# Model registry — (provider_name, model_id, tier)
# ---------------------------------------------------------------------------

_MODEL_REGISTRY: list[tuple[str, str, ModelTier]] = [
    # Free tier — $0 cost
    ("cerebras", "llama3.1-8b", ModelTier.FREE),
    ("sambanova", "Meta-Llama-3.3-70B-Instruct", ModelTier.FREE),
    ("groq", "llama-3.3-70b-versatile", ModelTier.FREE),
    ("groq", "llama-3.1-8b-instant", ModelTier.FREE),
    ("openrouter", "nvidia/nemotron-3-super-120b-a12b:free", ModelTier.FREE),
    ("openrouter", "google/gemma-3-12b-it:free", ModelTier.FREE),
    ("openrouter", "meta-llama/llama-3.3-70b-instruct:free", ModelTier.FREE),
    ("ollama", "llama3.1:8b", ModelTier.FREE),
    # Cheap tier — under $0.50/1M tokens
    ("gemini", "gemini-2.5-flash", ModelTier.CHEAP),
    ("gemini", "gemini-2.5-flash-lite", ModelTier.CHEAP),
    ("mistral", "mistral-small-latest", ModelTier.CHEAP),
    # Standard tier
    ("claude", "claude-haiku-4-5-20251001", ModelTier.STANDARD),
    ("mistral", "mistral-large-latest", ModelTier.STANDARD),
    # Premium tier
    ("claude", "claude-sonnet-4-20250514", ModelTier.PREMIUM),
]

# Complexity → ordered list of (provider, model) to try
# Strategy: free first, then cheap, then paid
ROUTING_TABLE: dict[TaskComplexity, list[tuple[str, str]]] = {
    TaskComplexity.TRIVIAL: [
        ("cerebras", "llama3.1-8b"),
        ("groq", "llama-3.1-8b-instant"),
        ("gemini", "gemini-2.5-flash-lite"),
        ("ollama", "llama3.1:8b"),
    ],
    TaskComplexity.SIMPLE: [
        ("cerebras", "llama3.1-8b"),
        ("groq", "llama-3.3-70b-versatile"),
        ("sambanova", "Meta-Llama-3.3-70B-Instruct"),
        ("gemini", "gemini-2.5-flash"),
        ("mistral", "mistral-small-latest"),
        ("ollama", "llama3.1:8b"),
    ],
    TaskComplexity.MODERATE: [
        ("gemini", "gemini-2.5-flash"),
        ("cerebras", "llama3.1-8b"),
        ("groq", "llama-3.3-70b-versatile"),
        ("mistral", "mistral-small-latest"),
    ],
    TaskComplexity.COMPLEX: [
        ("gemini", "gemini-2.5-flash"),
        ("mistral", "mistral-small-latest"),
        ("cerebras", "llama3.1-8b"),
        ("claude", "claude-haiku-4-5-20251001"),
    ],
    TaskComplexity.CRITICAL: [
        ("claude", "claude-haiku-4-5-20251001"),
        ("gemini", "gemini-2.5-flash"),
        ("claude", "claude-sonnet-4-20250514"),
    ],
}


# ---------------------------------------------------------------------------
# Provider factory
# ---------------------------------------------------------------------------

def _create_provider(provider_name: str, model: str | None = None) -> BaseLLMProvider:
    """Lazily create a provider instance. Raises ValueError if not configured."""
    if provider_name == "gemini":
        from .providers.gemini import GeminiProvider
        return GeminiProvider(model=model)
    if provider_name == "groq":
        from .providers.groq import GroqProvider
        return GroqProvider(model=model)
    if provider_name == "mistral":
        from .providers.mistral import MistralProvider
        return MistralProvider(model=model)
    if provider_name == "openrouter":
        from .providers.openrouter import OpenRouterProvider
        return OpenRouterProvider(model=model)
    if provider_name == "ollama":
        from .providers.ollama import OllamaProvider
        return OllamaProvider(model=model)
    if provider_name == "claude":
        from .providers.claude import ClaudeProvider
        return ClaudeProvider(model=model)
    if provider_name == "cerebras":
        from .providers.cerebras import CerebrasProvider
        return CerebrasProvider(model=model)
    if provider_name == "sambanova":
        from .providers.sambanova import SambaNovaProvider
        return SambaNovaProvider(model=model)
    raise ValueError(f"Unknown provider: {provider_name}")


def _is_provider_configured(provider_name: str) -> bool:
    """Check if the provider has the necessary API key / endpoint configured."""
    checks = {
        "gemini": lambda: bool(settings.GEMINI_API_KEY),
        "groq": lambda: bool(settings.GROQ_API_KEY),
        "mistral": lambda: bool(settings.MISTRAL_API_KEY),
        "openrouter": lambda: bool(settings.OPENROUTER_API_KEY),
        "ollama": lambda: bool(settings.OLLAMA_BASE_URL),
        "claude": lambda: bool(settings.ANTHROPIC_API_KEY),
        "cerebras": lambda: bool(settings.CEREBRAS_API_KEY),
        "sambanova": lambda: bool(settings.SAMBANOVA_API_KEY),
    }
    check = checks.get(provider_name)
    return check() if check else False


# ---------------------------------------------------------------------------
# LLM Router
# ---------------------------------------------------------------------------

class LLMRouter:
    """Intelligent router that picks the cheapest model for the task
    and falls back through alternatives on failure."""

    def __init__(self, cost_tracker: CostTracker | None = None):
        self._cost_tracker = cost_tracker or CostTracker()

    async def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        complexity: TaskComplexity = TaskComplexity.MODERATE,
        agent_name: str = "",
        task_type: str = "chat",
        temperature: float = 0.3,
        max_tokens: int = 4000,
        preferred_provider: str | None = None,
        preferred_model: str | None = None,
    ) -> LLMResponse:
        """Route to the best available model with automatic fallback.

        If *preferred_provider* / *preferred_model* are given they are
        tried first, before the routing table.
        """
        candidates = self._build_candidate_list(
            complexity, preferred_provider, preferred_model,
        )

        last_error: Exception | None = None

        for provider_name, model_id in candidates:
            if not _is_provider_configured(provider_name):
                log.debug(
                    "llm.router.skip",
                    provider=provider_name,
                    reason="not configured",
                )
                continue

            try:
                provider = _create_provider(provider_name, model_id)
                start = time.monotonic()
                response = await provider.complete(
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    model=model_id,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                latency_ms = int((time.monotonic() - start) * 1000)

                # Track cost
                await self._cost_tracker.record(
                    provider=provider_name,
                    model=model_id,
                    input_tokens=response.input_tokens,
                    output_tokens=response.output_tokens,
                    agent_name=agent_name,
                    task_type=task_type,
                    latency_ms=latency_ms,
                    success=True,
                )

                log.info(
                    "llm.router.success",
                    provider=provider_name,
                    model=model_id,
                    complexity=complexity.value,
                    latency_ms=latency_ms,
                    input_tokens=response.input_tokens,
                    output_tokens=response.output_tokens,
                )
                return response

            except Exception as exc:
                last_error = exc
                log.warning(
                    "llm.router.fallback",
                    provider=provider_name,
                    model=model_id,
                    error=str(exc),
                )
                await self._cost_tracker.record(
                    provider=provider_name,
                    model=model_id,
                    input_tokens=0,
                    output_tokens=0,
                    agent_name=agent_name,
                    task_type=task_type,
                    latency_ms=0,
                    success=False,
                    error_message=str(exc),
                )
                continue

        # All candidates exhausted — fall back to local template
        log.error(
            "llm.router.all_failed",
            complexity=complexity.value,
            candidates_tried=len(candidates),
            last_error=str(last_error) if last_error else "no candidates",
        )
        from .providers.local import LocalTemplateProvider
        return await LocalTemplateProvider().complete(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
        )

    def _build_candidate_list(
        self,
        complexity: TaskComplexity,
        preferred_provider: str | None,
        preferred_model: str | None,
    ) -> list[tuple[str, str]]:
        """Build ordered list: preferred first, then routing table."""
        candidates: list[tuple[str, str]] = []

        if preferred_provider and preferred_model:
            candidates.append((preferred_provider, preferred_model))

        for provider_name, model_id in ROUTING_TABLE.get(complexity, []):
            pair = (provider_name, model_id)
            if pair not in candidates:
                candidates.append(pair)

        return candidates

    def get_available_providers(self) -> list[dict]:
        """Return list of configured providers with their models."""
        result = []
        seen_providers: set[str] = set()
        for provider_name, model_id, tier in _MODEL_REGISTRY:
            if not _is_provider_configured(provider_name):
                continue
            if provider_name not in seen_providers:
                seen_providers.add(provider_name)
            result.append({
                "provider": provider_name,
                "model": model_id,
                "tier": tier.value,
                "configured": True,
            })
        return result


# ---------------------------------------------------------------------------
# Module-level convenience
# ---------------------------------------------------------------------------

_router: LLMRouter | None = None


def get_router() -> LLMRouter:
    """Get or create the singleton router instance."""
    global _router
    if _router is None:
        _router = LLMRouter()
    return _router


async def routed_complete(
    system_prompt: str,
    user_prompt: str,
    *,
    complexity: TaskComplexity = TaskComplexity.MODERATE,
    agent_name: str = "",
    task_type: str = "chat",
    temperature: float = 0.3,
    max_tokens: int = 4000,
    preferred_provider: str | None = None,
    preferred_model: str | None = None,
) -> LLMResponse:
    """Convenience function — route through the singleton router."""
    router = get_router()
    return await router.complete(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        complexity=complexity,
        agent_name=agent_name,
        task_type=task_type,
        temperature=temperature,
        max_tokens=max_tokens,
        preferred_provider=preferred_provider,
        preferred_model=preferred_model,
    )
