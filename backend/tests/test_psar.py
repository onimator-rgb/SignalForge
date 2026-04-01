"""Tests for Parabolic SAR calculator."""

import pandas as pd

from app.indicators.calculators.psar import PSARResult, calc_psar


# ── calc_psar tests ─────────────────────────────────


def test_psar_insufficient_data_empty() -> None:
    """Returns None for empty series."""
    assert calc_psar(pd.Series([], dtype=float), pd.Series([], dtype=float)) is None


def test_psar_insufficient_data_one_bar() -> None:
    """Returns None for single bar."""
    assert calc_psar(pd.Series([100.0]), pd.Series([99.0])) is None


def test_psar_returns_result_for_two_bars() -> None:
    """Returns PSARResult with exactly 2 bars."""
    result = calc_psar(pd.Series([101.0, 102.0]), pd.Series([99.0, 100.0]))
    assert result is not None
    assert isinstance(result, PSARResult)
    assert result.trend in ("bullish", "bearish")


def test_psar_uptrend() -> None:
    """Clear uptrend should give bullish trend with SAR below last low."""
    n = 60
    highs = pd.Series([100.0 + i * 2.0 for i in range(n)])
    lows = pd.Series([98.0 + i * 2.0 for i in range(n)])

    result = calc_psar(highs, lows)
    assert result is not None
    assert result.trend == "bullish"
    # SAR should be below the last low in a strong uptrend
    assert result.sar < float(lows.iloc[-1]), (
        f"Expected SAR ({result.sar}) < last low ({lows.iloc[-1]}) in uptrend"
    )


def test_psar_downtrend() -> None:
    """Clear downtrend should give bearish trend with SAR above last high."""
    n = 60
    highs = pd.Series([200.0 - i * 2.0 for i in range(n)])
    lows = pd.Series([198.0 - i * 2.0 for i in range(n)])

    result = calc_psar(highs, lows)
    assert result is not None
    assert result.trend == "bearish"
    # SAR should be above the last high in a strong downtrend
    assert result.sar > float(highs.iloc[-1]), (
        f"Expected SAR ({result.sar}) > last high ({highs.iloc[-1]}) in downtrend"
    )


def test_psar_reversal() -> None:
    """Trend should reverse when price crosses SAR."""
    # Start with uptrend then sharply reverse
    n_up = 20
    n_down = 20
    highs_up = [100.0 + i * 2.0 for i in range(n_up)]
    lows_up = [98.0 + i * 2.0 for i in range(n_up)]

    # Sharp reversal: prices drop significantly
    last_high = highs_up[-1]
    highs_down = [last_high - i * 3.0 for i in range(1, n_down + 1)]
    lows_down = [last_high - 2.0 - i * 3.0 for i in range(1, n_down + 1)]

    highs = pd.Series(highs_up + highs_down)
    lows = pd.Series(lows_up + lows_down)

    result = calc_psar(highs, lows)
    assert result is not None
    # After the downtrend, should be bearish
    assert result.trend == "bearish"


def test_psar_af_capping() -> None:
    """AF should not exceed af_max."""
    # Long uptrend with many new highs to push AF to the cap
    n = 100
    highs = pd.Series([100.0 + i * 1.0 for i in range(n)])
    lows = pd.Series([99.0 + i * 1.0 for i in range(n)])

    result = calc_psar(highs, lows, af_start=0.02, af_increment=0.02, af_max=0.20)
    assert result is not None
    assert result.af <= 0.20, f"AF should be capped at 0.20, got {result.af}"
    # With 100 bars of continuous new highs, AF should reach the cap
    assert result.af == 0.20, f"AF should reach max 0.20 with many new highs, got {result.af}"


def test_psar_custom_af_params() -> None:
    """Custom AF parameters should be respected."""
    n = 60
    highs = pd.Series([100.0 + i * 2.0 for i in range(n)])
    lows = pd.Series([98.0 + i * 2.0 for i in range(n)])

    result = calc_psar(highs, lows, af_start=0.01, af_increment=0.01, af_max=0.10)
    assert result is not None
    assert result.af <= 0.10, f"AF should respect custom max 0.10, got {result.af}"


def test_psar_fields_present() -> None:
    """PSARResult has sar, trend, and af fields."""
    result = calc_psar(
        pd.Series([101.0, 102.0, 103.0]),
        pd.Series([99.0, 100.0, 101.0]),
    )
    assert result is not None
    assert hasattr(result, "sar")
    assert hasattr(result, "trend")
    assert hasattr(result, "af")
    assert isinstance(result.sar, float)
    assert isinstance(result.trend, str)
    assert isinstance(result.af, float)


def test_psar_registered_in_init() -> None:
    """calc_psar and PSARResult are exported from calculators __init__."""
    from app.indicators.calculators import PSARResult as PR
    from app.indicators.calculators import calc_psar as cp

    assert cp is calc_psar
    assert PR is PSARResult
