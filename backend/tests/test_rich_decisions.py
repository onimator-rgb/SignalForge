"""Tests for rich entry/exit decision logging with signal snapshots."""

import json
from datetime import datetime
from uuid import uuid4

import pytest

from app.indicators.schemas import BollingerOut, IndicatorSnapshot, MACDOut
from app.portfolio.decision_context import build_entry_snapshot, build_exit_snapshot
from app.recommendations.scoring import SignalScore


def _make_indicators() -> IndicatorSnapshot:
    """Create a full IndicatorSnapshot for testing."""
    return IndicatorSnapshot(
        asset_id=uuid4(),
        asset_symbol="BTC/USD",
        interval="1h",
        bar_time=datetime(2026, 4, 1, 0, 0),
        close=50000.0,
        rsi_14=45.2,
        macd=MACDOut(macd=120.5, signal=100.3, histogram=20.2),
        bollinger=BollingerOut(upper=51000.0, middle=50000.0, lower=49000.0, width=0.04),
        adx_14=28.5,
        stoch_rsi_k=0.35,
        stoch_rsi_d=0.42,
        bars_available=100,
    )


def _make_signals() -> list[SignalScore]:
    return [
        SignalScore(name="rsi", score=0.3, weight=0.15, detail="RSI 45 neutral-bullish"),
        SignalScore(name="macd", score=0.5, weight=0.15, detail="MACD bullish cross"),
        SignalScore(name="bollinger", score=-0.2, weight=0.15, detail="Price near middle band"),
    ]


class TestBuildEntrySnapshot:
    def test_full_indicators(self) -> None:
        ind = _make_indicators()
        signals = _make_signals()
        snap = build_entry_snapshot(
            indicators=ind, signals=signals,
            composite_score=72.5, recommendation_type="candidate_buy",
            confidence="high", risk_level="medium",
            regime="bull", profile_name="aggressive",
            change_24h_pct=2.5, avg_volume=1000.0, latest_volume=1500.0,
        )

        assert snap["rsi"] == 45.2
        assert snap["macd"] == {"line": 120.5, "signal": 100.3, "histogram": 20.2}
        assert snap["bollinger"] == {
            "upper": 51000.0, "middle": 50000.0, "lower": 49000.0, "bandwidth": 0.04,
        }
        assert snap["adx"] == 28.5
        assert snap["stoch_rsi"] == {"k": 0.35, "d": 0.42}
        assert snap["composite_score"] == 72.5
        assert snap["recommendation_type"] == "candidate_buy"
        assert snap["confidence"] == "high"
        assert snap["risk_level"] == "medium"
        assert snap["regime"] == "bull"
        assert snap["profile"] == "aggressive"
        assert snap["change_24h_pct"] == 2.5
        assert snap["volume_ratio"] == pytest.approx(1.5)
        assert snap["snapshot_version"] == "v1"

    def test_signals_list_structure(self) -> None:
        signals = _make_signals()
        snap = build_entry_snapshot(
            indicators=None, signals=signals,
            composite_score=65.0, recommendation_type="candidate_buy",
            confidence="medium", risk_level="low",
            regime="neutral", profile_name="default",
            change_24h_pct=None, avg_volume=None, latest_volume=None,
        )

        assert len(snap["signals"]) == 3
        for s in snap["signals"]:
            assert set(s.keys()) == {"name", "score", "weight", "detail"}

        assert snap["signals"][0]["name"] == "rsi"
        assert snap["signals"][0]["score"] == 0.3
        assert snap["signals"][0]["weight"] == 0.15

    def test_none_indicators_no_crash(self) -> None:
        snap = build_entry_snapshot(
            indicators=None, signals=None,
            composite_score=None, recommendation_type=None,
            confidence=None, risk_level=None,
            regime=None, profile_name=None,
            change_24h_pct=None, avg_volume=None, latest_volume=None,
        )

        assert snap["rsi"] is None
        assert snap["macd"] is None
        assert snap["bollinger"] is None
        assert snap["adx"] is None
        assert snap["stoch_rsi"] is None
        assert snap["signals"] == []
        assert snap["volume_ratio"] is None
        assert snap["snapshot_version"] == "v1"

    def test_volume_ratio_computed(self) -> None:
        snap = build_entry_snapshot(
            indicators=None, signals=None,
            composite_score=50.0, recommendation_type="hold",
            confidence="low", risk_level="high",
            regime="bear", profile_name="conservative",
            change_24h_pct=-3.0, avg_volume=2000.0, latest_volume=3000.0,
        )
        assert snap["volume_ratio"] == pytest.approx(1.5)

    def test_volume_ratio_none_when_avg_zero(self) -> None:
        snap = build_entry_snapshot(
            indicators=None, signals=None,
            composite_score=50.0, recommendation_type="hold",
            confidence="low", risk_level="high",
            regime="bear", profile_name="conservative",
            change_24h_pct=None, avg_volume=0.0, latest_volume=100.0,
        )
        assert snap["volume_ratio"] is None

    def test_volume_ratio_none_when_missing(self) -> None:
        snap = build_entry_snapshot(
            indicators=None, signals=None,
            composite_score=50.0, recommendation_type="hold",
            confidence="low", risk_level="high",
            regime="bear", profile_name="conservative",
            change_24h_pct=None, avg_volume=1000.0, latest_volume=None,
        )
        assert snap["volume_ratio"] is None

    def test_json_serializable(self) -> None:
        ind = _make_indicators()
        signals = _make_signals()
        snap = build_entry_snapshot(
            indicators=ind, signals=signals,
            composite_score=72.5, recommendation_type="candidate_buy",
            confidence="high", risk_level="medium",
            regime="bull", profile_name="aggressive",
            change_24h_pct=2.5, avg_volume=1000.0, latest_volume=1500.0,
        )
        # Must not raise
        serialized = json.dumps(snap)
        deserialized = json.loads(serialized)
        assert deserialized["snapshot_version"] == "v1"
        assert isinstance(deserialized["signals"], list)

    def test_partial_indicators(self) -> None:
        """Indicators with only RSI set (macd, bollinger None)."""
        ind = IndicatorSnapshot(
            asset_id=uuid4(), asset_symbol="ETH/USD", interval="1h",
            bar_time=datetime(2026, 4, 1), close=3000.0,
            rsi_14=55.0, bars_available=50,
        )
        snap = build_entry_snapshot(
            indicators=ind, signals=None,
            composite_score=60.0, recommendation_type="hold",
            confidence="medium", risk_level="low",
            regime="neutral", profile_name="default",
            change_24h_pct=1.0, avg_volume=500.0, latest_volume=600.0,
        )
        assert snap["rsi"] == 55.0
        assert snap["macd"] is None
        assert snap["bollinger"] is None
        assert snap["adx"] is None
        assert snap["stoch_rsi"] is None


