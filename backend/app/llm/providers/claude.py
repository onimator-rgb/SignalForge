"""Anthropic Claude LLM provider."""

import httpx

from app.config import settings
from app.logging_config import get_logger

from .base import BaseLLMProvider, LLMResponse

log = get_logger(__name__)

DEFAULT_MODEL = "claude-sonnet-4-20250514"


class ClaudeProvider(BaseLLMProvider):
    def __init__(self, api_key: str | None = None, model: str | None = None):
        self._api_key = api_key or settings.ANTHROPIC_API_KEY
        self._default_model = model or settings.LLM_MODEL or DEFAULT_MODEL
        if not self._api_key:
            raise ValueError("ANTHROPIC_API_KEY not configured")

    @property
    def provider_name(self) -> str:
        return "claude"

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
            provider="claude",
            model=use_model,
            system_len=len(system_prompt),
            user_len=len(user_prompt),
        )

        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": self._api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": use_model,
                    "max_tokens": max_tokens,
                    "temperature": temperature,
                    "system": system_prompt,
                    "messages": [{"role": "user", "content": user_prompt}],
                },
            )
            resp.raise_for_status()
            data = resp.json()

        content = data["content"][0]["text"]
        usage = data.get("usage", {})

        log.debug(
            "llm.request_done",
            provider="claude",
            model=data.get("model", use_model),
            input_tokens=usage.get("input_tokens", 0),
            output_tokens=usage.get("output_tokens", 0),
        )

        return LLMResponse(
            content=content,
            model=data.get("model", use_model),
            provider="claude",
            input_tokens=usage.get("input_tokens", 0),
            output_tokens=usage.get("output_tokens", 0),
        )
