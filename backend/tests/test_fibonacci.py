"""Tests for Fibonacci retracement levels calculator."""

import pandas as pd
import pytest

from app.indicators.calculators.fibonacci import FibonacciResult, calc_fibonacci


# ── Insufficient data ────────────────────────────────


def test_fibonacci_insufficient_data() -> None:
    """Returns None when fewer than lookback bars provided."""
    n = 10  # Less than default lookback of 20
    highs = pd.Series([100.0 + i for i in range(n)])
    lows = pd.Series([99.0 + i for i in range(n)])
    closes = pd.Series([99.5 + i for i in range(n)])
    assert calc_fibonacci(highs, lows, closes, lookback=20) is None


def test_fibonacci_exact_lookback() -> None:
    """Works when exactly lookback bars are provided."""
    n = 20
    highs = pd.Series([100.0 + i for i in range(n)])
    lows = pd.Series([98.0 + i for i in range(n)])
    closes = pd.Series([99.0 + i for i in range(n)])
    result = calc_fibonacci(highs, lows, closes, lookback=20)
    assert result is not None


# ── Flat market ───────────────────────────────────────


def test_fibonacci_flat_market() -> None:
    """Returns None when swing_high equals swing_low."""
    n = 20
    highs = pd.Series([100.0] * n)
    lows = pd.Series([100.0] * n)
    closes = pd.Series([100.0] * n)
    assert calc_fibonacci(highs, lows, closes, lookback=20) is None


# ── Known uptrend ─────────────────────────────────────


def test_fibonacci_uptrend_values() -> None:
    """Verify correct Fibonacci ratios for known uptrend data."""
    n = 20
    # Uptrend: lows rise then highs rise — swing_low at start, swing_high at end
    lows = pd.Series([90.0] + [95.0 + i * 0.1 for i in range(n - 1)])
    highs = pd.Series([95.0 + i * 0.1 for i in range(n - 1)] + [110.0])
    closes = pd.Series([92.0 + i for i in range(n)])

    result = calc_fibonacci(highs, lows, closes, lookback=20)
    assert result is not None

    # swing_low = 90.0, swing_high = 110.0, diff = 20.0
    assert result.swing_low == 90.0
    assert result.swing_high == 110.0
    assert result.level_0 == 90.0  # 0% = swing_low
    assert result.level_236 == pytest.approx(90.0 + 0.236 * 20.0, abs=0.01)
    assert result.level_382 == pytest.approx(90.0 + 0.382 * 20.0, abs=0.01)
    assert result.level_500 == pytest.approx(100.0, abs=0.01)
    assert result.level_618 == pytest.approx(90.0 + 0.618 * 20.0, abs=0.01)
    assert result.level_786 == pytest.approx(90.0 + 0.786 * 20.0, abs=0.01)
    assert result.level_100 == 110.0  # 100% = swing_high
    assert result.trend == "up"


# ── Known downtrend ───────────────────────────────────


def test_fibonacci_downtrend_values() -> None:
    """Verify correct Fibonacci ratios for known downtrend data."""
    n = 20
    # Downtrend: swing_high at start, swing_low at end
    highs = pd.Series([110.0] + [105.0 - i * 0.1 for i in range(n - 1)])
    lows = pd.Series([105.0 - i * 0.1 for i in range(n - 1)] + [90.0])
    closes = pd.Series([108.0 - i for i in range(n)])

    result = calc_fibonacci(highs, lows, closes, lookback=20)
    assert result is not None

    assert result.swing_low == 90.0
    assert result.swing_high == 110.0
    assert result.level_0 == 90.0
    assert result.level_100 == 110.0
    assert result.trend == "down"


# ── Level invariants ──────────────────────────────────


def test_fibonacci_level_0_equals_swing_low() -> None:
    """level_0 always equals swing_low."""
    n = 30
    highs = pd.Series([100.0 + i * 1.5 for i in range(n)])
    lows = pd.Series([98.0 + i * 1.5 for i in range(n)])
    closes = pd.Series([99.0 + i * 1.5 for i in range(n)])

    result = calc_fibonacci(highs, lows, closes, lookback=20)
    assert result is not None
    assert result.level_0 == result.swing_low


def test_fibonacci_level_100_equals_swing_high() -> None:
    """level_100 always equals swing_high."""
    n = 30
    highs = pd.Series([100.0 + i * 1.5 for i in range(n)])
    lows = pd.Series([98.0 + i * 1.5 for i in range(n)])
    closes = pd.Series([99.0 + i * 1.5 for i in range(n)])

    result = calc_fibonacci(highs, lows, closes, lookback=20)
    assert result is not None
    assert result.level_100 == result.swing_high


# ── Trend detection ───────────────────────────────────


def test_fibonacci_trend_up_when_low_before_high() -> None:
    """trend is 'up' when swing_low occurs before swing_high."""
    n = 20
    # Low at index 0, high at index 19
    lows = pd.Series([80.0] + [95.0] * (n - 1))
    highs = pd.Series([95.0] * (n - 1) + [120.0])
    closes = pd.Series([90.0 + i for i in range(n)])

    result = calc_fibonacci(highs, lows, closes, lookback=20)
    assert result is not None
    assert result.trend == "up"


def test_fibonacci_trend_down_when_high_before_low() -> None:
    """trend is 'down' when swing_high occurs before swing_low."""
    n = 20
    # High at index 0, low at index 19
    highs = pd.Series([120.0] + [95.0] * (n - 1))
    lows = pd.Series([95.0] * (n - 1) + [80.0])
    closes = pd.Series([110.0 - i for i in range(n)])

    result = calc_fibonacci(highs, lows, closes, lookback=20)
    assert result is not None
    assert result.trend == "down"


# ── Rounding ──────────────────────────────────────────


def test_fibonacci_levels_rounded_to_2_decimals() -> None:
    """All levels are rounded to 2 decimal places."""
    n = 20
    # Use values that produce non-round Fibonacci levels
    lows = pd.Series([100.0] + [102.0] * (n - 1))
    highs = pd.Series([102.0] * (n - 1) + [107.0])
    closes = pd.Series([101.0 + i * 0.3 for i in range(n)])

    result = calc_fibonacci(highs, lows, closes, lookback=20)
    assert result is not None

    for field in [
        "swing_high", "swing_low",
        "level_0", "level_236", "level_382", "level_500",
        "level_618", "level_786", "level_100",
    ]:
        val = getattr(result, field)
        assert val == round(val, 2), f"{field}={val} not rounded to 2 decimals"
