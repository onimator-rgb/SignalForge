"""Squeeze release detector — fires when BB-inside-KC squeeze ends with momentum."""

import pandas as pd

from app.indicators.calculators.squeeze import detect_squeeze

from .base import AnomalyCandidate, BaseDetector, score_to_severity


class SqueezeDetector(BaseDetector):
    @property
    def name(self) -> str:
        return "squeeze_release"

    def detect(
        self,
        closes: pd.Series,
        volumes: pd.Series,
        rsi: float | None = None,
    ) -> AnomalyCandidate | None:
        if len(closes) < 21:
            return None

        # Approximate highs/lows from closes (no H/L in BaseDetector interface)
        highs = closes * 1.005
        lows = closes * 0.995

        state = detect_squeeze(closes, highs, lows)
        if state is None:
            return None

        # Fire only on squeeze release with strong momentum
        if state.is_squeeze:
            return None

        latest_close = float(closes.iloc[-1])
        if latest_close == 0:
            return None

        momentum_pct = abs(state.momentum) / latest_close
        if momentum_pct < 0.005:  # 0.5% threshold
            return None

        raw_score = min(momentum_pct * 100, 1.0)  # normalize: 1% momentum -> score 1.0
        severity = score_to_severity(raw_score)

        return AnomalyCandidate(
            anomaly_type="squeeze_release",
            severity=severity,
            score=round(raw_score, 4),
            details={
                "is_squeeze": state.is_squeeze,
                "momentum": round(state.momentum, 4),
                "bb_width": round(state.bb_width, 4),
                "kc_width": round(state.kc_width, 4),
                "close": round(latest_close, 4),
            },
        )
