"""Comprehensive unit tests for all 4 anomaly detectors.

Task: marketpulse-task-2026-04-01-0003
"""

from __future__ import annotations

from dataclasses import dataclass
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest

from app.anomalies.detectors.base import AnomalyCandidate, score_to_severity
from app.anomalies.detectors.price_spike import PriceSpikeDetector
from app.anomalies.detectors.rsi_extreme import RSIExtremeDetector
from app.anomalies.detectors.squeeze import SqueezeDetector
from app.anomalies.detectors.volume_spike import VolumeSpikeDetector


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_DUMMY_VOL = pd.Series([1000.0] * 100)
_DUMMY_CLOSES = pd.Series([100.0] * 100)


# ---------------------------------------------------------------------------
# PriceSpikeDetector  (WINDOW=50, threshold=2.5)
# ---------------------------------------------------------------------------


class TestPriceSpikeDetector:
    det = PriceSpikeDetector()

    def test_returns_none_when_data_too_short(self) -> None:
        closes = pd.Series([100.0] * 50)  # need >= 51
        assert self.det.detect(closes, _DUMMY_VOL[:50]) is None

    def test_returns_none_when_no_spike(self) -> None:
        # All constant prices -> std==0 -> guard returns None
        closes = pd.Series([100.0] * 60)
        assert self.det.detect(closes, _DUMMY_VOL[:60]) is None

    def test_detects_price_spike(self) -> None:
        rng = np.random.default_rng(42)
        prices = 100.0 + rng.normal(0, 0.1, 51)
        prices[-1] = 115.0  # big spike
        closes = pd.Series(prices)
        result = self.det.detect(closes, _DUMMY_VOL[:51])
        assert result is not None
        assert result.anomaly_type == "price_spike"
        assert result.details["z_score"] > 0

    def test_detects_price_crash(self) -> None:
        rng = np.random.default_rng(42)
        prices = 100.0 + rng.normal(0, 0.1, 51)
        prices[-1] = 85.0  # big drop
        closes = pd.Series(prices)
        result = self.det.detect(closes, _DUMMY_VOL[:51])
        assert result is not None
        assert result.anomaly_type == "price_crash"
        assert result.details["z_score"] < 0

    def test_at_threshold_boundary(self) -> None:
        # Constant prices = zero std -> None (no spike possible at boundary)
        closes = pd.Series([100.0] * 60)
        assert self.det.detect(closes, _DUMMY_VOL[:60]) is None

    def test_severity_mapping(self) -> None:
        assert score_to_severity(0.3) == "low"
        assert score_to_severity(0.6) == "medium"
        assert score_to_severity(0.75) == "high"
        assert score_to_severity(0.9) == "critical"

    def test_details_keys(self) -> None:
        rng = np.random.default_rng(42)
        prices = 100.0 + rng.normal(0, 0.1, 51)
        prices[-1] = 115.0
        closes = pd.Series(prices)
        result = self.det.detect(closes, _DUMMY_VOL[:51])
        assert result is not None
        expected_keys = {"z_score", "threshold", "pct_change", "window", "latest_close"}
        assert expected_keys == set(result.details.keys())


# ---------------------------------------------------------------------------
# VolumeSpikeDetector  (WINDOW=20, threshold=3.0)
# ---------------------------------------------------------------------------


class TestVolumeSpikeDetector:
    det = VolumeSpikeDetector()

    def test_returns_none_when_data_too_short(self) -> None:
        vols = pd.Series([1000.0] * 20)  # need >= 21
        assert self.det.detect(_DUMMY_CLOSES[:20], vols) is None

    def test_returns_none_when_no_spike(self) -> None:
        vols = pd.Series([1000.0] * 25)
        assert self.det.detect(_DUMMY_CLOSES[:25], vols) is None

    def test_detects_volume_spike(self) -> None:
        rng = np.random.default_rng(7)
        base = 1000.0 + rng.normal(0, 50, 20)
        vols = pd.Series(list(base) + [10000.0])  # last bar ~10x
        result = self.det.detect(_DUMMY_CLOSES[:21], vols)
        assert result is not None
        assert result.anomaly_type == "volume_spike"
        assert result.details["z_score"] > 0

    def test_returns_none_for_negative_z(self) -> None:
        # Below-average volume should not trigger
        vols = pd.Series([10000.0] * 20 + [100.0])
        result = self.det.detect(_DUMMY_CLOSES[:21], vols)
        assert result is None

    def test_zero_mean_guard(self) -> None:
        vols = pd.Series([0.0] * 21)
        assert self.det.detect(_DUMMY_CLOSES[:21], vols) is None

    def test_details_has_ratio_vs_avg(self) -> None:
        rng = np.random.default_rng(7)
        base = 1000.0 + rng.normal(0, 50, 20)
        vols = pd.Series(list(base) + [10000.0])
        result = self.det.detect(_DUMMY_CLOSES[:21], vols)
        assert result is not None
        assert "ratio_vs_avg" in result.details


