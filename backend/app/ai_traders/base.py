"""Base AI Trader — abstract autonomous trader that makes buy/sell/hold decisions.

Each AI trader:
1. Receives market context (prices, indicators, anomalies, portfolio state)
2. Sends it to an LLM with its unique personality/strategy prompt
3. Parses the structured decision (action, confidence, reasoning, prices)
4. Returns a TradeDecision that the Arena can execute
"""

from __future__ import annotations

import json
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum

from app.llm.router import TaskComplexity, routed_complete
from app.logging_config import get_logger

log = get_logger(__name__)


class TradeAction(str, Enum):
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"
    SKIP = "skip"


@dataclass
class TradeDecision:
    """Structured output from an AI trader's analysis."""
    action: TradeAction
    confidence: float               # 0.0 - 1.0
    reasoning: str                  # LLM-generated explanation
    position_size_pct: float = 0.0  # % of portfolio to allocate
    target_entry_price: float | None = None
    stop_loss_price: float | None = None
    take_profit_price: float | None = None
    exit_pct: float = 1.0  # 0.25, 0.5, 0.75, or 1.0 (for SELL only)
    model_used: str = ""
    cost_usd: float = 0.0
    latency_ms: int = 0
    raw_response: str = ""


# The structured JSON format we ask the LLM to return
DECISION_FORMAT = """\
You MUST respond with ONLY a valid JSON object (no markdown, no explanation outside JSON):
{
  "action": "buy" | "sell" | "hold" | "skip",
  "confidence": 0.0 to 1.0,
  "reasoning": "2-4 sentences explaining your decision based on the data",
  "position_size_pct": 0.0 to 0.25 (fraction of portfolio, only for buy),
  "stop_loss_price": number or null,
  "take_profit_price": number or null,
  "exit_pct": 1.0  // fraction of position to close: 0.25, 0.5, 0.75, or 1.0 (sell only, default 1.0)
}
"""


