"""Tests for AI Trader Arena — personalities, decisions, routing."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.ai_traders.base import BaseAITrader, TradeAction, TradeDecision, DECISION_FORMAT
from app.ai_traders.registry import get_all_traders, get_trader_by_slug, TRADER_DESCRIPTIONS
from app.llm.providers.base import LLMResponse
from app.llm.router import TaskComplexity


# ---------------------------------------------------------------------------
# Registry tests
# ---------------------------------------------------------------------------

class TestRegistry:
    def test_get_all_traders_returns_9(self):
        traders = get_all_traders()
        assert len(traders) == 9

    def test_all_traders_have_unique_slugs(self):
        traders = get_all_traders()
        slugs = [t.slug for t in traders]
        assert len(slugs) == len(set(slugs))

    def test_all_traders_have_unique_names(self):
        traders = get_all_traders()
        names = [t.name for t in traders]
        assert len(names) == len(set(names))

    def test_get_trader_by_slug(self):
        trader = get_trader_by_slug("conservative_quant")
        assert trader is not None
        assert trader.name == "Conservative Quant"

    def test_get_trader_by_slug_not_found(self):
        trader = get_trader_by_slug("nonexistent")
        assert trader is None

    def test_all_traders_have_descriptions(self):
        traders = get_all_traders()
        for t in traders:
            assert t.slug in TRADER_DESCRIPTIONS

    def test_all_traders_have_system_prompts(self):
        traders = get_all_traders()
        for t in traders:
            prompt = t.get_system_prompt()
            assert len(prompt) > 100
            assert "JSON" in prompt  # All prompts require JSON output

    def test_all_traders_have_risk_params(self):
        traders = get_all_traders()
        for t in traders:
            assert "max_position_pct" in t.risk_params
            assert "stop_loss_pct" in t.risk_params
            assert "take_profit_pct" in t.risk_params
            assert t.risk_params["max_position_pct"] > 0
            assert t.risk_params["max_position_pct"] <= 0.30


# ---------------------------------------------------------------------------
# Personality diversity tests
# ---------------------------------------------------------------------------

class TestPersonalityDiversity:
    def test_different_llm_providers(self):
        """Traders should use diverse LLM providers."""
        traders = get_all_traders()
        providers = {t.llm_provider for t in traders}
        assert len(providers) >= 3  # At least 3 different providers

    def test_different_risk_profiles(self):
        """Traders should have different risk levels."""
        traders = get_all_traders()
        max_positions = [t.risk_params["max_position_pct"] for t in traders]
        # Should not all be the same
        assert len(set(max_positions)) >= 3

    def test_conservative_has_lowest_risk(self):
        cq = get_trader_by_slug("conservative_quant")
        mh = get_trader_by_slug("momentum_hunter")
        assert cq.risk_params["max_position_pct"] < mh.risk_params["max_position_pct"]
        assert abs(cq.risk_params["stop_loss_pct"]) < abs(mh.risk_params["stop_loss_pct"])

    def test_momentum_has_highest_reward(self):
        mh = get_trader_by_slug("momentum_hunter")
        cq = get_trader_by_slug("conservative_quant")
        assert mh.risk_params["take_profit_pct"] > cq.risk_params["take_profit_pct"]

    def test_complexity_levels_vary(self):
        """Different traders should use different complexity levels."""
        traders = get_all_traders()
        complexities = {t.get_complexity() for t in traders}
        assert len(complexities) >= 2


# ---------------------------------------------------------------------------
# Decision parsing tests
# ---------------------------------------------------------------------------

class TestDecisionParsing:
    def _make_trader(self):
        """Create a minimal test trader."""
        class TestTrader(BaseAITrader):
            def get_system_prompt(self):
                return "Test"
            def get_complexity(self):
                return TaskComplexity.SIMPLE

        return TestTrader(
            name="Test", slug="test",
            llm_provider="groq", llm_model="test",
            risk_params={"max_position_pct": 0.20},
        )

    def test_parse_valid_buy_json(self):
        trader = self._make_trader()
        raw = json.dumps({
            "action": "buy",
            "confidence": 0.85,
            "reasoning": "Strong oversold signal with RSI at 22",
            "position_size_pct": 0.15,
            "stop_loss_price": 62000,
            "take_profit_price": 72000,
        })
        decision = trader._parse_decision(raw)
        assert decision.action == TradeAction.BUY
        assert decision.confidence == 0.85
        assert decision.position_size_pct == 0.15
        assert decision.stop_loss_price == 62000
        assert decision.take_profit_price == 72000

    def test_parse_sell_decision(self):
        trader = self._make_trader()
        raw = json.dumps({
            "action": "sell",
            "confidence": 0.72,
            "reasoning": "Take profit reached, overbought RSI",
        })
        decision = trader._parse_decision(raw)
        assert decision.action == TradeAction.SELL
        assert decision.confidence == 0.72

    def test_parse_hold_decision(self):
        trader = self._make_trader()
        raw = json.dumps({
            "action": "hold",
            "confidence": 0.50,
            "reasoning": "Mixed signals, waiting for clarity",
        })
        decision = trader._parse_decision(raw)
        assert decision.action == TradeAction.HOLD

    def test_parse_skip_decision(self):
        trader = self._make_trader()
        raw = json.dumps({
            "action": "skip",
            "confidence": 0.30,
            "reasoning": "No data available",
        })
        decision = trader._parse_decision(raw)
        assert decision.action == TradeAction.SKIP

    def test_parse_json_in_markdown_block(self):
        trader = self._make_trader()
        raw = '```json\n{"action": "buy", "confidence": 0.8, "reasoning": "test"}\n```'
        decision = trader._parse_decision(raw)
        assert decision.action == TradeAction.BUY

    def test_parse_json_with_surrounding_text(self):
        trader = self._make_trader()
        raw = 'Here is my analysis:\n{"action": "sell", "confidence": 0.6, "reasoning": "overbought"}\nEnd.'
        decision = trader._parse_decision(raw)
        assert decision.action == TradeAction.SELL

    def test_parse_invalid_json_returns_skip(self):
        trader = self._make_trader()
        raw = "This is not valid JSON at all"
        decision = trader._parse_decision(raw)
        assert decision.action == TradeAction.SKIP
        assert decision.confidence == 0.0

    def test_parse_invalid_action_returns_skip(self):
        trader = self._make_trader()
        raw = json.dumps({"action": "moon", "confidence": 0.5, "reasoning": "test"})
        decision = trader._parse_decision(raw)
        assert decision.action == TradeAction.SKIP

    def test_confidence_clamped_to_0_1(self):
        trader = self._make_trader()
        raw = json.dumps({"action": "buy", "confidence": 5.0, "reasoning": "test"})
        decision = trader._parse_decision(raw)
        assert decision.confidence == 1.0

        raw2 = json.dumps({"action": "buy", "confidence": -2.0, "reasoning": "test"})
        decision2 = trader._parse_decision(raw2)
        assert decision2.confidence == 0.0

    def test_position_size_capped_by_risk_params(self):
        trader = self._make_trader()
        raw = json.dumps({
            "action": "buy",
            "confidence": 0.9,
            "reasoning": "test",
            "position_size_pct": 0.50,  # Exceeds max_position_pct of 0.20
        })
        decision = trader._parse_decision(raw)
        assert decision.position_size_pct == 0.20  # Capped


# ---------------------------------------------------------------------------
# User prompt building tests
# ---------------------------------------------------------------------------

class TestPromptBuilding:
    def _make_trader(self):
        class TestTrader(BaseAITrader):
            def get_system_prompt(self):
                return "Test"
            def get_complexity(self):
                return TaskComplexity.SIMPLE

        return TestTrader(
            name="Test", slug="test",
            llm_provider="groq", llm_model="test",
        )

    def test_prompt_contains_asset_info(self):
        trader = self._make_trader()
        ctx = {
            "asset": {"symbol": "BTC", "name": "Bitcoin"},
            "price": {"current": 67000, "change_24h_pct": 2.3},
            "indicators": {"composite_score": 72},
            "anomalies": [],
            "timestamp": "2026-04-03T12:00:00",
        }
        prompt = trader.build_user_prompt(ctx)
        assert "BTC" in prompt
        assert "67000" in prompt
        assert "Your Task" in prompt

    def test_prompt_includes_anomalies(self):
        trader = self._make_trader()
        ctx = {
            "asset": {"symbol": "ETH"},
            "price": {"current": 3500},
            "indicators": {},
            "anomalies": [{"type": "price_spike", "severity": "high"}],
            "timestamp": "now",
        }
        prompt = trader.build_user_prompt(ctx)
        assert "Anomalies" in prompt
        assert "price_spike" in prompt

    def test_prompt_includes_existing_position(self):
        trader = self._make_trader()
        ctx = {
            "asset": {"symbol": "SOL"},
            "price": {"current": 150},
            "indicators": {},
            "anomalies": [],
            "existing_position": {"entry_price": 140, "unrealized_pnl_pct": 7.1},
            "timestamp": "now",
        }
        prompt = trader.build_user_prompt(ctx)
        assert "Open Position" in prompt
        assert "140" in prompt


# ---------------------------------------------------------------------------
# LLM integration test (mocked)
# ---------------------------------------------------------------------------

class TestDecideWithMockedLLM:
    @pytest.mark.asyncio
    async def test_decide_returns_decision(self):
        class TestTrader(BaseAITrader):
            def get_system_prompt(self):
                return "You are a test trader."
            def get_complexity(self):
                return TaskComplexity.SIMPLE

        trader = TestTrader(
            name="Test", slug="test",
            llm_provider="groq", llm_model="test-model",
        )

        mock_response = LLMResponse(
            content=json.dumps({
                "action": "buy",
                "confidence": 0.78,
                "reasoning": "RSI oversold, MACD bullish crossover",
                "position_size_pct": 0.12,
                "stop_loss_price": 60000,
                "take_profit_price": 75000,
            }),
            model="test-model",
            provider="groq",
            input_tokens=500,
            output_tokens=100,
        )

        with patch("app.ai_traders.base.routed_complete", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = mock_response

            ctx = {
                "asset": {"symbol": "BTC"},
                "price": {"current": 65000},
                "indicators": {"composite_score": 70},
                "anomalies": [],
                "timestamp": "now",
            }
            decision = await trader.decide(ctx)

        assert decision.action == TradeAction.BUY
        assert decision.confidence == 0.78
        assert decision.model_used == "test-model"
        assert "RSI" in decision.reasoning

    @pytest.mark.asyncio
    async def test_decide_handles_llm_error(self):
        class TestTrader(BaseAITrader):
            def get_system_prompt(self):
                return "Test"
            def get_complexity(self):
                return TaskComplexity.SIMPLE

        trader = TestTrader(
            name="Test", slug="test",
            llm_provider="groq", llm_model="test",
        )

        with patch("app.ai_traders.base.routed_complete", new_callable=AsyncMock) as mock_llm:
            mock_llm.side_effect = ConnectionError("API down")

            ctx = {
                "asset": {"symbol": "BTC"},
                "price": {"current": 65000},
                "indicators": {},
                "anomalies": [],
                "timestamp": "now",
            }
            decision = await trader.decide(ctx)

        assert decision.action == TradeAction.SKIP
        assert "failed" in decision.reasoning.lower()
