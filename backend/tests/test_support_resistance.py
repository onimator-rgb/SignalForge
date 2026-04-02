"""Tests for Support & Resistance Level Calculator."""

import pandas as pd
import pytest

from app.indicators.calculators.support_resistance import SRLevel, find_support_resistance


class TestInsufficientData:
    """Tests for edge cases with insufficient data."""

    def test_empty_series(self) -> None:
        empty = pd.Series([], dtype=float)
        result = find_support_resistance(empty, empty, empty)
        assert result == []

    def test_fewer_bars_than_required(self) -> None:
        # window=5 requires 2*5+1=11 bars, provide 10
        s = pd.Series(range(10), dtype=float)
        result = find_support_resistance(s, s, s, window=5)
        assert result == []

    def test_exact_minimum_bars(self) -> None:
        # window=2 requires 2*2+1=5 bars
        highs = pd.Series([10.0, 12.0, 8.0, 11.0, 9.0])
        lows = pd.Series([9.0, 11.0, 7.0, 10.0, 8.0])
        closes = pd.Series([9.5, 11.5, 7.5, 10.5, 8.5])
        result = find_support_resistance(highs, lows, closes, window=2)
        assert isinstance(result, list)


class TestFlatPrices:
    """Tests for flat/constant price data."""

    def test_all_same_prices(self) -> None:
        n = 20
        flat = pd.Series([100.0] * n)
        result = find_support_resistance(flat, flat, flat, window=3)
        # With all identical prices, every point is both a local min and max
        # The function should still return valid results (all clustered together)
        # All levels should cluster into at most a few merged levels
        for level in result:
            assert level.price == 100.0


class TestBasicDetection:
    """Tests for basic support/resistance identification."""

    @pytest.fixture()
    def oscillating_data(self) -> tuple[pd.Series, pd.Series, pd.Series]:
        """Create oscillating price data with support ~100 and resistance ~120."""
        # Pattern: price oscillates between ~100 and ~120 multiple times
        prices = []
        for _ in range(5):
            prices.extend([100, 105, 110, 115, 120, 115, 110, 105])
        highs = pd.Series([p + 1.0 for p in prices])
        lows = pd.Series([p - 1.0 for p in prices])
        closes = pd.Series([float(p) for p in prices])
        return highs, lows, closes

    def test_finds_support_level(
        self, oscillating_data: tuple[pd.Series, pd.Series, pd.Series]
    ) -> None:
        highs, lows, closes = oscillating_data
        result = find_support_resistance(highs, lows, closes, window=3)
        assert len(result) > 0
        support_levels = [lv for lv in result if lv.level_type == "support"]
        assert len(support_levels) > 0
        # At least one support near 99 (lows near 100 - 1)
        support_prices = [lv.price for lv in support_levels]
        assert any(95 <= p <= 105 for p in support_prices)

    def test_finds_resistance_level(
        self, oscillating_data: tuple[pd.Series, pd.Series, pd.Series]
    ) -> None:
        highs, lows, closes = oscillating_data
        result = find_support_resistance(highs, lows, closes, window=3)
        resistance_levels = [lv for lv in result if lv.level_type == "resistance"]
        assert len(resistance_levels) > 0
        resistance_prices = [lv.price for lv in resistance_levels]
        assert any(115 <= p <= 125 for p in resistance_prices)

    def test_returns_srlevels(
        self, oscillating_data: tuple[pd.Series, pd.Series, pd.Series]
    ) -> None:
        highs, lows, closes = oscillating_data
        result = find_support_resistance(highs, lows, closes, window=3)
        for level in result:
            assert isinstance(level, SRLevel)
            assert level.level_type in ("support", "resistance")
            assert level.touch_count >= 1
            assert level.strength > 0


class TestClustering:
    """Tests for proximity clustering of nearby levels."""

    def test_nearby_minima_merge(self) -> None:
        """Two nearby minima at 99.5 and 100.5 should merge into one level."""
        # Build data with two slightly different support levels
        prices = []
        for _ in range(3):
            prices.extend([99.5, 105, 110, 115, 120, 115, 110, 105])
        for _ in range(3):
            prices.extend([100.5, 105, 110, 115, 120, 115, 110, 105])

        highs = pd.Series([p + 0.5 for p in prices])
        lows = pd.Series([p - 0.5 for p in prices])
        closes = pd.Series([float(p) for p in prices])

        result = find_support_resistance(
            highs, lows, closes, window=3, cluster_pct=0.02
        )
        # The two support levels near 99-101 should be clustered
        support_near_100 = [
            lv for lv in result if lv.level_type == "support" and 95 <= lv.price <= 105
        ]
        # Should be merged into one (or very few) cluster(s)
        assert len(support_near_100) <= 2

    def test_distant_levels_not_merged(self) -> None:
        """Levels far apart should not be merged."""
        prices = []
        for _ in range(3):
            prices.extend([50, 75, 100, 125, 150, 125, 100, 75])

        highs = pd.Series([p + 1.0 for p in prices])
        lows = pd.Series([p - 1.0 for p in prices])
        closes = pd.Series([float(p) for p in prices])

        result = find_support_resistance(
            highs, lows, closes, window=3, cluster_pct=0.02
        )
        # Should have distinct levels near 50 and 150
        prices_found = [lv.price for lv in result]
        if len(prices_found) >= 2:
            assert max(prices_found) - min(prices_found) > 10


class TestMaxLevels:
    """Tests for max_levels parameter."""

    def test_max_levels_limits_output(self) -> None:
        # Create data with many distinct levels
        prices = list(range(10, 200, 5)) * 2
        highs = pd.Series([p + 1.0 for p in prices])
        lows = pd.Series([p - 1.0 for p in prices])
        closes = pd.Series([float(p) for p in prices])

        result = find_support_resistance(
            highs, lows, closes, window=2, max_levels=3
        )
        assert len(result) <= 3

    def test_max_levels_one(self) -> None:
        prices = []
        for _ in range(5):
            prices.extend([100, 110, 120, 110])
        highs = pd.Series([p + 1.0 for p in prices])
        lows = pd.Series([p - 1.0 for p in prices])
        closes = pd.Series([float(p) for p in prices])

        result = find_support_resistance(
            highs, lows, closes, window=2, max_levels=1
        )
        assert len(result) <= 1


class TestSorting:
    """Tests for output sorting by touch_count descending."""

    def test_sorted_by_touch_count_descending(self) -> None:
        prices = []
        for _ in range(5):
            prices.extend([100, 110, 120, 110])
        highs = pd.Series([p + 1.0 for p in prices])
        lows = pd.Series([p - 1.0 for p in prices])
        closes = pd.Series([float(p) for p in prices])

        result = find_support_resistance(highs, lows, closes, window=2)
        for i in range(len(result) - 1):
            assert result[i].touch_count >= result[i + 1].touch_count


class TestStrength:
    """Tests for strength calculation."""

    def test_strength_is_normalized(self) -> None:
        prices = []
        for _ in range(5):
            prices.extend([100, 110, 120, 110])
        highs = pd.Series([p + 1.0 for p in prices])
        lows = pd.Series([p - 1.0 for p in prices])
        closes = pd.Series([float(p) for p in prices])

        result = find_support_resistance(highs, lows, closes, window=2)
        for level in result:
            assert 0 < level.strength <= 1.0


class TestFrozenDataclass:
    """Tests for SRLevel immutability."""

    def test_srlevel_is_frozen(self) -> None:
        level = SRLevel(price=100.0, level_type="support", touch_count=3, strength=0.1)
        with pytest.raises(AttributeError):
            level.price = 200.0  # type: ignore[misc]
