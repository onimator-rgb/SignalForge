"""Groq LLM provider — ultra-fast inference, free tier available."""

from __future__ import annotations

import httpx

from app.config import settings
from app.logging_config import get_logger

from .base import BaseLLMProvider, LLMResponse

log = get_logger(__name__)

DEFAULT_MODEL = "llama-3.3-70b-versatile"

# Pricing per 1M tokens (USD) — free tier has rate limits
MODEL_PRICING: dict[str, tuple[float, float]] = {
    "llama-3.3-70b-versatile": (0.59, 0.79),
    "llama-3.1-8b-instant": (0.05, 0.08),
    "mixtral-8x7b-32768": (0.24, 0.24),
    "gemma2-9b-it": (0.20, 0.20),
}


class GroqProvider(BaseLLMProvider):
    """Groq Cloud — OpenAI-compatible API with blazing fast inference."""

    def __init__(self, api_key: str | None = None, model: str | None = None):
        self._api_key = api_key or settings.GROQ_API_KEY
        self._default_model = model or DEFAULT_MODEL
        if not self._api_key:
            raise ValueError("GROQ_API_KEY not configured")

    @property
    def provider_name(self) -> str:
        return "groq"

    def get_pricing(self, model: str) -> tuple[float, float]:
        """Return (input_price_per_1m, output_price_per_1m)."""
        return MODEL_PRICING.get(model, (0.59, 0.79))

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
            provider="groq",
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

        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
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
            provider="groq",
            model=use_model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )

        return LLMResponse(
            content=content,
            model=use_model,
            provider="groq",
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )
