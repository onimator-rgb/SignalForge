"""RSI extreme detector — overbought/oversold thresholds."""

import pandas as pd

from app.config import settings

from .base import AnomalyCandidate, BaseDetector, score_to_severity


class RSIExtremeDetector(BaseDetector):
    @property
    def name(self) -> str:
        return "rsi_extreme"

    def detect(
        self,
        closes: pd.Series,
        volumes: pd.Series,
        rsi: float | None = None,
    ) -> AnomalyCandidate | None:
        if rsi is None:
            return None

        upper = settings.ANOMALY_RSI_UPPER
        lower = settings.ANOMALY_RSI_LOWER

        if lower <= rsi <= upper:
            return None

        # How far beyond the threshold
        if rsi > upper:
            distance = rsi - upper
            max_distance = 100 - upper  # max possible overshoot
            direction = "overbought"
        else:
            distance = lower - rsi
            max_distance = lower  # max possible overshoot
            direction = "oversold"

        raw_score = min(0.5 + (distance / max_distance) * 0.5, 1.0) if max_distance > 0 else 0.5
        severity = score_to_severity(raw_score)

        return AnomalyCandidate(
            anomaly_type="rsi_extreme",
            severity=severity,
            score=round(raw_score, 4),
            details={
                "rsi": round(rsi, 2),
                "direction": direction,
                "threshold": upper if direction == "overbought" else lower,
                "distance": round(distance, 2),
            },
        )