class TestBuildExitSnapshot:
    def test_full_exit(self) -> None:
        ind = _make_indicators()
        snap = build_exit_snapshot(
            indicators=ind,
            rec_score=35.0, rec_type="sell",
            close_reason="stop_loss", pnl_pct=-5.2,
            regime="bear",
        )

        assert snap["rsi"] == 45.2
        assert snap["macd"]["line"] == 120.5
        assert snap["bollinger"]["upper"] == 51000.0
        assert snap["adx"] == 28.5
        assert snap["stoch_rsi"] == {"k": 0.35, "d": 0.42}
        assert snap["rec_score"] == 35.0
        assert snap["rec_type"] == "sell"
        assert snap["close_reason"] == "stop_loss"
        assert snap["pnl_pct"] == -5.2
        assert snap["regime"] == "bear"
        assert snap["snapshot_version"] == "v1"

    def test_none_indicators(self) -> None:
        snap = build_exit_snapshot(
            indicators=None,
            rec_score=None, rec_type=None,
            close_reason="manual", pnl_pct=0.0,
            regime=None,
        )
        assert snap["rsi"] is None
        assert snap["macd"] is None
        assert snap["close_reason"] == "manual"
        assert snap["snapshot_version"] == "v1"

    def test_json_serializable(self) -> None:
        ind = _make_indicators()
        snap = build_exit_snapshot(
            indicators=ind,
            rec_score=42.0, rec_type="hold",
            close_reason="take_profit", pnl_pct=8.5,
            regime="bull",
        )
        serialized = json.dumps(snap)
        deserialized = json.loads(serialized)
        assert deserialized["pnl_pct"] == 8.5
        assert deserialized["snapshot_version"] == "v1"


ENTRY_SNAPSHOT_KEYS = {
    "rsi", "macd", "bollinger", "adx", "stoch_rsi", "signals",
    "composite_score", "recommendation_type", "confidence", "risk_level",
    "regime", "profile", "change_24h_pct", "volume_ratio", "snapshot_version",
}

EXIT_SNAPSHOT_KEYS = {
    "rsi", "macd", "bollinger", "adx", "stoch_rsi",
    "rec_score", "rec_type", "close_reason", "pnl_pct", "regime",
    "snapshot_version",
}


class TestSnapshotKeys:
    def test_entry_snapshot_has_all_keys(self) -> None:
        snap = build_entry_snapshot(
            indicators=None, signals=None,
            composite_score=None, recommendation_type=None,
            confidence=None, risk_level=None,
            regime=None, profile_name=None,
            change_24h_pct=None, avg_volume=None, latest_volume=None,
        )
        assert set(snap.keys()) == ENTRY_SNAPSHOT_KEYS

    def test_exit_snapshot_has_all_keys(self) -> None:
        snap = build_exit_snapshot(
            indicators=None,
            rec_score=None, rec_type=None,
            close_reason=None, pnl_pct=None,
            regime=None,
        )
        assert set(snap.keys()) == EXIT_SNAPSHOT_KEYS
