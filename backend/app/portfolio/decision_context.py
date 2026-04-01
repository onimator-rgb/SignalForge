"""Pure functions for building rich signal snapshots on entry/exit decisions.

Snapshots capture the full indicator + signal state at decision time,
stored in EntryDecision.context_data and PortfolioPosition.exit_context.
"""

from __future__ import annotations

from typing import Any

from app.indicators.schemas import IndicatorSnapshot


def build_entry_snapshot(
    indicators: IndicatorSnapshot | None,
    signals: list[Any] | None,
    composite_score: float | None,
    recommendation_type: str | None,
    confidence: str | None,
    risk_level: str | None,
    regime: str | None,
    profile_name: str | None,
    change_24h_pct: float | None,
    avg_volume: float | None,
    latest_volume: float | None,
) -> dict[str, Any]:
    """Build a serializable snapshot of all indicator/signal state at entry time.

    All parameters are optional-safe: None inputs produce None values in output.
    """
    # Extract indicator values
    rsi = None
    macd = None
    bollinger = None
    adx = None
    stoch_rsi = None

    if indicators is not None:
        rsi = indicators.rsi_14
        if indicators.macd is not None:
            macd = {
                "line": indicators.macd.macd,
                "signal": indicators.macd.signal,
                "histogram": indicators.macd.histogram,
            }
        if indicators.bollinger is not None:
            bollinger = {
                "upper": indicators.bollinger.upper,
                "middle": indicators.bollinger.middle,
                "lower": indicators.bollinger.lower,
                "bandwidth": indicators.bollinger.width,
            }
        adx = indicators.adx_14
        if indicators.stoch_rsi_k is not None or indicators.stoch_rsi_d is not None:
            stoch_rsi = {
                "k": indicators.stoch_rsi_k,
                "d": indicators.stoch_rsi_d,
            }

    # Build signals list
    signals_list: list[dict[str, Any]] = []
    if signals:
        for s in signals:
            signals_list.append({
                "name": s.name,
                "score": s.score,
                "weight": s.weight,
                "detail": s.detail,
            })

    # Compute volume ratio
    volume_ratio: float | None = None
    if latest_volume is not None and avg_volume is not None and avg_volume > 0:
        volume_ratio = latest_volume / avg_volume

    return {
        "rsi": rsi,
        "macd": macd,
        "bollinger": bollinger,
        "adx": adx,
        "stoch_rsi": stoch_rsi,
        "signals": signals_list,
        "composite_score": composite_score,
        "recommendation_type": recommendation_type,
        "confidence": confidence,
        "risk_level": risk_level,
        "regime": regime,
        "profile": profile_name,
        "change_24h_pct": change_24h_pct,
        "volume_ratio": volume_ratio,
        "snapshot_version": "v1",
    }


def build_exit_snapshot(
    indicators: IndicatorSnapshot | None,
    rec_score: float | None,
    rec_type: str | None,
    close_reason: str | None,
    pnl_pct: float | None,
    regime: str | None,
) -> dict[str, Any]:
    """Build a serializable snapshot of indicator/signal state at exit time."""
    rsi = None
    macd = None
    bollinger = None
    adx = None
    stoch_rsi = None

    if indicators is not None:
        rsi = indicators.rsi_14
        if indicators.macd is not None:
            macd = {
                "line": indicators.macd.macd,
                "signal": indicators.macd.signal,
                "histogram": indicators.macd.histogram,
            }
        if indicators.bollinger is not None:
            bollinger = {
                "upper": indicators.bollinger.upper,
                "middle": indicators.bollinger.middle,
                "lower": indicators.bollinger.lower,
                "bandwidth": indicators.bollinger.width,
            }
        adx = indicators.adx_14
        if indicators.stoch_rsi_k is not None or indicators.stoch_rsi_d is not None:
            stoch_rsi = {
                "k": indicators.stoch_rsi_k,
                "d": indicators.stoch_rsi_d,
            }

    return {
        "rsi": rsi,
        "macd": macd,
        "bollinger": bollinger,
        "adx": adx,
        "stoch_rsi": stoch_rsi,
        "rec_score": rec_score,
        "rec_type": rec_type,
        "close_reason": close_reason,
        "pnl_pct": pnl_pct,
        "regime": regime,
        "snapshot_version": "v1",
    }