class BaseAITrader(ABC):
    """Abstract base for all AI trader personalities."""

    def __init__(
        self,
        name: str,
        slug: str,
        llm_provider: str,
        llm_model: str,
        risk_params: dict | None = None,
    ):
        self.name = name
        self.slug = slug
        self.llm_provider = llm_provider
        self.llm_model = llm_model
        self.risk_params = risk_params or {}

    @abstractmethod
    def get_system_prompt(self) -> str:
        """Return the system prompt defining this trader's personality and strategy."""

    @abstractmethod
    def get_complexity(self) -> TaskComplexity:
        """Return the task complexity for LLM routing."""

    def build_user_prompt(self, asset_context: dict) -> str:
        """Build the user prompt from market context."""
        symbol = asset_context.get("asset", {}).get("symbol", "UNKNOWN")
        price_data = asset_context.get("price", {})
        indicators = asset_context.get("indicators", {})
        anomalies = asset_context.get("anomalies", [])
        existing_pos = asset_context.get("existing_position")
        portfolio = asset_context.get("portfolio", {})

        parts = [
            f"## Asset: {symbol}",
            f"Time: {asset_context.get('timestamp', 'N/A')}",
            "",
            "### Price Data",
            json.dumps(price_data, indent=2, default=str),
            "",
            "### Technical Indicators & Scoring",
            json.dumps(indicators, indent=2, default=str),
            "",
        ]

        if anomalies:
            parts.append("### Active Anomalies (last 48h)")
            parts.append(json.dumps(anomalies, indent=2, default=str))
            parts.append("")

        # Market regime
        regime = asset_context.get("market_regime")
        if regime:
            parts.append("### Market Regime")
            parts.append(f"Current: {regime.get('regime', 'unknown').upper()}")
            parts.append(f"BTC 7d: {regime.get('btc_7d_change_pct', 'N/A')}% | Avg Score: {regime.get('avg_composite_score', 'N/A')} | Volatility: {regime.get('volatility_index', 'N/A')}")
            parts.append("")

        # Consensus
        consensus = asset_context.get("consensus")
        if consensus and consensus.get("total_traders", 0) > 0:
            parts.append("### Trader Consensus (Previous Round)")
            parts.append(f"BUY: {consensus['buy']}/{consensus['total_traders']} | SELL: {consensus['sell']}/{consensus['total_traders']} | HOLD: {consensus['hold']}/{consensus['total_traders']}")
            if consensus.get("bullish_pct", 0) > 0.7:
                parts.append("Strong bullish consensus — high confidence but watch for crowded trades.")
            elif consensus.get("bullish_pct", 0) < 0.3:
                parts.append("Weak bullish consensus — most traders cautious.")
            parts.append("")

        news = asset_context.get("news", [])
        if news:
            parts.append("### Recent Verified News (last 24h)")
            for n in news[:3]:
                verified = " [VERIFIED]" if n.get("verified") else ""
                parts.append(f"- [{n.get('sentiment', 'neutral')}] {n.get('title', '')}{verified}")
                parts.append(f"  Source: {n.get('source', '')} | Reliability: {n.get('reliability', 0):.1f} | Sources: {n.get('sources_count', 1)}")
            parts.append("")

        if existing_pos:
            parts.append("### Your Current Open Position")
            parts.append(json.dumps(existing_pos, indent=2, default=str))
            parts.append("")

        if portfolio:
            parts.append("### Portfolio State")
            parts.append(json.dumps(portfolio, indent=2, default=str))
            parts.append("")

        # Trader memory
        memory = asset_context.get("trader_memory")
        if memory:
            stats = memory.get("overall_stats", {})
            parts.append("### Your Recent Performance")
            parts.append(f"Win Rate: {stats.get('win_rate', 'N/A')}% ({stats.get('wins', 0)}W / {stats.get('losses', 0)}L)")
            recent = memory.get("recent_trades", [])
            if recent:
                parts.append("Last closed trades:")
                for t in recent[:5]:
                    parts.append(f"  PnL: {t['realized_pnl_pct']}% | Exit: {t['close_reason']}")
            parts.append("")

        parts.append("### Your Task")
        parts.append("Analyze the data above and make a trading decision. Be decisive — if the data shows a clear opportunity, ACT on it with a buy or sell. Don't default to skip/hold when there are actionable signals.")
        parts.append("")
        parts.append("Example of a good BUY decision when RSI is oversold and price is at support:")
        parts.append('```json')
        parts.append('{')
        parts.append('  "action": "buy",')
        parts.append('  "confidence": 0.72,')
        parts.append('  "reasoning": "RSI at 28 indicates oversold conditions. Price touching lower Bollinger Band with volume spike suggests capitulation. MACD histogram turning positive. Entry at support with tight stop.",')
        parts.append('  "position_size_pct": 0.12,')
        parts.append('  "stop_loss_price": 142.50,')
        parts.append('  "take_profit_price": 158.00,')
        parts.append('  "exit_pct": 1.0')
        parts.append('}')
        parts.append('```')
        parts.append("")
        parts.append(DECISION_FORMAT)

        return "\n".join(parts)

    async def decide(self, asset_context: dict) -> TradeDecision:
        """Call LLM and parse the trading decision."""
        system_prompt = self.get_system_prompt()
        user_prompt = self.build_user_prompt(asset_context)

        start = time.monotonic()

        try:
            response = await routed_complete(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                complexity=self.get_complexity(),
                agent_name=f"trader_{self.slug}",
                task_type="trade_decision",
                temperature=0.2,  # Low temp for consistent decisions
                max_tokens=1000,
                preferred_provider=self.llm_provider,
                preferred_model=self.llm_model,
            )

            latency_ms = int((time.monotonic() - start) * 1000)
            decision = self._parse_decision(response.content)
            decision.model_used = response.model
            decision.cost_usd = 0.0  # tracked by router's cost_tracker
            decision.latency_ms = latency_ms
            decision.raw_response = response.content

            log.info(
                "ai_trader.decision",
                trader=self.slug,
                symbol=asset_context.get("asset", {}).get("symbol"),
                action=decision.action.value,
                confidence=decision.confidence,
                model=response.model,
                latency_ms=latency_ms,
            )

            return decision

        except Exception as exc:
            latency_ms = int((time.monotonic() - start) * 1000)
            log.error(
                "ai_trader.decision_failed",
                trader=self.slug,
                error=str(exc),
                latency_ms=latency_ms,
            )
            return TradeDecision(
                action=TradeAction.SKIP,
                confidence=0.0,
                reasoning=f"Decision failed: {exc}",
                latency_ms=latency_ms,
            )

    def _parse_decision(self, raw: str) -> TradeDecision:
        """Parse LLM response into a TradeDecision."""
        # Try to extract JSON from response
        text = raw.strip()

        # Handle markdown code blocks
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0].strip()
        elif "```" in text:
            text = text.split("```")[1].split("```")[0].strip()

        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            # Try to find JSON object in text
            start = text.find("{")
            end = text.rfind("}") + 1
            if start >= 0 and end > start:
                data = json.loads(text[start:end])
            else:
                return TradeDecision(
                    action=TradeAction.SKIP,
                    confidence=0.0,
                    reasoning=f"Failed to parse LLM response: {raw[:200]}",
                )

        action_str = data.get("action", "skip").lower()
        try:
            action = TradeAction(action_str)
        except ValueError:
            action = TradeAction.SKIP

        confidence = min(1.0, max(0.0, float(data.get("confidence", 0) or 0)))

        # Apply risk params limits
        max_pos = self.risk_params.get("max_position_pct", 0.20)
        raw_size = data.get("position_size_pct")
        position_size = min(max_pos, float(raw_size)) if raw_size is not None else 0.0

        # Safely parse optional price fields (LLM may return null or strings)
        def _safe_float(val):
            if val is None:
                return None
            try:
                return float(val)
            except (ValueError, TypeError):
                return None

        raw_exit = data.get("exit_pct", 1.0)
        try:
            exit_pct_val = float(raw_exit) if raw_exit else 1.0
        except (ValueError, TypeError):
            exit_pct_val = 1.0
        exit_pct_val = max(0.25, min(1.0, exit_pct_val))
        valid_steps = [0.25, 0.5, 0.75, 1.0]
        exit_pct_val = min(valid_steps, key=lambda x: abs(x - exit_pct_val))

        return TradeDecision(
            action=action,
            confidence=confidence,
            reasoning=data.get("reasoning", "No reasoning provided"),
            position_size_pct=position_size,
            target_entry_price=_safe_float(data.get("target_entry_price")),
            stop_loss_price=_safe_float(data.get("stop_loss_price")),
            take_profit_price=_safe_float(data.get("take_profit_price")),
            exit_pct=exit_pct_val,
        )
