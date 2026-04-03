"""Google Gemini LLM provider — optimized for cost (Flash models)."""

from __future__ import annotations

import httpx

from app.config import settings
from app.logging_config import get_logger

from .base import BaseLLMProvider, LLMResponse

log = get_logger(__name__)

DEFAULT_MODEL = "gemini-2.5-flash"

# Pricing per 1M tokens (USD) — April 2026
# NOTE: gemini-2.0-flash deprecated June 2026 — use 2.5 variants
MODEL_PRICING: dict[str, tuple[float, float]] = {
    "gemini-2.5-flash": (0.075, 0.30),
    "gemini-2.5-flash-lite": (0.02, 0.075),
    "gemini-2.0-flash": (0.075, 0.30),       # DEPRECATED — remove after June 2026
    "gemini-2.0-flash-lite": (0.02, 0.075),   # DEPRECATED
    "gemini-1.5-pro": (1.25, 5.00),
}


class GeminiProvider(BaseLLMProvider):
    """Google Gemini via REST API (generativelanguage.googleapis.com)."""

    def __init__(self, api_key: str | None = None, model: str | None = None):
        self._api_key = api_key or settings.GEMINI_API_KEY
        self._default_model = model or DEFAULT_MODEL
        if not self._api_key:
            raise ValueError("GEMINI_API_KEY not configured")

    @property
    def provider_name(self) -> str:
        return "gemini"

    def get_pricing(self, model: str) -> tuple[float, float]:
        """Return (input_price_per_1m, output_price_per_1m)."""
        return MODEL_PRICING.get(model, (0.075, 0.30))

    async def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        model: str | None = None,
        temperature: float = 0.3,
        max_tokens: int = 4000,
    ) -> LLMResponse:
        use_model = model or self._default_model
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/"
            f"models/{use_model}:generateContent?key={self._api_key}"
        )

        log.debug(
            "llm.request_start",
            provider="gemini",
            model=use_model,
            system_len=len(system_prompt),
            user_len=len(user_prompt),
        )

        payload = {
            "contents": [{"parts": [{"text": user_prompt}]}],
            "systemInstruction": {"parts": [{"text": system_prompt}]},
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens,
            },
        }

        async with httpx.AsyncClient(timeout=90.0) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            data = resp.json()

        # Extract content
        candidates = data.get("candidates", [])
        if not candidates:
            raise ValueError("Gemini returned no candidates")
        content = candidates[0]["content"]["parts"][0]["text"]

        # Extract usage
        usage = data.get("usageMetadata", {})
        input_tokens = usage.get("promptTokenCount", 0)
        output_tokens = usage.get("candidatesTokenCount", 0)

        log.debug(
            "llm.request_done",
            provider="gemini",
            model=use_model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )

        return LLMResponse(
            content=content,
            model=use_model,
            provider="gemini",
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )
