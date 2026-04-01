"""Tests for market_circuit_breaker_guard pure function.

Covers edge cases: empty input, below/at/above threshold, exact boundary
drops, custom thresholds, and worst_drops ordering.
"""

import pytest

from app.portfolio.protections import (
    MARKET_CB_DROP_PCT,
    MARKET_CB_RULE,
    market_circuit_breaker_guard,
)


def _make_drops(
    dropping: int, total: int, drop_pct: float = -0.05, ok_pct: float = -0.01
) -> list[dict[str, object]]:
    """Helper: build an asset_drops list with *dropping* bad assets out of *total*."""
    return [
        {"asset_id": f"id-{i}", "symbol": f"DROP{i}", "drop_pct": drop_pct}
        for i in range(dropping)
    ] + [
        {"asset_id": f"id-{i}", "symbol": f"OK{i}", "drop_pct": ok_pct}
        for i in range(dropping, total)
    ]


# ── Basic cases ──────────────────────────────────────


def test_no_assets_returns_none() -> None:
    assert market_circuit_breaker_guard([]) is None


def test_below_threshold_returns_none() -> None:
    # 3/10 = 30 % dropping — below 60 % threshold
    drops = _make_drops(dropping=3, total=10)
    assert market_circuit_breaker_guard(drops) is None


def test_at_threshold_triggers() -> None:
    # 6/10 = 60 % — exactly at threshold
    drops = _make_drops(dropping=6, total=10)
    result = market_circuit_breaker_guard(drops)
    assert result is not None
    assert result["blocked"] is True
    assert result["rule"] == MARKET_CB_RULE
    assert result["dropping_count"] == 6
    assert result["total_count"] == 10


def test_above_threshold_triggers() -> None:
    # 8/10 = 80 %
    drops = _make_drops(dropping=8, total=10)
    result = market_circuit_breaker_guard(drops)
    assert result is not None
    assert result["dropping_count"] == 8
    assert result["total_count"] == 10


def test_exact_3pct_drop_triggers() -> None:
    """An asset at exactly -3.0 % should count as dropping (<=)."""
    drops = _make_drops(dropping=6, total=10, drop_pct=-0.03)
    result = market_circuit_breaker_guard(drops)
    assert result is not None
    assert result["dropping_count"] == 6


def test_small_drops_not_counted() -> None:
    """Assets dropping only 2.9 % must NOT count toward the breaker."""
    drops = _make_drops(dropping=10, total=10, drop_pct=-0.029)
    assert market_circuit_breaker_guard(drops) is None


def test_worst_drops_included() -> None:
    """worst_drops should list top-3 worst performers sorted ascending."""
    drops: list[dict[str, object]] = [
        {"asset_id": f"id-{i}", "symbol": f"SYM{i}", "drop_pct": -0.03 - i * 0.01}
        for i in range(8)
    ] + [
        {"asset_id": "id-ok", "symbol": "OK", "drop_pct": -0.005},
        {"asset_id": "id-ok2", "symbol": "OK2", "drop_pct": -0.002},
    ]
    result = market_circuit_breaker_guard(drops)
    assert result is not None
    worst = result["worst_drops"]
    assert isinstance(worst, list)
    assert len(worst) == 3
    # Worst first (most negative)
    pcts = [float(w["drop_pct"]) for w in worst]  # type: ignore[arg-type]
    assert pcts == sorted(pcts)  # ascending = most negative first


def test_custom_thresholds() -> None:
    """Override both threshold_drop_pct and threshold_asset_pct."""
    # 2/5 = 40 % — would not trigger at default 60 %, but triggers at 40 %
    drops = _make_drops(dropping=2, total=5, drop_pct=-0.02)
    result = market_circuit_breaker_guard(
        drops, threshold_drop_pct=-0.02, threshold_asset_pct=0.40
    )
    assert result is not None
    assert result["dropping_count"] == 2
    assert result["drop_pct_threshold"] == -0.02


def test_all_assets_dropping() -> None:
    """100 % of assets dropping should trigger."""
    drops = _make_drops(dropping=5, total=5)
    result = market_circuit_breaker_guard(drops)
    assert result is not None
    assert result["dropping_count"] == 5
    assert result["total_count"] == 5


def test_single_asset_not_enough() -> None:
    """1/10 = 10 % — far below threshold."""
    drops = _make_drops(dropping=1, total=10)
    assert market_circuit_breaker_guard(drops) is None


def test_drop_pct_threshold_in_result() -> None:
    """Result dict must include drop_pct_threshold."""
    drops = _make_drops(dropping=7, total=10)
    result = market_circuit_breaker_guard(drops)
    assert result is not None
    assert result["drop_pct_threshold"] == MARKET_CB_DROP_PCT
