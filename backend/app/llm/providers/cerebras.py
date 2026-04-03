"""Cerebras LLM provider — fastest inference, free tier (1M tokens/day)."""

from __future__ import annotations

import httpx

from app.config import settings
from app.logging_config import get_logger

from .base import BaseLLMProvider, LLMResponse

log = get_logger(__name__)

DEFAULT_MODEL = "llama3.1-8b"

MODEL_PRICING: dict[str, tuple[float, float]] = {
    "llama3.1-8b": (0.0, 0.0),
    "qwen-3-235b-a22b-instruct-2507": (0.0, 0.0),
    "gpt-oss-120b": (0.0, 0.0),
}


class CerebrasProvider(BaseLLMProvider):
    """Cerebras — ultra-fast inference, free 1M tokens/day."""

    def __init__(self, api_key: str | None = None, model: str | None = None):
        self._api_key = api_key or settings.CEREBRAS_API_KEY
        self._default_model = model or DEFAULT_MODEL
        if not self._api_key:
            raise ValueError("CEREBRAS_API_KEY not configured")

    @property
    def provider_name(self) -> str:
        return "cerebras"

    def get_pricing(self, model: str) -> tuple[float, float]:
        return MODEL_PRICING.get(model, (0.0, 0.0))

    async def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        model: str | None = None,
        temperature: float = 0.3,
        max_tokens: int = 4000,
    ) -> LLMResponse:
        use_model = model or self._default_model

        log.debug("llm.request_start", provider="cerebras", model=use_model)

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
                "https://api.cerebras.ai/v1/chat/completions",
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

        log.debug("llm.request_done", provider="cerebras", model=use_model,
                  input_tokens=usage.get("prompt_tokens", 0),
                  output_tokens=usage.get("completion_tokens", 0))

        return LLMResponse(
            content=content,
            model=use_model,
            provider="cerebras",
            input_tokens=usage.get("prompt_tokens", 0),
            output_tokens=usage.get("completion_tokens", 0),
        )
