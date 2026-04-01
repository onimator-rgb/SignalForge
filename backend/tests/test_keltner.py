"""Unit tests for Keltner Channels calculator."""

import numpy as np
import pandas as pd
import pytest

from app.indicators.calculators.squeeze import KeltnerResult, calc_keltner


class TestKeltnerInsufficientData:
    def test_keltner_insufficient_data(self) -> None:
        """Series shorter than max(ema_period, atr_period) + 1 = 21 returns None."""
        short = pd.Series([100.0] * 20)
        result = calc_keltner(short, short, short, ema_period=20, atr_period=10, atr_mult=1.5)
        assert result is None


class TestKeltnerValidInput:
    @pytest.fixture()
    def synthetic_data(self) -> tuple[pd.Series, pd.Series, pd.Series]:
        rng = np.random.default_rng(42)
        base = 100.0 + np.cumsum(rng.normal(0, 1, 40))
        closes = pd.Series(base)
        highs = pd.Series(base + rng.uniform(0.5, 2.0, 40))
        lows = pd.Series(base - rng.uniform(0.5, 2.0, 40))
        return closes, highs, lows

    def test_keltner_returns_result_for_valid_input(
        self, synthetic_data: tuple[pd.Series, pd.Series, pd.Series]
    ) -> None:
        closes, highs, lows = synthetic_data
        result = calc_keltner(closes, highs, lows)
        assert result is not None
        assert isinstance(result, KeltnerResult)
        assert result.upper > result.middle > result.lower

    def test_keltner_upper_greater_than_lower(
        self, synthetic_data: tuple[pd.Series, pd.Series, pd.Series]
    ) -> None:
        closes, highs, lows = synthetic_data
        result = calc_keltner(closes, highs, lows)
        assert result is not None
        assert result.upper > result.lower


class TestKeltnerChannelProperties:
    def test_keltner_channel_widens_with_volatility(self) -> None:
        n = 40
        flat_closes = pd.Series([100.0] * n)
        flat_highs = pd.Series([100.5] * n)
        flat_lows = pd.Series([99.5] * n)

        rng = np.random.default_rng(123)
        base = 100.0 + np.cumsum(rng.normal(0, 3, n))
        vol_closes = pd.Series(base)
        vol_highs = pd.Series(base + rng.uniform(2.0, 6.0, n))
        vol_lows = pd.Series(base - rng.uniform(2.0, 6.0, n))

        flat_res = calc_keltner(flat_closes, flat_highs, flat_lows)
        vol_res = calc_keltner(vol_closes, vol_highs, vol_lows)

        assert flat_res is not None
        assert vol_res is not None

        flat_width = flat_res.upper - flat_res.lower
        vol_width = vol_res.upper - vol_res.lower
        assert vol_width > flat_width

    def test_keltner_middle_near_ema(self) -> None:
        n = 40
        price = 50.0
        closes = pd.Series([price] * n)
        highs = pd.Series([price] * n)
        lows = pd.Series([price] * n)

        result = calc_keltner(closes, highs, lows)
        assert result is not None
        assert result.middle == pytest.approx(price, abs=0.01)


class TestKeltnerExports:
    def test_keltner_exported_from_init(self) -> None:
        from app.indicators.calculators import KeltnerResult as KR
        from app.indicators.calculators import calc_keltner as ck

        assert KR is KeltnerResult
        assert ck is calc_keltner
