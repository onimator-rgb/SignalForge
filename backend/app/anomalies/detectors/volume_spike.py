"""Volume spike detector — Z-score on volume vs rolling average."""

import numpy as np
import pandas as pd

from app.config import settings

from .base import AnomalyCandidate, BaseDetector, score_to_severity

WINDOW = 20


class VolumeSpikeDetector(BaseDetector):
    @property
    def name(self) -> str:
        return "volume_spike"

    def detect(
        self,
        closes: pd.Series,
        volumes: pd.Series,
        rsi: float | None = None,
    ) -> AnomalyCandidate | None:
        if len(volumes) < WINDOW + 1:
            return None

        recent = volumes.iloc[-WINDOW - 1 : -1]  # window BEFORE the latest bar
        mean = recent.mean()
        std = recent.std()

        if std == 0 or np.isnan(std) or mean == 0:
            return None

        latest_vol = float(volumes.iloc[-1])
        z = (latest_vol - mean) / std
        threshold = settings.ANOMALY_VOLUME_ZSCORE_THRESHOLD

        if z < threshold:
            return None

        raw_score = min(z / (threshold * 2), 1.0)
        severity = score_to_severity(raw_score)

        return AnomalyCandidate(
            anomaly_type="volume_spike",
            severity=severity,
            score=round(raw_score, 4),
            details={
                "z_score": round(float(z), 4),
                "threshold": threshold,
                "latest_volume": round(latest_vol, 2),
                "avg_volume": round(float(mean), 2),
                "ratio_vs_avg": round(latest_vol / float(mean), 2),
                "window": WINDOW,
            },
        )
