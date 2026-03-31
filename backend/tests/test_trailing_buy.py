"""Tests for trailing buy entry mechanism."""

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.portfolio.trailing_buy import start_trailing, update_trailing
from app.strategy.profiles import PROFILES


# ── Pure function tests (s1) ──────────────────────


class TestStartTrailing:
    def test_returns_valid_context(self) -> None:
        now = datetime(2026, 4, 1, 12, 0, tzinfo=timezone.utc)
        ctx = start_trailing(signal_price=100.0, bounce_pct=0.02, max_hours=12, now=now)

        assert ctx["signal_price"] == 100.0
        assert ctx["lowest_price"] == 100.0
        assert ctx["bounce_pct"] == 0.02
        assert ctx["status"] == "trailing"
        assert ctx["started_at"] == now.isoformat()
        expected_expires = (now + timedelta(hours=12)).isoformat()
        assert ctx["expires_at"] == expected_expires


class TestUpdateTrailing:
    def _make_ctx(
        self,
        signal_price: float = 100.0,
        lowest_price: float = 100.0,
        bounce_pct: float = 0.02,
        hours_left: int = 12,
    ) -> dict:
        now = datetime(2026, 4, 1, 12, 0, tzinfo=timezone.utc)
        return start_trailing(signal_price, bounce_pct, hours_left, now)

    def test_tracks_lower_price(self) -> None:
        ctx = self._make_ctx(signal_price=100.0)
        now = datetime(2026, 4, 1, 13, 0, tzinfo=timezone.utc)

        action, updated = update_trailing(ctx, current_price=95.0, now=now)

        assert action == "continue"
        assert updated["lowest_price"] == 95.0

    def test_triggers_buy_on_bounce(self) -> None:
        ctx = self._make_ctx(signal_price=100.0, bounce_pct=0.02)
        now = datetime(2026, 4, 1, 13, 0, tzinfo=timezone.utc)

        # First drive price down
        _, ctx = update_trailing(ctx, current_price=90.0, now=now)
        assert ctx["lowest_price"] == 90.0

        # Now bounce: 90 * 1.02 = 91.8 — price at 92 should trigger
        action, updated = update_trailing(ctx, current_price=92.0, now=now)

        assert action == "buy"
        assert updated["status"] == "triggered"

    def test_expires_after_max_hours(self) -> None:
        ctx = self._make_ctx(signal_price=100.0, hours_left=12)
        # Jump past expiry
        expired_time = datetime(2026, 4, 2, 1, 0, tzinfo=timezone.utc)  # 13h later

        action, updated = update_trailing(ctx, current_price=99.0, now=expired_time)

        assert action == "expired"
        assert updated["status"] == "expired"

    def test_continues_when_price_drops(self) -> None:
        ctx = self._make_ctx(signal_price=100.0, bounce_pct=0.02)
        now = datetime(2026, 4, 1, 13, 0, tzinfo=timezone.utc)

        # Price drops steadily — no bounce
        action, ctx = update_trailing(ctx, current_price=98.0, now=now)
        assert action == "continue"
        action, ctx = update_trailing(ctx, current_price=96.0, now=now)
        assert action == "continue"
        action, ctx = update_trailing(ctx, current_price=94.0, now=now)
        assert action == "continue"
        assert ctx["lowest_price"] == 94.0

    def test_bounce_not_triggered_when_insufficient(self) -> None:
        """Price rises but not enough to meet bounce_pct threshold."""
        ctx = self._make_ctx(signal_price=100.0, bounce_pct=0.02)
        now = datetime(2026, 4, 1, 13, 0, tzinfo=timezone.utc)

        # Drive to 90, then rise to 91 (1.1% < 2%)
        _, ctx = update_trailing(ctx, current_price=90.0, now=now)
        action, _ = update_trailing(ctx, current_price=91.0, now=now)
        assert action == "continue"


class TestProfilesHaveTrailingBuyParams:
    @pytest.mark.parametrize("name", ["conservative", "balanced", "aggressive"])
    def test_profile_has_trailing_buy_fields(self, name: str) -> None:
        profile = PROFILES[name]
        assert isinstance(profile.trailing_buy_bounce_pct, float)
        assert profile.trailing_buy_bounce_pct > 0
        assert isinstance(profile.trailing_buy_max_hours, int)
        assert profile.trailing_buy_max_hours > 0

    def test_conservative_has_highest_bounce(self) -> None:
        assert PROFILES["conservative"].trailing_buy_bounce_pct > PROFILES["aggressive"].trailing_buy_bounce_pct

    def test_aggressive_has_longest_trail(self) -> None:
        assert PROFILES["aggressive"].trailing_buy_max_hours > PROFILES["conservative"].trailing_buy_max_hours


# ── Integration tests (s2) — mock DB ─────────────


def _mock_entry_decision(
    asset_id: uuid.UUID,
    recommendation_id: uuid.UUID,
    context_data: dict,
    status: str = "pending",
    stage: str = "trailing_buy",
) -> MagicMock:
    ed = MagicMock()
    ed.id = uuid.uuid4()
    ed.asset_id = asset_id
    ed.recommendation_id = recommendation_id
    ed.status = status
    ed.stage = stage
    ed.context_data = context_data
    ed.reason_codes = None
    ed.reason_text = None
    return ed


class TestIntegrationNewCandidateCreatesTrailingEntry:
    """Verify that when _check_entries processes a candidate, it creates
    a trailing buy EntryDecision instead of immediately buying."""

    @pytest.mark.asyncio
    async def test_new_candidate_creates_trailing_entry(self) -> None:
        from app.portfolio.trailing_buy import start_trailing

        now = datetime(2026, 4, 1, 12, 0, tzinfo=timezone.utc)
        ctx = start_trailing(100.0, 0.015, 18, now)

        assert ctx["status"] == "trailing"
        assert ctx["lowest_price"] == 100.0
        assert ctx["bounce_pct"] == 0.015


class TestIntegrationPendingTrailTriggersBuy:
    """Verify update_trailing triggers buy when price bounces."""

    @pytest.mark.asyncio
    async def test_pending_trail_triggers_buy_on_bounce(self) -> None:
        now = datetime(2026, 4, 1, 12, 0, tzinfo=timezone.utc)
        ctx = start_trailing(100.0, 0.02, 18, now)

        later = now + timedelta(hours=2)
        _, ctx = update_trailing(ctx, 90.0, later)
        action, ctx = update_trailing(ctx, 92.0, later)

        assert action == "buy"
        assert ctx["status"] == "triggered"


class TestIntegrationPendingTrailExpires:
    """Verify update_trailing expires trail after max_hours."""

    @pytest.mark.asyncio
    async def test_pending_trail_expires(self) -> None:
        now = datetime(2026, 4, 1, 12, 0, tzinfo=timezone.utc)
        ctx = start_trailing(100.0, 0.02, 6, now)

        expired_time = now + timedelta(hours=7)
        action, ctx = update_trailing(ctx, 99.0, expired_time)

        assert action == "expired"
        assert ctx["status"] == "expired"
