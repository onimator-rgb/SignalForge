"""Ollama LLM provider — local models, zero cost, offline capable."""

from __future__ import annotations

import httpx

from app.config import settings
from app.logging_config import get_logger

from .base import BaseLLMProvider, LLMResponse

log = get_logger(__name__)

DEFAULT_MODEL = "llama3.1:8b"


class OllamaProvider(BaseLLMProvider):
    """Ollama — local LLM inference server (OpenAI-compatible endpoint)."""

    def __init__(self, base_url: str | None = None, model: str | None = None):
        self._base_url = (base_url or settings.OLLAMA_BASE_URL).rstrip("/")
        self._default_model = model or DEFAULT_MODEL

    @property
    def provider_name(self) -> str:
        return "ollama"

    def get_pricing(self, model: str) -> tuple[float, float]:
        return (0.0, 0.0)

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
            provider="ollama",
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
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
            "stream": False,
        }

        async with httpx.AsyncClient(timeout=180.0) as client:
            resp = await client.post(
                f"{self._base_url}/api/chat",
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()

        content = data["message"]["content"]
        input_tokens = data.get("prompt_eval_count", 0)
        output_tokens = data.get("eval_count", 0)

        log.debug(
            "llm.request_done",
            provider="ollama",
            model=use_model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )

        return LLMResponse(
            content=content,
            model=use_model,
            provider="ollama",
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )
