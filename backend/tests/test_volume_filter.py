"""Tests for absolute volume floor confirmation rule (#5)."""

from datetime import datetime, timezone

from app.portfolio.confirmations import (
    MIN_ABS_VOLUME_CRYPTO,
    MIN_ABS_VOLUME_STOCK,
    RISKOFF_ABS_VOLUME_CRYPTO,
    RISKOFF_ABS_VOLUME_STOCK,
    check_confirmations,
)

NOW = datetime.now(timezone.utc)
# latest_volume high enough to avoid weak_volume trigger on rule #3
HIGH_LATEST_VOL = 500_000.0


def _check(
    avg_volume: float | None,
    asset_class: str = "crypto",
    regime: str = "neutral",
) -> dict:
    return check_confirmations(
        indicators=None,
        change_24h_pct=None,
        avg_volume=avg_volume,
        latest_volume=HIGH_LATEST_VOL,
        rec_generated_at=NOW,
        asset_class=asset_class,
        regime=regime,
        now=NOW,
    )


def test_low_abs_volume_crypto_blocks() -> None:
    result = _check(avg_volume=30_000, asset_class="crypto", regime="neutral")
    assert not result["allowed"]
    assert "low_abs_volume" in result["reason_codes"]


def test_sufficient_volume_crypto_passes() -> None:
    result = _check(avg_volume=80_000, asset_class="crypto")
    assert result["allowed"]
    assert "low_abs_volume" not in result["reason_codes"]


def test_low_abs_volume_stock_blocks() -> None:
    result = _check(avg_volume=60_000, asset_class="stock")
    assert not result["allowed"]
    assert "low_abs_volume" in result["reason_codes"]


def test_sufficient_volume_stock_passes() -> None:
    result = _check(avg_volume=150_000, asset_class="stock")
    assert result["allowed"]
    assert "low_abs_volume" not in result["reason_codes"]


def test_none_volume_passes() -> None:
    result = _check(avg_volume=None)
    assert result["allowed"]
    assert "low_abs_volume" not in result["reason_codes"]


def test_risk_off_tighter_threshold_crypto() -> None:
    # 70k passes normal crypto (50k) but fails risk_off crypto (100k)
    normal = _check(avg_volume=70_000, asset_class="crypto", regime="neutral")
    assert normal["allowed"]
    riskoff = _check(avg_volume=70_000, asset_class="crypto", regime="risk_off")
    assert not riskoff["allowed"]
    assert "low_abs_volume" in riskoff["reason_codes"]


def test_risk_off_tighter_threshold_stock() -> None:
    # 150k passes normal stock (100k) but fails risk_off stock (200k)
    normal = _check(avg_volume=150_000, asset_class="stock", regime="neutral")
    assert normal["allowed"]
    riskoff = _check(avg_volume=150_000, asset_class="stock", regime="risk_off")
    assert not riskoff["allowed"]
    assert "low_abs_volume" in riskoff["reason_codes"]


def test_context_includes_volume_fields() -> None:
    result = _check(avg_volume=30_000, asset_class="crypto")
    ctx = result["context"]
    assert ctx["avg_volume_usd"] == 30_000.0
    assert ctx["min_volume_threshold"] == MIN_ABS_VOLUME_CRYPTO


def test_low_abs_volume_reason_text() -> None:
    result = _check(avg_volume=30_000, asset_class="crypto")
    assert "average volume below minimum" in result["reason_text"]
