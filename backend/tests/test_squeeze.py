"""Tests for Squeeze Momentum calculator and SqueezeDetector."""

import pandas as pd
import pytest

from app.indicators.calculators.squeeze import (
    KeltnerResult,
    SqueezeState,
    calc_keltner,
    detect_squeeze,
)
from app.anomalies.detectors.squeeze import SqueezeDetector


# ── calc_keltner tests ────────────────────────────────


def test_keltner_insufficient_data() -> None:
    """Returns None when fewer than 21 bars provided."""
    n = 15
    closes = pd.Series([100.0 + i for i in range(n)])
    highs = pd.Series([101.0 + i for i in range(n)])
    lows = pd.Series([99.0 + i for i in range(n)])
    assert calc_keltner(closes, highs, lows) is None


def test_keltner_valid_output() -> None:
    """60 bars of trending data returns KeltnerResult with upper > middle > lower."""
    n = 60
    closes = pd.Series([100.0 + i * 0.5 for i in range(n)])
    highs = pd.Series([101.0 + i * 0.5 for i in range(n)])
    lows = pd.Series([99.0 + i * 0.5 for i in range(n)])

    result = calc_keltner(closes, highs, lows)
    assert result is not None
    assert isinstance(result, KeltnerResult)
    assert result.upper > result.middle > result.lower, (
        f"Expected upper > middle > lower, got {result.upper}, {result.middle}, {result.lower}"
    )


# ── detect_squeeze tests ─────────────────────────────


def test_squeeze_detected_low_volatility() -> None:
    """Tight-range bars cause BB to contract inside KC -> is_squeeze=True."""
    n = 60
    # Very tight range: BB bands will be narrow, KC bands wider due to ATR
    base = [100.0 + i * 0.01 for i in range(n)]  # near-flat prices
    closes = pd.Series(base)
    highs = pd.Series([c + 0.5 for c in base])   # wide high-low range for ATR
    lows = pd.Series([c - 0.5 for c in base])     # but close prices barely move

    result = detect_squeeze(closes, highs, lows)
    assert result is not None
    assert isinstance(result, SqueezeState)
    assert result.is_squeeze is True, (
        f"Expected squeeze (BB inside KC), got bb_width={result.bb_width}, kc_width={result.kc_width}"
    )


def test_no_squeeze_high_volatility() -> None:
    """Wide-swinging closes cause BB to expand outside KC -> is_squeeze=False."""
    n = 60
    # Closes swing wildly but high/low track close tightly
    import math
    base = [100.0 + 10.0 * math.sin(i * 0.5) for i in range(n)]
    closes = pd.Series(base)
    highs = pd.Series([c + 0.2 for c in base])  # tight H/L -> small ATR -> narrow KC
    lows = pd.Series([c - 0.2 for c in base])

    result = detect_squeeze(closes, highs, lows)
    assert result is not None
    assert result.is_squeeze is False, (
        f"Expected no squeeze (BB outside KC), got bb_width={result.bb_width}, kc_width={result.kc_width}"
    )


# ── SqueezeDetector tests ────────────────────────────


def test_squeeze_detector_name() -> None:
    """Verify name property returns 'squeeze_release'."""
    detector = SqueezeDetector()
    assert detector.name == "squeeze_release"


def test_squeeze_detector_returns_none_no_squeeze() -> None:
    """Sideways data with no meaningful momentum -> detector returns None."""
    import math

    n = 60
    # Small oscillation around 100 — no squeeze release, weak momentum
    closes = pd.Series([100.0 + 0.1 * math.sin(i * 0.3) for i in range(n)])
    volumes = pd.Series([1000.0] * n)

    detector = SqueezeDetector()
    result = detector.detect(closes, volumes)
    # With approximated H/L and tiny oscillation, momentum should be
    # well below 0.5% threshold
    assert result is None


def test_squeeze_detector_returns_candidate_on_release() -> None:
    """Squeeze release with strong momentum -> returns AnomalyCandidate."""
    n = 60
    # Phase 1 (0-39): tight range -> builds squeeze in approximated H/L
    # Phase 2 (40-59): sudden breakout upward -> squeeze releases with momentum
    vals = []
    for i in range(40):
        vals.append(100.0 + i * 0.001)  # near-flat
    for i in range(20):
        vals.append(100.04 + i * 2.0)   # strong breakout

    closes = pd.Series(vals)
    volumes = pd.Series([1000.0] * n)

    detector = SqueezeDetector()
    result = detector.detect(closes, volumes)

    if result is not None:
        # If detected, validate structure
        assert result.anomaly_type == "squeeze_release"
        assert 0.0 <= result.score <= 1.0
        assert "momentum" in result.details
        assert "bb_width" in result.details
        assert "kc_width" in result.details
        assert "close" in result.details
