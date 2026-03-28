"""Base detector interface and shared types."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime

import pandas as pd


@dataclass(frozen=True)
class AnomalyCandidate:
    """Output of a detector when an anomaly is found."""

    anomaly_type: str  # e.g. 'price_spike', 'volume_spike', 'rsi_extreme'
    severity: str  # 'low', 'medium', 'high', 'critical'
    score: float  # 0.0 — 1.0
    details: dict  # supporting evidence: z_score, threshold, value, etc.


def score_to_severity(score: float) -> str:
    """Map a 0-1 score to severity label."""
    if score >= 0.9:
        return "critical"
    if score >= 0.75:
        return "high"
    if score >= 0.6:
        return "medium"
    return "low"


class BaseDetector(ABC):
    """Interface for all anomaly detectors."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Detector identifier."""

    @abstractmethod
    def detect(
        self,
        closes: pd.Series,
        volumes: pd.Series,
        rsi: float | None = None,
    ) -> AnomalyCandidate | None:
        """Run detection on the given data.

        Args:
            closes: Close prices, oldest first.
            volumes: Volumes, oldest first. Same length as closes.
            rsi: Pre-computed RSI value (optional, avoids recomputation).

        Returns:
            AnomalyCandidate if anomaly detected, None otherwise.
        """
