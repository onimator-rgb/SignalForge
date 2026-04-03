"""OpenRouter LLM provider — unified gateway to 100+ models."""

from __future__ import annotations

import httpx

from app.config import settings
from app.logging_config import get_logger

from .base import BaseLLMProvider, LLMResponse

log = get_logger(__name__)

DEFAULT_MODEL = "google/gemini-2.0-flash-exp:free"

# Popular cheap models via OpenRouter
MODEL_PRICING: dict[str, tuple[float, float]] = {
    "google/gemini-2.0-flash-exp:free": (0.0, 0.0),
    "meta-llama/llama-3.3-70b-instruct:free": (0.0, 0.0),
    "mistralai/mistral-small-3.1-24b-instruct:free": (0.0, 0.0),
    "google/gemini-2.0-flash-001": (0.10, 0.40),
    "anthropic/claude-3.5-haiku": (0.80, 4.00),
    "anthropic/claude-sonnet-4": (3.00, 15.00),
}


class OpenRouterProvider(BaseLLMProvider):
    """OpenRouter — single API for 100+ models with unified billing."""

    def __init__(self, api_key: str | None = None, model: str | None = None):
        self._api_key = api_key or settings.OPENROUTER_API_KEY
        self._default_model = model or DEFAULT_MODEL
        if not self._api_key:
            raise ValueError("OPENROUTER_API_KEY not configured")

    @property
    def provider_name(self) -> str:
        return "openrouter"

    def get_pricing(self, model: str) -> tuple[float, float]:
        return MODEL_PRICING.get(model, (0.10, 0.40))

    async def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        model: str | None = None,
        temperature: float = 0.3,
        max_tokens: int = 4000,
    ) -> LLMResponse:
        use_model = model or self._default_model

        log.debug(
            "llm.request_start",
            provider="openrouter",
            model=use_model,
            system_len=len(system_prompt),
            user_len=len(user_prompt),
        )

        payload = {
            "model": use_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        async with httpx.AsyncClient(timeout=90.0) as client:
            resp = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://marketpulse.local",
                    "X-Title": "MarketPulse AI",
                },
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()

        content = data["choices"][0]["message"]["content"]
        usage = data.get("usage", {})
        input_tokens = usage.get("prompt_tokens", 0)
        output_tokens = usage.get("completion_tokens", 0)

        log.debug(
            "llm.request_done",
            provider="openrouter",
            model=use_model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )

        return LLMResponse(
            content=content,
            model=use_model,
            provider="openrouter",
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )
