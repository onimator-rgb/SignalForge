"""Tests for the multi-provider LLM router and cost tracking."""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.llm.providers.base import LLMResponse
from app.llm.cost_tracker import calculate_cost
from app.llm.router import (
    LLMRouter,
    TaskComplexity,
    ModelTier,
    ROUTING_TABLE,
    _is_provider_configured,
    _MODEL_REGISTRY,
)


# ---------------------------------------------------------------------------
# Cost calculation tests
# ---------------------------------------------------------------------------

class TestCalculateCost:
    def test_gemini_flash_cost(self):
        # 1000 input tokens, 500 output tokens at gemini-2.0-flash pricing
        cost = calculate_cost("gemini-2.0-flash", 1000, 500)
        # (1000 * 0.075 + 500 * 0.30) / 1_000_000 = 0.000225
        assert cost == Decimal("0.000225")

    def test_free_model_zero_cost(self):
        cost = calculate_cost("local-template-v1", 5000, 2000)
        assert cost == Decimal("0")

    def test_claude_sonnet_cost(self):
        cost = calculate_cost("claude-sonnet-4-20250514", 1000, 1000)
        # (1000 * 3.0 + 1000 * 15.0) / 1_000_000 = 0.018
        assert cost == Decimal("0.018")

    def test_unknown_model_default_pricing(self):
        cost = calculate_cost("unknown-model-xyz", 1000, 1000)
        # default: (0.10, 0.30) -> (1000*0.10 + 1000*0.30)/1M = 0.0004
        assert cost == Decimal("0.0004")

    def test_zero_tokens(self):
        cost = calculate_cost("gemini-2.0-flash", 0, 0)
        assert cost == Decimal("0")

    def test_groq_llama_cost(self):
        cost = calculate_cost("llama-3.3-70b-versatile", 10000, 5000)
        # (10000 * 0.59 + 5000 * 0.79) / 1_000_000 = 0.00985
        assert cost == Decimal("0.00985")


# ---------------------------------------------------------------------------
# Routing table tests
# ---------------------------------------------------------------------------

class TestRoutingTable:
    def test_all_complexities_have_routes(self):
        for complexity in TaskComplexity:
            assert complexity in ROUTING_TABLE
            assert len(ROUTING_TABLE[complexity]) >= 1

    def test_trivial_prefers_cheap_or_free(self):
        providers = [p for p, _ in ROUTING_TABLE[TaskComplexity.TRIVIAL]]
        # Should start with cheap/free providers, not claude
        assert providers[0] in ("gemini", "groq", "ollama", "cerebras", "sambanova")

    def test_critical_includes_claude(self):
        providers = [p for p, _ in ROUTING_TABLE[TaskComplexity.CRITICAL]]
        assert "claude" in providers

    def test_simple_includes_free_models(self):
        providers = [p for p, _ in ROUTING_TABLE[TaskComplexity.SIMPLE]]
        assert "groq" in providers

    def test_model_registry_has_all_tiers(self):
        tiers = {tier for _, _, tier in _MODEL_REGISTRY}
        assert ModelTier.FREE in tiers
        assert ModelTier.CHEAP in tiers
        assert ModelTier.STANDARD in tiers
        assert ModelTier.PREMIUM in tiers


# ---------------------------------------------------------------------------
# Provider configuration check tests
# ---------------------------------------------------------------------------

class TestProviderConfigured:
    @patch("app.llm.router.settings")
    def test_gemini_configured(self, mock_settings):
        mock_settings.GEMINI_API_KEY = "test-key"
        assert _is_provider_configured("gemini") is True

    @patch("app.llm.router.settings")
    def test_gemini_not_configured(self, mock_settings):
        mock_settings.GEMINI_API_KEY = ""
        assert _is_provider_configured("gemini") is False

    @patch("app.llm.router.settings")
    def test_ollama_always_configured(self, mock_settings):
        mock_settings.OLLAMA_BASE_URL = "http://localhost:11434"
        assert _is_provider_configured("ollama") is True

    def test_unknown_provider(self):
        assert _is_provider_configured("nonexistent") is False


# ---------------------------------------------------------------------------
# Router integration tests (with mocked providers)
# ---------------------------------------------------------------------------

