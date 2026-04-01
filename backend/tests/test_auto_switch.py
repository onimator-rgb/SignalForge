"""Tests for auto strategy profile switch based on market regime."""

from unittest.mock import AsyncMock, patch

import pytest

from app.strategy.profiles import is_auto_switch_enabled, PROFILES
from app.strategy.service import auto_select_profile, REGIME_TO_PROFILE


def test_regime_to_profile_mapping() -> None:
    """REGIME_TO_PROFILE maps all 3 regimes to correct profiles."""
    assert REGIME_TO_PROFILE == {
        "risk_on": "aggressive",
        "neutral": "balanced",
        "risk_off": "conservative",
    }


@pytest.mark.asyncio
async def test_auto_select_profile_risk_on() -> None:
    """risk_on regime selects aggressive profile."""
    regime_info = {"regime": "risk_on", "score": 5, "inputs": {}}
    with patch(
        "app.strategy.service.calculate_regime",
        new_callable=AsyncMock,
        return_value=regime_info,
    ):
        db = AsyncMock()
        profile, info = await auto_select_profile(db)
        assert profile == PROFILES["aggressive"]
        assert info["regime"] == "risk_on"


@pytest.mark.asyncio
async def test_auto_select_profile_risk_off() -> None:
    """risk_off regime selects conservative profile."""
    regime_info = {"regime": "risk_off", "score": -5, "inputs": {}}
    with patch(
        "app.strategy.service.calculate_regime",
        new_callable=AsyncMock,
        return_value=regime_info,
    ), patch(
        "app.strategy.service.apply_profile_to_open_positions",
        new_callable=AsyncMock,
        return_value=0,
    ):
        db = AsyncMock()
        profile, info = await auto_select_profile(db)
        assert profile == PROFILES["conservative"]
        assert info["regime"] == "risk_off"


@pytest.mark.asyncio
async def test_auto_select_profile_neutral() -> None:
    """neutral regime selects balanced profile."""
    regime_info = {"regime": "neutral", "score": 0, "inputs": {}}
    with patch(
        "app.strategy.service.calculate_regime",
        new_callable=AsyncMock,
        return_value=regime_info,
    ), patch(
        "app.strategy.service.apply_profile_to_open_positions",
        new_callable=AsyncMock,
        return_value=0,
    ):
        db = AsyncMock()
        profile, info = await auto_select_profile(db)
        assert profile == PROFILES["balanced"]
        assert info["regime"] == "neutral"


def test_is_auto_switch_enabled_default() -> None:
    """Auto-switch is disabled by default."""
    assert is_auto_switch_enabled() is False


def test_is_auto_switch_enabled_true() -> None:
    """Auto-switch returns True when setting is enabled."""
    with patch("app.strategy.profiles.settings") as mock_settings:
        mock_settings.STRATEGY_AUTO_SWITCH = True
        assert is_auto_switch_enabled() is True
