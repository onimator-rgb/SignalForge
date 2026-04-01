"""Tests for enhanced regime detection with ADX, price trend, and transition handling.

Task: marketpulse-task-2026-04-01-0011
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.strategy.profiles import PROFILES
from app.strategy.regime import _calc_price_trend_score, calculate_regime
from app.strategy.service import (
    _last_regime,
    apply_profile_to_open_positions,
    detect_regime_transition,
)

# ── Helpers ─────────────────────────────────────────────────


@dataclass
class FakeLivePrice:
    symbol: str
    asset_class: str
    price: float
    change_24h_pct: float | None
    source: str
    updated_at: datetime


def _make_cache(changes: list[float]) -> dict[str, FakeLivePrice]:
    """Build a fake live-price cache with given 24h change values."""
    cache: dict[str, FakeLivePrice] = {}
    for i, pct in enumerate(changes):
        sym = f"SYM{i}"
        cache[sym] = FakeLivePrice(
            symbol=sym,
            asset_class="crypto",
            price=100.0,
            change_24h_pct=pct,
            source="test",
            updated_at=datetime.utcnow(),
        )
    return cache


def _make_position(status: str = "open", exit_context: dict | None = None) -> MagicMock:
    """Create a mock PortfolioPosition."""
    pos = MagicMock()
    pos.id = uuid.uuid4()
    pos.status = status
    pos.exit_context = exit_context
    return pos


# ── TestADXRegimeScoring ───────────────────────────────────


class TestADXRegimeScoring:
    """Test ADX contribution to regime score."""

    @pytest.mark.asyncio
    @patch("app.strategy.regime._calc_avg_adx", new_callable=AsyncMock)
    @patch("app.strategy.regime.get_all_prices")
    async def test_high_adx_bullish_adds_points(
        self, mock_prices: MagicMock, mock_adx: AsyncMock,
    ) -> None:
        """avg_adx=35 + breadth_ratio > 0.55 → score includes +2 from ADX."""
        # 8 out of 10 positive → breadth_ratio = 0.8
        mock_prices.return_value = _make_cache([5.0] * 8 + [-1.0] * 2)
        mock_adx.return_value = 35.0

        db = AsyncMock()
        # avg_score=50, buy_signals=0, anomalies=0, active_assets=10
        db.execute = AsyncMock(side_effect=_db_side_effect(50, 0, 0, 10))

        result = await calculate_regime(db)
        assert result["inputs"]["avg_adx"] == 35.0
        # With breadth=0.8 (>0.55) and adx=35 (>30), ADX adds +2
        # Breadth 0.8>0.6 → +3, avg_score=50<52 → -2, buy=0 → -1,
        # anomaly=0 → 0, ADX → +2, price_trend → +1 (median=5.0>2)
        # Total = 3 - 2 - 1 + 2 + 1 = 3
        assert result["score"] >= 3

    @pytest.mark.asyncio
    @patch("app.strategy.regime._calc_avg_adx", new_callable=AsyncMock)
    @patch("app.strategy.regime.get_all_prices")
    async def test_high_adx_bearish_subtracts_points(
        self, mock_prices: MagicMock, mock_adx: AsyncMock,
    ) -> None:
        """avg_adx=35 + breadth_ratio < 0.40 → score includes -2 from ADX."""
        # 2 out of 10 positive → breadth_ratio = 0.2
        mock_prices.return_value = _make_cache([-3.0] * 8 + [1.0] * 2)
        mock_adx.return_value = 35.0

        db = AsyncMock()
        db.execute = AsyncMock(side_effect=_db_side_effect(50, 0, 0, 10))

        result = await calculate_regime(db)
        assert result["inputs"]["avg_adx"] == 35.0
        # breadth=0.2<0.35 → -3, avg=50 → -2, buy=0 → -1,
        # ADX → -2 (breadth<0.4), price_trend → -1 (median=-3<-2)
        # Total = -3 -2 -1 -2 -1 = -9
        assert result["score"] <= -3
        assert result["regime"] == "risk_off"

    @pytest.mark.asyncio
    @patch("app.strategy.regime._calc_avg_adx", new_callable=AsyncMock)
    @patch("app.strategy.regime.get_all_prices")
    async def test_low_adx_no_contribution(
        self, mock_prices: MagicMock, mock_adx: AsyncMock,
    ) -> None:
        """avg_adx=12 → no ADX score contribution."""
        mock_prices.return_value = _make_cache([5.0] * 8 + [-1.0] * 2)
        mock_adx.return_value = 12.0

        db = AsyncMock()
        db.execute = AsyncMock(side_effect=_db_side_effect(50, 0, 0, 10))

        result = await calculate_regime(db)
        assert result["inputs"]["avg_adx"] == 12.0
        # Same as bullish but WITHOUT the +2 ADX bonus
        # Breadth=0.8 → +3, avg=50 → -2, buy=0 → -1, ADX(12<15) → 0, trend → +1
        # Total = 3 -2 -1 +0 +1 = 1
        assert result["score"] == 1

    @pytest.mark.asyncio
    @patch("app.strategy.regime._calc_avg_adx", new_callable=AsyncMock)
    @patch("app.strategy.regime.get_all_prices")
    async def test_adx_unavailable_graceful(
        self, mock_prices: MagicMock, mock_adx: AsyncMock,
    ) -> None:
        """ADX calc raises exception → regime still calculates without ADX."""
        mock_prices.return_value = _make_cache([1.0] * 5 + [-1.0] * 5)
        mock_adx.side_effect = Exception("No price data")

        db = AsyncMock()
        db.execute = AsyncMock(side_effect=_db_side_effect(55, 3, 0, 10))

        result = await calculate_regime(db)
        assert result["inputs"]["avg_adx"] is None
        assert "regime" in result
        assert "score" in result


# ── TestPriceTrendScore ────────────────────────────────────


class TestPriceTrendScore:
    """Test _calc_price_trend_score helper."""

    def test_positive_trend(self) -> None:
        cache = _make_cache([3.0, 4.0, 5.0, 2.5, 3.5])
        assert _calc_price_trend_score(cache) == 1

    def test_negative_trend(self) -> None:
        cache = _make_cache([-3.0, -4.0, -5.0, -2.5, -3.5])
        assert _calc_price_trend_score(cache) == -1

    def test_neutral_trend(self) -> None:
        cache = _make_cache([1.0, -1.0, 0.5, -0.5, 0.0])
        assert _calc_price_trend_score(cache) == 0

    def test_empty_cache(self) -> None:
        assert _calc_price_trend_score({}) == 0

    def test_all_none_changes(self) -> None:
        cache = {"A": FakeLivePrice("A", "crypto", 100, None, "t", datetime.utcnow())}
        assert _calc_price_trend_score(cache) == 0


# ── TestRegimeTransition ──────────────────────────────────


class TestRegimeTransition:
    """Test detect_regime_transition state tracking."""

    def setup_method(self) -> None:
        """Reset module-level state before each test."""
        import app.strategy.service as svc
        svc._last_regime = None

    def test_first_call_no_transition(self) -> None:
        changed, prev = detect_regime_transition("neutral")
        assert changed is False
        assert prev is None

    def test_regime_change_detected(self) -> None:
        detect_regime_transition("neutral")  # set initial
        changed, prev = detect_regime_transition("risk_on")
        assert changed is True
        assert prev == "neutral"

    def test_same_regime_no_transition(self) -> None:
        detect_regime_transition("risk_on")
        changed, prev = detect_regime_transition("risk_on")
        assert changed is False
        assert prev is None

    def test_multiple_transitions(self) -> None:
        detect_regime_transition("neutral")

        changed1, prev1 = detect_regime_transition("risk_on")
        assert changed1 is True
        assert prev1 == "neutral"

        changed2, prev2 = detect_regime_transition("risk_on")
        assert changed2 is False
        assert prev2 is None

        changed3, prev3 = detect_regime_transition("risk_off")
        assert changed3 is True
        assert prev3 == "risk_on"


# ── TestApplyProfileToPositions ────────────────────────────


class TestApplyProfileToPositions:
    """Test apply_profile_to_open_positions."""

    @pytest.mark.asyncio
    async def test_updates_open_positions(self) -> None:
        """3 open positions → all get regime params in exit_context."""
        positions = [_make_position(exit_context={}) for _ in range(3)]
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = positions

        db = AsyncMock()
        db.execute = AsyncMock(return_value=mock_result)

        profile = PROFILES["aggressive"]
        count = await apply_profile_to_open_positions(db, profile)
        assert count == 3
        for pos in positions:
            ctx = pos.exit_context
            assert ctx["regime_stop_loss"] == profile.stop_loss_pct
            assert ctx["regime_take_profit"] == profile.take_profit_pct
            assert ctx["regime_trailing_pct"] == profile.trailing_pct
            assert ctx["regime_profile"] == "aggressive"
            assert "regime_switched_at" in ctx

    @pytest.mark.asyncio
    async def test_no_open_positions(self) -> None:
        """No open positions → returns 0."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []

        db = AsyncMock()
        db.execute = AsyncMock(return_value=mock_result)

        profile = PROFILES["conservative"]
        count = await apply_profile_to_open_positions(db, profile)
        assert count == 0

    @pytest.mark.asyncio
    async def test_preserves_existing_exit_context(self) -> None:
        """Existing keys in exit_context (DCA, scaling) are preserved."""
        existing = {"dca_step": 2, "scaling_factor": 1.5}
        pos = _make_position(exit_context=existing)
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [pos]

        db = AsyncMock()
        db.execute = AsyncMock(return_value=mock_result)

        profile = PROFILES["balanced"]
        count = await apply_profile_to_open_positions(db, profile)
        assert count == 1
        ctx = pos.exit_context
        # Original keys preserved
        assert ctx["dca_step"] == 2
        assert ctx["scaling_factor"] == 1.5
        # New regime keys added
        assert ctx["regime_stop_loss"] == profile.stop_loss_pct
        assert ctx["regime_profile"] == "balanced"

    @pytest.mark.asyncio
    async def test_handles_none_exit_context(self) -> None:
        """Position with exit_context=None gets a new dict."""
        pos = _make_position(exit_context=None)
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [pos]

        db = AsyncMock()
        db.execute = AsyncMock(return_value=mock_result)

        profile = PROFILES["aggressive"]
        count = await apply_profile_to_open_positions(db, profile)
        assert count == 1
        assert pos.exit_context["regime_profile"] == "aggressive"


# ── DB mock helper ─────────────────────────────────────────


def _db_side_effect(
    avg_score: float, buy_signals: int, anomalies: int, active_assets: int,
):
    """Return a side_effect callable for db.execute that mimics the 4 regime queries."""
    call_count = 0

    async def _execute(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        mock = MagicMock()
        if call_count == 1:
            mock.scalar_one.return_value = avg_score  # avg recommendation score
        elif call_count == 2:
            mock.scalar_one.return_value = buy_signals  # buy signal count
        elif call_count == 3:
            mock.scalar_one.return_value = anomalies  # unresolved anomalies
        elif call_count == 4:
            mock.scalar_one.return_value = active_assets  # active assets
        return mock

    return _execute
