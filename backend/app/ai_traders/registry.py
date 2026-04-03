"""AI Trader registry — manages all available trader personalities."""

from __future__ import annotations

from app.ai_traders.base import BaseAITrader
from app.ai_traders.personalities.conservative_quant import ConservativeQuant
from app.ai_traders.personalities.momentum_hunter import MomentumHunter
from app.ai_traders.personalities.mean_reversion import MeanReversionTrader
from app.ai_traders.personalities.sentiment_contrarian import SentimentContrarian
from app.ai_traders.personalities.balanced_hybrid import BalancedHybrid
from app.ai_traders.personalities.scalper_quant import ScalperQuant
from app.ai_traders.personalities.whale_follower import WhaleFollower
from app.ai_traders.personalities.fibonacci_trader import FibonacciTrader
from app.ai_traders.personalities.news_sentiment import NewsSentimentTrader


def get_all_traders() -> list[BaseAITrader]:
    """Return instances of all available AI traders."""
    return [
        ConservativeQuant(),
        MomentumHunter(),
        MeanReversionTrader(),
        SentimentContrarian(),
        BalancedHybrid(),
        ScalperQuant(),
        WhaleFollower(),
        FibonacciTrader(),
        NewsSentimentTrader(),
    ]


def get_trader_by_slug(slug: str) -> BaseAITrader | None:
    """Find a trader by its slug."""
    for trader in get_all_traders():
        if trader.slug == slug:
            return trader
    return None


TRADER_DESCRIPTIONS = {
    "conservative_quant": {
        "name": "Conservative Quant",
        "strategy": "Risk-averse, data-driven, small positions, tight stops",
        "model": "Gemini Flash",
        "style": "Quantitative / Risk Manager",
        "cost": "cheap",
    },
    "momentum_hunter": {
        "name": "Momentum Hunter",
        "strategy": "Trend-following, breakout-hunting, rides momentum waves",
        "model": "Groq Llama 3.3",
        "style": "Aggressive / Trend Follower",
        "cost": "cheap",
    },
    "mean_reversion": {
        "name": "Mean Reversion",
        "strategy": "Buys oversold dips, sells overbought rallies, contrarian",
        "model": "Mistral Small",
        "style": "Contrarian / Value",
        "cost": "cheap",
    },
    "sentiment_contrarian": {
        "name": "Sentiment Contrarian",
        "strategy": "Trades against crowd emotions, anomaly-driven entries",
        "model": "Gemini Flash Lite",
        "style": "Behavioral / Anti-Crowd",
        "cost": "ultra-cheap",
    },
    "balanced_hybrid": {
        "name": "Balanced Hybrid",
        "strategy": "Adapts to market regime — momentum/reversion/defensive",
        "model": "Gemini Flash",
        "style": "Adaptive / Multi-Strategy",
        "cost": "cheap",
    },
    "scalper_quant": {
        "name": "Scalper Quant",
        "strategy": "High-frequency small gains, tight risk, quick in/out",
        "model": "OpenRouter Gemini Free",
        "style": "Scalping / High-Frequency",
        "cost": "free",
    },
    "whale_follower": {
        "name": "Whale Follower",
        "strategy": "Follows smart money via volume spikes, institutional flow",
        "model": "OpenRouter Llama Free",
        "style": "Volume Analysis / Smart Money",
        "cost": "free",
    },
    "fibonacci_trader": {
        "name": "Fibonacci Trader",
        "strategy": "Trades Fibonacci support/resistance levels with confirmation",
        "model": "OpenRouter Mistral Free",
        "style": "Technical / Level Trading",
        "cost": "free",
    },
    "news_sentiment": {
        "name": "News Sentiment",
        "strategy": "Trades exclusively on verified cross-source news signals",
        "model": "Cerebras Llama 3.3",
        "style": "News-Driven / Event Trading",
        "cost": "free",
    },
}
