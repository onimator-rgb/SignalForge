"""Mistral AI LLM provider — cost-effective European models."""

from __future__ import annotations

import httpx

from app.config import settings
from app.logging_config import get_logger

from .base import BaseLLMProvider, LLMResponse

log = get_logger(__name__)

DEFAULT_MODEL = "mistral-small-latest"

MODEL_PRICING: dict[str, tuple[float, float]] = {
    "mistral-small-latest": (0.10, 0.30),
    "mistral-medium-latest": (2.70, 8.10),
    "mistral-large-latest": (2.00, 6.00),
    "open-mistral-nemo": (0.15, 0.15),
    "codestral-latest": (0.30, 0.90),
}


class MistralProvider(BaseLLMProvider):
    """Mistral AI — OpenAI-compatible chat completions API."""

    def __init__(self, api_key: str | None = None, model: str | None = None):
        self._api_key = api_key or settings.MISTRAL_API_KEY
        self._default_model = model or DEFAULT_MODEL
        if not self._api_key:
            raise ValueError("MISTRAL_API_KEY not configured")

    @property
    def provider_name(self) -> str:
        return "mistral"

    def get_pricing(self, model: str) -> tuple[float, float]:
        return MODEL_PRICING.get(model, (0.10, 0.30))

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
            provider="mistral",
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
                "https://api.mistral.ai/v1/chat/completions",
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
            provider="mistral",
            model=use_model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )

        return LLMResponse(
            content=content,
            model=use_model,
            provider="mistral",
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )
