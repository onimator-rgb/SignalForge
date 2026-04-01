"""Tests for loss-aware buy cooldown per asset (marketpulse-task-2026-04-01-0007)."""

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.portfolio.protections import (
    COOLDOWN_AFTER_LOSS_HOURS,
    COOLDOWN_AFTER_PROFIT_HOURS,
    _check_asset_cooldown,
    check_protections,
)


def _make_position(
    closed_at: datetime,
    realized_pnl_usd: float,
    portfolio_id: uuid.UUID | None = None,
    asset_id: uuid.UUID | None = None,
) -> MagicMock:
    pos = MagicMock()
    pos.portfolio_id = portfolio_id or uuid.uuid4()
    pos.asset_id = asset_id or uuid.uuid4()
    pos.status = "closed"
    pos.closed_at = closed_at
    pos.realized_pnl_usd = realized_pnl_usd
    return pos


def _mock_db_returning_position(position: MagicMock | None) -> AsyncMock:
    """Create a mock AsyncSession whose execute().scalars().first() returns position."""
    db = AsyncMock()
    result = MagicMock()
    scalars = MagicMock()
    scalars.first.return_value = position
    result.scalars.return_value = scalars
    db.execute.return_value = result
    return db


NOW = datetime(2026, 4, 1, 12, 0, 0, tzinfo=timezone.utc)
PID = uuid.uuid4()
AID = uuid.uuid4()


# ── 1. Cooldown blocks re-entry after a loss within 48h ──

@pytest.mark.asyncio
async def test_loss_blocks_within_48h() -> None:
    closed_at = NOW - timedelta(hours=10)  # closed 10h ago — well within 48h
    pos = _make_position(closed_at=closed_at, realized_pnl_usd=-50.0)
    db = _mock_db_returning_position(pos)

    blocked, reason, hours = await _check_asset_cooldown(db, PID, AID, NOW)

    assert blocked is True
    assert hours == COOLDOWN_AFTER_LOSS_HOURS
    assert reason is not None
    assert "loss" in reason
    assert str(COOLDOWN_AFTER_LOSS_HOURS) in reason


# ── 2. Cooldown allows re-entry after a loss once 48h passed ──

@pytest.mark.asyncio
async def test_loss_allows_after_48h() -> None:
    closed_at = NOW - timedelta(hours=49)  # closed 49h ago — past 48h
    pos = _make_position(closed_at=closed_at, realized_pnl_usd=-50.0)
    db = _mock_db_returning_position(pos)

    blocked, reason, hours = await _check_asset_cooldown(db, PID, AID, NOW)

    assert blocked is False
    assert reason is None


# ── 3. Cooldown blocks re-entry after a profit within 12h ──

@pytest.mark.asyncio
async def test_profit_blocks_within_12h() -> None:
    closed_at = NOW - timedelta(hours=5)  # closed 5h ago — within 12h
    pos = _make_position(closed_at=closed_at, realized_pnl_usd=30.0)
    db = _mock_db_returning_position(pos)

    blocked, reason, hours = await _check_asset_cooldown(db, PID, AID, NOW)

    assert blocked is True
    assert hours == COOLDOWN_AFTER_PROFIT_HOURS
    assert reason is not None
    assert "profit" in reason
    assert str(COOLDOWN_AFTER_PROFIT_HOURS) in reason


# ── 4. Cooldown allows re-entry after a profit once 12h passed ──

@pytest.mark.asyncio
async def test_profit_allows_after_12h() -> None:
    closed_at = NOW - timedelta(hours=13)  # closed 13h ago — past 12h
    pos = _make_position(closed_at=closed_at, realized_pnl_usd=30.0)
    db = _mock_db_returning_position(pos)

    blocked, reason, hours = await _check_asset_cooldown(db, PID, AID, NOW)

    assert blocked is False
    assert reason is None


# ── 5. No prior closes for asset → entry allowed ──

@pytest.mark.asyncio
async def test_no_prior_closes_allows_entry() -> None:
    db = _mock_db_returning_position(None)

    blocked, reason, hours = await _check_asset_cooldown(db, PID, AID, NOW)

    assert blocked is False
    assert reason is None
    assert hours == 0


# ── 6. ProtectionEvent is logged with correct expires_at ──

@pytest.mark.asyncio
async def test_protection_event_logged_with_correct_expiry() -> None:
    closed_at = NOW - timedelta(hours=2)
    pos = _make_position(closed_at=closed_at, realized_pnl_usd=-10.0)

    # We need to mock check_protections' dependencies
    # Mock _check_asset_cooldown to return blocked with loss cooldown
    # and verify _log_protection is called with the right expires

    with patch("app.portfolio.protections._expire_protections", new_callable=AsyncMock), \
         patch("app.portfolio.protections._check_asset_cooldown", new_callable=AsyncMock) as mock_cd, \
         patch("app.portfolio.protections._log_protection", new_callable=AsyncMock) as mock_log:
        mock_cd.return_value = (True, f"Asset closed at loss within last {COOLDOWN_AFTER_LOSS_HOURS}h", COOLDOWN_AFTER_LOSS_HOURS)

        db = AsyncMock()
        allowed, ptype, reason = await check_protections(
            db, PID, AID, asset_class="crypto", regime="neutral", now=NOW
        )

        assert allowed is False
        assert ptype == "asset_cooldown"

        mock_log.assert_called_once()
        call_kwargs = mock_log.call_args
        expires_at = call_kwargs.kwargs.get("expires") or call_kwargs[1].get("expires")
        expected = NOW + timedelta(hours=COOLDOWN_AFTER_LOSS_HOURS)
        assert expires_at == expected


# ── Edge: zero PnL treated as profit (>= 0) ──

@pytest.mark.asyncio
async def test_zero_pnl_uses_profit_cooldown() -> None:
    closed_at = NOW - timedelta(hours=5)
    pos = _make_position(closed_at=closed_at, realized_pnl_usd=0.0)
    db = _mock_db_returning_position(pos)

    blocked, reason, hours = await _check_asset_cooldown(db, PID, AID, NOW)

    assert blocked is True
    assert hours == COOLDOWN_AFTER_PROFIT_HOURS