class TestLLMRouter:
    @pytest.mark.asyncio
    async def test_route_to_first_available(self):
        mock_response = LLMResponse(
            content="Test response",
            model="gemini-2.0-flash",
            provider="gemini",
            input_tokens=100,
            output_tokens=50,
        )

        router = LLMRouter(cost_tracker=MagicMock(record=AsyncMock(return_value=Decimal("0"))))

        with patch("app.llm.router._is_provider_configured", return_value=True), \
             patch("app.llm.router._create_provider") as mock_create:
            mock_provider = AsyncMock()
            mock_provider.complete.return_value = mock_response
            mock_create.return_value = mock_provider

            result = await router.complete(
                system_prompt="You are helpful.",
                user_prompt="Hello",
                complexity=TaskComplexity.SIMPLE,
            )

        assert result.content == "Test response"
        assert result.provider == "gemini"

    @pytest.mark.asyncio
    async def test_fallback_on_error(self):
        """When first provider fails, router should try next."""
        good_response = LLMResponse(
            content="Fallback works",
            model="mistral-small-latest",
            provider="mistral",
            input_tokens=100,
            output_tokens=50,
        )

        mock_tracker = MagicMock(record=AsyncMock(return_value=Decimal("0")))
        router = LLMRouter(cost_tracker=mock_tracker)

        call_count = 0

        async def mock_complete(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ConnectionError("Provider down")
            return good_response

        with patch("app.llm.router._is_provider_configured", return_value=True), \
             patch("app.llm.router._create_provider") as mock_create:
            mock_provider = AsyncMock()
            mock_provider.complete = mock_complete
            mock_create.return_value = mock_provider

            result = await router.complete(
                system_prompt="Test",
                user_prompt="Hello",
                complexity=TaskComplexity.MODERATE,
            )

        assert result.content == "Fallback works"
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_all_fail_returns_local(self):
        """When all providers fail, should return local template response."""
        mock_tracker = MagicMock(record=AsyncMock(return_value=Decimal("0")))
        router = LLMRouter(cost_tracker=mock_tracker)

        with patch("app.llm.router._is_provider_configured", return_value=True), \
             patch("app.llm.router._create_provider") as mock_create:
            mock_provider = AsyncMock()
            mock_provider.complete.side_effect = ConnectionError("All down")
            mock_create.return_value = mock_provider

            result = await router.complete(
                system_prompt="Test",
                user_prompt="Hello",
                complexity=TaskComplexity.TRIVIAL,
            )

        # Should fall back to local template
        assert result.provider == "local"

    @pytest.mark.asyncio
    async def test_preferred_provider_tried_first(self):
        mock_response = LLMResponse(
            content="Preferred response",
            model="claude-haiku-4-5-20251001",
            provider="claude",
            input_tokens=100,
            output_tokens=50,
        )

        mock_tracker = MagicMock(record=AsyncMock(return_value=Decimal("0")))
        router = LLMRouter(cost_tracker=mock_tracker)

        with patch("app.llm.router._is_provider_configured", return_value=True), \
             patch("app.llm.router._create_provider") as mock_create:
            mock_provider = AsyncMock()
            mock_provider.complete.return_value = mock_response
            mock_create.return_value = mock_provider

            result = await router.complete(
                system_prompt="Test",
                user_prompt="Hello",
                complexity=TaskComplexity.SIMPLE,
                preferred_provider="claude",
                preferred_model="claude-haiku-4-5-20251001",
            )

        assert result.content == "Preferred response"
        # Verify claude was the first provider tried
        first_call = mock_create.call_args_list[0]
        assert first_call[0][0] == "claude"

    @pytest.mark.asyncio
    async def test_skips_unconfigured_providers(self):
        mock_response = LLMResponse(
            content="OK",
            model="ollama",
            provider="ollama",
            input_tokens=100,
            output_tokens=50,
        )

        mock_tracker = MagicMock(record=AsyncMock(return_value=Decimal("0")))
        router = LLMRouter(cost_tracker=mock_tracker)

        def is_configured(name):
            # Only ollama is configured
            return name == "ollama"

        with patch("app.llm.router._is_provider_configured", side_effect=is_configured), \
             patch("app.llm.router._create_provider") as mock_create:
            mock_provider = AsyncMock()
            mock_provider.complete.return_value = mock_response
            mock_create.return_value = mock_provider

            result = await router.complete(
                system_prompt="Test",
                user_prompt="Hello",
                complexity=TaskComplexity.TRIVIAL,
            )

        assert result.content == "OK"

    def test_get_available_providers(self):
        with patch("app.llm.router._is_provider_configured") as mock_check:
            mock_check.side_effect = lambda name: name in ("gemini", "groq")
            router = LLMRouter()
            providers = router.get_available_providers()

        provider_names = {p["provider"] for p in providers}
        assert "gemini" in provider_names
        assert "groq" in provider_names
        assert "claude" not in provider_names

    def test_build_candidate_list_with_preferred(self):
        router = LLMRouter()
        candidates = router._build_candidate_list(
            TaskComplexity.SIMPLE, "claude", "claude-haiku-4-5-20251001"
        )
        # Preferred should be first
        assert candidates[0] == ("claude", "claude-haiku-4-5-20251001")
        # Routing table entries should follow
        assert len(candidates) > 1


# ---------------------------------------------------------------------------
# Provider unit tests (structure only, no real API calls)
# ---------------------------------------------------------------------------

class TestProviderStructure:
    def test_gemini_provider_name(self):
        with patch("app.llm.providers.gemini.settings") as mock_settings:
            mock_settings.GEMINI_API_KEY = "test"
            from app.llm.providers.gemini import GeminiProvider
            p = GeminiProvider(api_key="test")
            assert p.provider_name == "gemini"

    def test_groq_provider_name(self):
        with patch("app.llm.providers.groq.settings") as mock_settings:
            mock_settings.GROQ_API_KEY = "test"
            from app.llm.providers.groq import GroqProvider
            p = GroqProvider(api_key="test")
            assert p.provider_name == "groq"

    def test_mistral_provider_name(self):
        with patch("app.llm.providers.mistral.settings") as mock_settings:
            mock_settings.MISTRAL_API_KEY = "test"
            from app.llm.providers.mistral import MistralProvider
            p = MistralProvider(api_key="test")
            assert p.provider_name == "mistral"

    def test_openrouter_provider_name(self):
        with patch("app.llm.providers.openrouter.settings") as mock_settings:
            mock_settings.OPENROUTER_API_KEY = "test"
            from app.llm.providers.openrouter import OpenRouterProvider
            p = OpenRouterProvider(api_key="test")
            assert p.provider_name == "openrouter"

    def test_ollama_provider_name(self):
        with patch("app.llm.providers.ollama.settings") as mock_settings:
            mock_settings.OLLAMA_BASE_URL = "http://localhost:11434"
            from app.llm.providers.ollama import OllamaProvider
            p = OllamaProvider()
            assert p.provider_name == "ollama"

    def test_gemini_pricing(self):
        with patch("app.llm.providers.gemini.settings") as mock_settings:
            mock_settings.GEMINI_API_KEY = "test"
            from app.llm.providers.gemini import GeminiProvider
            p = GeminiProvider(api_key="test")
            inp, out = p.get_pricing("gemini-2.0-flash")
            assert inp == 0.075
            assert out == 0.30

    def test_ollama_pricing_always_free(self):
        with patch("app.llm.providers.ollama.settings") as mock_settings:
            mock_settings.OLLAMA_BASE_URL = "http://localhost:11434"
            from app.llm.providers.ollama import OllamaProvider
            p = OllamaProvider()
            inp, out = p.get_pricing("any-model")
            assert inp == 0.0
            assert out == 0.0


# ---------------------------------------------------------------------------
# Client backward compatibility
# ---------------------------------------------------------------------------

class TestClientBackwardCompat:
    def test_get_llm_provider_local(self):
        with patch("app.llm.client.settings") as mock_settings:
            mock_settings.LLM_PROVIDER = "local"
            from app.llm.client import get_llm_provider
            provider = get_llm_provider()
            assert provider.provider_name == "local"

    def test_get_llm_provider_gemini(self):
        with patch("app.llm.client.settings") as mock_settings:
            mock_settings.LLM_PROVIDER = "gemini"
            mock_settings.GEMINI_API_KEY = "test-key"
            from app.llm.client import get_llm_provider
            # Patch the gemini module settings too
            with patch("app.llm.providers.gemini.settings") as gs:
                gs.GEMINI_API_KEY = "test-key"
                provider = get_llm_provider()
                assert provider.provider_name == "gemini"
