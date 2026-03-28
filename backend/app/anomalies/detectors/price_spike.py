"""Price spike / crash detector — Z-score on percentage change."""

import numpy as np
import pandas as pd

from app.config import settings

from .base import AnomalyCandidate, BaseDetector, score_to_severity

WINDOW = 50  # rolling window for Z-score calculation


class PriceSpikeDetector(BaseDetector):
    @property
    def name(self) -> str:
        return "price_spike"

    def detect(
        self,
        closes: pd.Series,
        volumes: pd.Series,
        rsi: float | None = None,
    ) -> AnomalyCandidate | None:
        if len(closes) < WINDOW + 1:
            return None

        pct_changes = closes.pct_change().dropna()
        if len(pct_changes) < WINDOW:
            return None

        recent = pct_changes.iloc[-WINDOW:]
        mean = recent.mean()
        std = recent.std()

        if std == 0 or np.isnan(std):
            return None

        latest_change = pct_changes.iloc[-1]
        z = (latest_change - mean) / std
        threshold = settings.ANOMALY_PRICE_ZSCORE_THRESHOLD

        if abs(z) < threshold:
            return None

        # Normalize z-score to 0-1 score: threshold maps to ~0.5, 2x threshold maps to ~1.0
        raw_score = min(abs(z) / (threshold * 2), 1.0)
        severity = score_to_severity(raw_score)
        anomaly_type = "price_crash" if z < 0 else "price_spike"

        return AnomalyCandidate(
            anomaly_type=anomaly_type,
            severity=severity,
            score=round(raw_score, 4),
            details={
                "z_score": round(float(z), 4),
                "threshold": threshold,
                "pct_change": round(float(latest_change), 6),
                "window": WINDOW,
                "latest_close": round(float(closes.iloc[-1]), 4),
            },
        )
