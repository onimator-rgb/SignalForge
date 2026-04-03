"""Intent detection — keyword matching + LLM fallback."""

from __future__ import annotations

import json
import re

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai_assistant.agents.base import ParsedIntent
from app.ai_assistant.prompts import INTENT_ROUTER_SYSTEM, INTENT_ROUTER_USER
from app.llm.router import TaskComplexity, routed_complete
from app.logging_config import get_logger

log = get_logger(__name__)

# ── Keyword maps ───────────────────────────────────────────────────
MARKET_KEYWORDS = {
    "price", "cena", "kurs", "analyze", "analiza", "analizuj",
    "trend", "rsi", "macd", "bollinger", "adx", "stochrsi",
    "vwap", "obv", "mfi", "fibonacci", "wsparcie", "opor",
    "support", "resistance", "volume", "wolumen", "anomalia",
    "anomaly", "rekomendacja", "recommendation", "prognoza",
    "co sadzisz", "jak wyglada", "sytuacja", "overview",
    "bull", "bear", "long", "short", "kupic", "sprzedac",
}

EDUCATION_KEYWORDS = {
    "co to jest", "what is", "czym jest", "jak dziala",
    "how does", "explain", "wytlumacz", "naucz", "teach",
    "definicja", "define", "roznica miedzy", "difference",
    "strategi", "strategy", "podstawy", "basics", "kurs",
    "lekcja", "lesson", "tutorial", "przyklad", "example",
    "dlaczego", "po co", "kiedy uzywac", "when to use",
}

# Common asset symbol aliases
SYMBOL_ALIASES: dict[str, str] = {
    "bitcoin": "BTC", "btc": "BTC",
    "ethereum": "ETH", "eth": "ETH", "ether": "ETH",
    "solana": "SOL", "sol": "SOL",
    "ripple": "XRP", "xrp": "XRP",
    "cardano": "ADA", "ada": "ADA",
    "dogecoin": "DOGE", "doge": "DOGE",
    "polkadot": "DOT", "dot": "DOT",
    "chainlink": "LINK", "link": "LINK",
    "apple": "AAPL", "aapl": "AAPL",
    "tesla": "TSLA", "tsla": "TSLA",
    "nvidia": "NVDA", "nvda": "NVDA",
    "microsoft": "MSFT", "msft": "MSFT",
    "amazon": "AMZN", "amzn": "AMZN",
    "google": "GOOGL", "googl": "GOOGL", "alphabet": "GOOGL",
    "meta": "META",
    "sp500": "SPY", "s&p": "SPY", "spy": "SPY",
    "gold": "GOLD", "zloto": "GOLD",
}

# Cache for DB symbols (populated on first call)
_db_symbols: set[str] | None = None


async def _load_db_symbols(db: AsyncSession) -> set[str]:
    """Load all asset symbols from DB (cached)."""
    global _db_symbols
    if _db_symbols is not None:
        return _db_symbols

    from app.assets.models import Asset
    result = await db.execute(select(Asset.symbol))
    _db_symbols = {row[0].upper() for row in result.all()}
    return _db_symbols


def _extract_symbols(message: str, known_symbols: set[str]) -> list[str]:
    """Extract asset symbols from message text."""
    symbols: list[str] = []
    msg_lower = message.lower()

    # Check aliases
    for alias, symbol in SYMBOL_ALIASES.items():
        if alias in msg_lower and symbol not in symbols:
            symbols.append(symbol)

    # Check for uppercase ticker patterns (e.g., BTC, AAPL)
    for word in re.findall(r"\b[A-Z]{2,6}\b", message):
        if word in known_symbols and word not in symbols:
            symbols.append(word)

    return symbols[:5]  # Cap at 5


def _keyword_score(message: str, keywords: set[str]) -> int:
    """Count keyword matches in message."""
    msg_lower = message.lower()
    return sum(1 for kw in keywords if kw in msg_lower)


async def detect_intent(message: str, db: AsyncSession) -> ParsedIntent:
    """Detect user intent — keyword matching first, LLM fallback for ambiguous cases."""
    known_symbols = await _load_db_symbols(db)
    symbols = _extract_symbols(message, known_symbols)

    market_score = _keyword_score(message, MARKET_KEYWORDS)
    education_score = _keyword_score(message, EDUCATION_KEYWORDS)

    # Clear winner — skip LLM
    if market_score > education_score and market_score >= 1:
        log.info("intent.keyword_match", agent="market_analyst", market=market_score, education=education_score)
        return ParsedIntent(
            agent_type="market_analyst",
            asset_symbols=symbols,
            topic="market analysis",
            raw_message=message,
            confidence=min(1.0, market_score / 3),
        )

    if education_score > market_score and education_score >= 1:
        log.info("intent.keyword_match", agent="education_coach", market=market_score, education=education_score)
        return ParsedIntent(
            agent_type="education_coach",
            asset_symbols=symbols,
            topic="education",
            raw_message=message,
            confidence=min(1.0, education_score / 3),
        )

    # Ambiguous — use LLM (TRIVIAL complexity, free models)
    try:
        llm_response = await routed_complete(
            system_prompt=INTENT_ROUTER_SYSTEM,
            user_prompt=INTENT_ROUTER_USER.format(message=message),
            complexity=TaskComplexity.TRIVIAL,
            agent_name="intent_router",
            task_type="intent_detection",
            temperature=0.1,
            max_tokens=200,
        )

        parsed = _parse_intent_json(llm_response.content)
        if parsed:
            log.info("intent.llm_detected", agent=parsed["agent"], model=llm_response.model)
            return ParsedIntent(
                agent_type=parsed.get("agent", "market_analyst"),
                asset_symbols=parsed.get("symbols", symbols),
                topic=parsed.get("topic", ""),
                raw_message=message,
                confidence=0.8,
            )
    except Exception as e:
        log.warning("intent.llm_fallback_error", error=str(e))

    # Default to market_analyst if symbols detected, else education
    default = "market_analyst" if symbols else "education_coach"
    log.info("intent.default", agent=default)
    return ParsedIntent(
        agent_type=default,
        asset_symbols=symbols,
        topic="",
        raw_message=message,
        confidence=0.5,
    )


def _parse_intent_json(text: str) -> dict | None:
    """Robustly parse JSON from LLM output."""
    # Try direct parse
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError:
        pass

    # Find JSON in text
    match = re.search(r"\{[^}]+\}", text)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass

    return None
