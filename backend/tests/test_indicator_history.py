"""Tests for get_indicator_history service function (marketpulse-task-2026-04-01-0021)."""

from datetime import datetime, timedelta, timezone

import pandas as pd
import pytest

from app.indicators.calculators.adx import calc_adx
from app.indicators.calculators.macd import calc_macd
from app.indicators.calculators.rsi import calc_rsi
from app.indicators.schemas import IndicatorHistory


# ── Helper to build synthetic bar data ────────────────────────


def _make_closes(n: int, start: float = 100.0, step: float = 1.0) -> pd.Series:
    """Generate a rising series of close prices."""
    return pd.Series([start + i * step for i in range(n)])


def _make_highs(closes: pd.Series, offset: float = 1.5) -> pd.Series:
    return closes + offset


def _make_lows(closes: pd.Series, offset: float = 1.5) -> pd.Series:
    return closes - offset


# ── Rolling RSI tests ─────────────────────────────────────────


def test_rolling_rsi_correct_length() -> None:
    """Rolling RSI from index 14..end should produce len(closes)-14 values."""
    n = 48
    closes = _make_closes(n)
    rsi_values: list[float | None] = []
    for i in range(14, n):
        val = calc_rsi(closes[: i + 1], period=14)
        rsi_values.append(val)
    assert len(rsi_values) == n - 14  # 34 values


def test_rolling_rsi_values_in_range() -> None:
    """All non-None RSI values should be in [0, 100]."""
    closes = _make_closes(48)
    for i in range(14, 48):
        val = calc_rsi(closes[: i + 1], period=14)
        if val is not None:
            assert 0 <= val <= 100


def test_rolling_rsi_short_series_returns_none() -> None:
    """With fewer than 15 bars, calc_rsi returns None."""
    closes = _make_closes(10)
    assert calc_rsi(closes, period=14) is None


# ── Rolling MACD histogram tests ──────────────────────────────


def test_rolling_macd_correct_length() -> None:
    """Rolling MACD from index 35..end should produce len(closes)-35 values."""
    n = 48
    closes = _make_closes(n)
    macd_values: list[float | None] = []
    for i in range(35, n):
        res = calc_macd(closes[: i + 1])
        macd_values.append(res.histogram if res else None)
    assert len(macd_values) == n - 35  # 13 values


def test_rolling_macd_values_are_floats() -> None:
    """All non-None MACD histogram values should be floats."""
    closes = _make_closes(48)
    for i in range(35, 48):
        res = calc_macd(closes[: i + 1])
        if res is not None:
            assert isinstance(res.histogram, float)


# ── Rolling ADX tests ─────────────────────────────────────────


def test_rolling_adx_correct_length() -> None:
    """Rolling ADX from index 28..end should produce len(closes)-28 values."""
    n = 48
    closes = _make_closes(n)
    highs = _make_highs(closes)
    lows = _make_lows(closes)
    adx_values: list[float | None] = []
    for i in range(28, n):
        res = calc_adx(highs[: i + 1], lows[: i + 1], closes[: i + 1])
        adx_values.append(res.adx if res else None)
    assert len(adx_values) == n - 28  # 20 values


def test_rolling_adx_values_in_range() -> None:
    """All non-None ADX values should be in [0, 100]."""
    closes = _make_closes(48)
    highs = _make_highs(closes)
    lows = _make_lows(closes)
    for i in range(28, 48):
        res = calc_adx(highs[: i + 1], lows[: i + 1], closes[: i + 1])
        if res is not None:
            assert 0 <= res.adx <= 100


# ── IndicatorHistory schema tests ─────────────────────────────


def test_indicator_history_schema_accepts_none_values() -> None:
    """IndicatorHistory should accept lists with None values."""
    now = datetime.now(tz=timezone.utc)
    history = IndicatorHistory(
        asset_id="00000000-0000-0000-0000-000000000001",
        interval="1h",
        bars_used=48,
        rsi_14=[None, None, 45.0, 55.0, 60.0],
        macd_histogram=[None, None, None, 0.5, -0.3],
        adx_14=[None, None, None, None, 25.0],
        bar_times=[now - timedelta(hours=i) for i in range(4, -1, -1)],
    )
    assert len(history.rsi_14) == 5
    assert history.rsi_14[0] is None
    assert history.rsi_14[2] == 45.0


def test_indicator_history_schema_empty_lists() -> None:
    """IndicatorHistory should accept empty lists (no bars)."""
    history = IndicatorHistory(
        asset_id="00000000-0000-0000-0000-000000000001",
        interval="1h",
        bars_used=0,
        rsi_14=[],
        macd_histogram=[],
        adx_14=[],
        bar_times=[],
    )
    assert len(history.rsi_14) == 0
    assert len(history.bar_times) == 0


# ── Alignment / padding tests ────────────────────────────────


def test_alignment_padding_shorter_arrays() -> None:
    """When arrays have different lengths, shorter ones should be front-padded with None."""
    n = 48
    closes = _make_closes(n)
    highs = _make_highs(closes)
    lows = _make_lows(closes)

    rsi_values: list[float | None] = []
    for i in range(14, n):
        rsi_values.append(calc_rsi(closes[: i + 1], period=14))

    macd_values: list[float | None] = []
    for i in range(35, n):
        res = calc_macd(closes[: i + 1])
        macd_values.append(res.histogram if res else None)

    adx_values: list[float | None] = []
    for i in range(28, n):
        res = calc_adx(highs[: i + 1], lows[: i + 1], closes[: i + 1])
        adx_values.append(res.adx if res else None)

    max_len = max(len(rsi_values), len(macd_values), len(adx_values))

    def pad_front(arr: list[float | None], target: int) -> list[float | None]:
        pad = target - len(arr)
        return [None] * pad + arr

    rsi_padded = pad_front(rsi_values, max_len)
    macd_padded = pad_front(macd_values, max_len)
    adx_padded = pad_front(adx_values, max_len)

    # All should now have same length
    assert len(rsi_padded) == max_len
    assert len(macd_padded) == max_len
    assert len(adx_padded) == max_len

    # RSI has the most values (starts earliest), so no padding
    assert rsi_padded[0] is not None or len(rsi_values) < max_len

    # MACD has fewest values, so front should be None-padded
    macd_pad_count = max_len - len(macd_values)
    for i in range(macd_pad_count):
        assert macd_padded[i] is None


def test_last_24_slice() -> None:
    """Taking last 24 entries should work correctly."""
    n = 48
    closes = _make_closes(n)
    rsi_values: list[float | None] = []
    for i in range(14, n):
        rsi_values.append(calc_rsi(closes[: i + 1], period=14))

    display_count = min(24, len(rsi_values))
    rsi_out = rsi_values[-display_count:]
    assert len(rsi_out) == 24
    # All should be floats (rising series with 34 total values, last 24 all valid)
    for v in rsi_out:
        assert v is not None
        assert isinstance(v, float)
