"""Pre-filter — rule-based gate BEFORE calling LLM.

Eliminates obvious non-trades without spending tokens.
Each trader personality has different filter criteria.
This saves ~60-80% of LLM calls (and cost).

Flow:
  Asset context → Pre-filter → PASS → LLM decision
                             → SKIP → No LLM call, log skip reason
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class FilterResult:
    should_analyze: bool
    skip_reason: str = ""


def pre_filter_conservative(ctx: dict) -> FilterResult:
    """Conservative Quant: only analyze strong signals."""
    indicators = ctx.get("indicators", {})
    price = ctx.get("price", {})
    anomalies = ctx.get("anomalies", [])

    # Skip if no recent data
    if not price.get("current"):
        return FilterResult(False, "no_price_data")

    # If already holding — always allow analysis (for potential exit decision)
    if ctx.get("existing_position"):
        return FilterResult(True)

    # Skip if HIGH/CRITICAL anomalies active (too risky for new entry)
    high_anomalies = [a for a in anomalies if a.get("severity") in ("high", "critical")]
    if high_anomalies:
        return FilterResult(False, f"high_anomaly_active:{len(high_anomalies)}")

    # Skip if composite score below minimum
    score = indicators.get("composite_score")
    if score is not None and score < 55:
        return FilterResult(False, f"score_too_low:{score}")

    # Skip if recommendation is SELL (not BUY opportunity)
    rec_type = indicators.get("recommendation_type", "").upper()
    if rec_type == "SELL":
        return FilterResult(False, "recommendation_is_sell")

    return FilterResult(True)


def pre_filter_momentum(ctx: dict) -> FilterResult:
    """Momentum Hunter: only analyze trending assets."""
    price = ctx.get("price", {})
    indicators = ctx.get("indicators", {})

    if not price.get("current"):
        return FilterResult(False, "no_price_data")

    # Skip if no momentum (flat 24h change)
    change = price.get("change_24h_pct")
    if change is not None and abs(change) < 1.5:
        return FilterResult(False, f"no_momentum:change={change}")

    # Skip if existing position (hold decisions don't need LLM)
    if ctx.get("existing_position"):
        pos = ctx["existing_position"]
        pnl = pos.get("unrealized_pnl_pct", 0)
        # Only re-analyze if significant move
        if abs(pnl) < 5:
            return FilterResult(False, f"position_stable:pnl={pnl}")

    return FilterResult(True)


def pre_filter_mean_reversion(ctx: dict) -> FilterResult:
    """Mean Reversion: only analyze extreme conditions."""
    indicators = ctx.get("indicators", {})
    price = ctx.get("price", {})

    if not price.get("current"):
        return FilterResult(False, "no_price_data")

    # Check for RSI extremes from signal breakdown
    breakdown = indicators.get("signal_breakdown", {})
    rsi_data = breakdown.get("rsi", {})

    # If we have score info, only analyze extremes
    score = indicators.get("composite_score")
    rec_type = indicators.get("recommendation_type", "").upper()

    # Mean reversion wants oversold (for buy) or overbought (for sell)
    # Skip neutral/trending conditions
    if score is not None and 40 < score < 70 and rec_type == "HOLD":
        return FilterResult(False, f"neutral_zone:score={score}")

    # If holding, check if it's worth analyzing for exit
    if ctx.get("existing_position"):
        return FilterResult(True)

    return FilterResult(True)


def pre_filter_sentiment(ctx: dict) -> FilterResult:
    """Sentiment Contrarian: only analyze when anomalies present."""
    anomalies = ctx.get("anomalies", [])
    price = ctx.get("price", {})

    if not price.get("current"):
        return FilterResult(False, "no_price_data")

    # This trader's ENTIRE edge comes from anomalies
    # No anomalies = no edge = skip
    if not anomalies and not ctx.get("existing_position"):
        return FilterResult(False, "no_anomalies_no_edge")

    # If holding, always check (need to monitor for exit signals)
    if ctx.get("existing_position"):
        return FilterResult(True)

    return FilterResult(True)


def pre_filter_balanced(ctx: dict) -> FilterResult:
    """Balanced Hybrid: moderate filter, skip obvious no-trades."""
    price = ctx.get("price", {})
    indicators = ctx.get("indicators", {})

    if not price.get("current"):
        return FilterResult(False, "no_price_data")

    # Skip if composite score very low (clear avoid)
    score = indicators.get("composite_score")
    if score is not None and score < 35 and not ctx.get("existing_position"):
        return FilterResult(False, f"score_very_low:{score}")

    return FilterResult(True)


def pre_filter_scalper(ctx: dict) -> FilterResult:
    """Scalper Quant: only analyze liquid, moving assets."""
    price = ctx.get("price", {})
    anomalies = ctx.get("anomalies", [])

    if not price.get("current"):
        return FilterResult(False, "no_price_data")

    # Scalpers avoid anomalies (too unpredictable)
    if anomalies:
        return FilterResult(False, "anomalies_active")

    # Need volume data to assess liquidity
    volume = price.get("volume_24h", 0)
    if volume == 0:
        return FilterResult(False, "no_volume_data")

    # Check existing position for time-based exit
    if ctx.get("existing_position"):
        return FilterResult(True)

    return FilterResult(True)


def pre_filter_whale(ctx: dict) -> FilterResult:
    """Whale Follower: only analyze when volume anomaly present."""
    anomalies = ctx.get("anomalies", [])
    price = ctx.get("price", {})

    if not price.get("current"):
        return FilterResult(False, "no_price_data")

    # This trader NEEDS volume anomalies — that's the entire signal
    volume_anomalies = [a for a in anomalies if a.get("type") in ("volume_surge", "volume_spike")]

    if not volume_anomalies and not ctx.get("existing_position"):
        return FilterResult(False, "no_volume_anomaly")

    if ctx.get("existing_position"):
        return FilterResult(True)

    return FilterResult(True)


def pre_filter_fibonacci(ctx: dict) -> FilterResult:
    """Fibonacci Trader: need price range data for level calculation."""
    price = ctx.get("price", {})

    if not price.get("current"):
        return FilterResult(False, "no_price_data")

    # Need 7-day price data to calculate Fibonacci levels
    daily_closes = price.get("daily_closes_7d", [])
    if len(daily_closes) < 3:
        return FilterResult(False, "insufficient_price_history")

    if ctx.get("existing_position"):
        return FilterResult(True)

    return FilterResult(True)


# Registry mapping slug → filter function
PRE_FILTERS = {
    "conservative_quant": pre_filter_conservative,
    "momentum_hunter": pre_filter_momentum,
    "mean_reversion": pre_filter_mean_reversion,
    "sentiment_contrarian": pre_filter_sentiment,
    "balanced_hybrid": pre_filter_balanced,
    "scalper_quant": pre_filter_scalper,
    "whale_follower": pre_filter_whale,
    "fibonacci_trader": pre_filter_fibonacci,
    "news_sentiment": lambda ctx: (
        FilterResult(True) if ctx.get("existing_position") or ctx.get("news")
        else FilterResult(False, "no_news_no_edge")
    ),
}


def apply_pre_filter(trader_slug: str, ctx: dict) -> FilterResult:
    """Apply the appropriate pre-filter for a trader."""
    fn = PRE_FILTERS.get(trader_slug)
    if fn is None:
        return FilterResult(True)  # No filter = always analyze
    return fn(ctx)