# ---------------------------------------------------------------------------
# RSIExtremeDetector  (upper=80, lower=20)
# ---------------------------------------------------------------------------


class TestRSIExtremeDetector:
    det = RSIExtremeDetector()

    def test_returns_none_when_rsi_is_none(self) -> None:
        assert self.det.detect(_DUMMY_CLOSES, _DUMMY_VOL, rsi=None) is None

    def test_returns_none_when_rsi_normal(self) -> None:
        assert self.det.detect(_DUMMY_CLOSES, _DUMMY_VOL, rsi=50.0) is None

    def test_at_upper_boundary(self) -> None:
        assert self.det.detect(_DUMMY_CLOSES, _DUMMY_VOL, rsi=80.0) is None

    def test_at_lower_boundary(self) -> None:
        assert self.det.detect(_DUMMY_CLOSES, _DUMMY_VOL, rsi=20.0) is None

    def test_overbought(self) -> None:
        result = self.det.detect(_DUMMY_CLOSES, _DUMMY_VOL, rsi=85.0)
        assert result is not None
        assert result.anomaly_type == "rsi_extreme"
        assert result.details["direction"] == "overbought"

    def test_oversold(self) -> None:
        result = self.det.detect(_DUMMY_CLOSES, _DUMMY_VOL, rsi=15.0)
        assert result is not None
        assert result.anomaly_type == "rsi_extreme"
        assert result.details["direction"] == "oversold"

    def test_extreme_overbought_high_severity(self) -> None:
        result = self.det.detect(_DUMMY_CLOSES, _DUMMY_VOL, rsi=98.0)
        assert result is not None
        assert result.severity in ("high", "critical")

    def test_extreme_oversold_high_severity(self) -> None:
        result = self.det.detect(_DUMMY_CLOSES, _DUMMY_VOL, rsi=2.0)
        assert result is not None
        assert result.severity in ("high", "critical")


# ---------------------------------------------------------------------------
# SqueezeDetector
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _FakeSqueezeState:
    """Minimal stand-in matching SqueezeState fields used by SqueezeDetector."""

    is_squeeze: bool
    momentum: float
    bb_width: float = 0.02
    kc_width: float = 0.04


_SQ_PATCH = "app.anomalies.detectors.squeeze.detect_squeeze"


class TestSqueezeDetector:
    det = SqueezeDetector()

    def test_returns_none_when_data_too_short(self) -> None:
        closes = pd.Series([100.0] * 20)  # need >= 21
        assert self.det.detect(closes, _DUMMY_VOL[:20]) is None

    def test_returns_none_during_active_squeeze(self) -> None:
        state = _FakeSqueezeState(is_squeeze=True, momentum=5.0)
        with patch(_SQ_PATCH, return_value=state):
            closes = pd.Series([100.0] * 25)
            assert self.det.detect(closes, _DUMMY_VOL[:25]) is None

    def test_detects_squeeze_release(self) -> None:
        state = _FakeSqueezeState(is_squeeze=False, momentum=5.0)
        with patch(_SQ_PATCH, return_value=state):
            closes = pd.Series([100.0] * 25)
            result = self.det.detect(closes, _DUMMY_VOL[:25])
            assert result is not None
            assert result.anomaly_type == "squeeze_release"

    def test_returns_none_when_momentum_too_low(self) -> None:
        # momentum_pct = 0.1/100 = 0.001 < 0.005 threshold
        state = _FakeSqueezeState(is_squeeze=False, momentum=0.1)
        with patch(_SQ_PATCH, return_value=state):
            closes = pd.Series([100.0] * 25)
            assert self.det.detect(closes, _DUMMY_VOL[:25]) is None

    def test_returns_none_when_detect_squeeze_returns_none(self) -> None:
        with patch(_SQ_PATCH, return_value=None):
            closes = pd.Series([100.0] * 25)
            assert self.det.detect(closes, _DUMMY_VOL[:25]) is None
