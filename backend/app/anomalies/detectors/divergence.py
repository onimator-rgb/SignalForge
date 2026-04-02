"""RSI/MACD divergence detector — swing high/low comparison."""

from __future__ import annotations

import pandas as pd

from app.indicators.calculators.rsi import calc_rsi

from .base import AnomalyCandidate, BaseDetector, score_to_severity

MIN_BARS = 40
RSI_TRAILING_WINDOW = 30
SWING_WINDOW = 5


def _find_swing_points(
    series: pd.Series, window: int = SWING_WINDOW
) -> tuple[list[tuple[int, float]], list[tuple[int, float]]]:
    """Find local swing highs and swing lows in a series.

    Returns:
        (swing_lows, swing_highs) — each is a list of (index, value) tuples.
    """
    lows: list[tuple[int, float]] = []
    highs: list[tuple[int, float]] = []
    values = series.values
    n = len(values)

    for i in range(window, n - window):
        val = float(values[i])
        left = values[i - window : i]
        right = values[i + 1 : i + window + 1]

        if val <= left.min() and val <= right.min():
            lows.append((i, val))
        if val >= left.max() and val >= right.max():
            highs.append((i, val))

    return lows, highs


def _build_rsi_series(closes: pd.Series, trailing: int = RSI_TRAILING_WINDOW) -> pd.Series:
    """Build a full RSI series by computing RSI on trailing slices."""
    rsi_values: list[float | None] = []
    for i in range(len(closes)):
        start = max(0, i - trailing + 1)
        sl = closes.iloc[start : i + 1]
        rsi_values.append(calc_rsi(sl, period=14))
    return pd.Series(rsi_values, dtype="float64")


class DivergenceDetector(BaseDetector):
    """Detect bullish/bearish divergences between price and RSI."""

    @property
    def name(self) -> str:
        return "divergence"

    def detect(
        self,
        closes: pd.Series,
        volumes: pd.Series,
        rsi: float | None = None,
    ) -> AnomalyCandidate | None:
        if len(closes) < MIN_BARS:
            return None

        # Build RSI series
        rsi_series = _build_rsi_series(closes)

        # Drop NaN values from RSI (first few bars won't have enough data)
        valid_mask = rsi_series.notna()
        if valid_mask.sum() < MIN_BARS // 2:
            return None

        # Find swing points in price and RSI
        price_lows, price_highs = _find_swing_points(closes)
        rsi_lows, rsi_highs = _find_swing_points(rsi_series.dropna().reset_index(drop=True))

        # Offset RSI swing indices to match original series indices
        first_valid = int(valid_mask.idxmax()) if valid_mask.any() else 0
        rsi_lows = [(idx + first_valid, val) for idx, val in rsi_lows]
        rsi_highs = [(idx + first_valid, val) for idx, val in rsi_highs]

        bullish = self._check_bullish(price_lows, rsi_lows)
        bearish = self._check_bearish(price_highs, rsi_highs)

        if bullish and bearish:
            return bullish if bullish.score >= bearish.score else bearish
        return bullish or bearish

    def _check_bullish(
        self,
        price_lows: list[tuple[int, float]],
        rsi_lows: list[tuple[int, float]],
    ) -> AnomalyCandidate | None:
        if len(price_lows) < 2 or len(rsi_lows) < 2:
            return None

        p1_idx, p1_val = price_lows[-2]
        p2_idx, p2_val = price_lows[-1]
        r1_idx, r1_val = rsi_lows[-2]
        r2_idx, r2_val = rsi_lows[-1]

        # Price makes lower low, RSI makes higher low
        if p2_val < p1_val and r2_val > r1_val:
            price_diff = abs(p1_val - p2_val) / max(abs(p1_val), 1e-9)
            rsi_diff = abs(r2_val - r1_val)
            magnitude = min(price_diff * 5 + rsi_diff / 100, 1.0)
            score = round(0.65 + magnitude * 0.20, 4)
            score = min(max(score, 0.65), 0.85)
            severity = score_to_severity(score)
            return AnomalyCandidate(
                anomaly_type="divergence",
                severity=severity,
                score=score,
                details={
                    "direction": "bullish",
                    "indicator": "rsi",
                    "price_points": [
                        {"index": p1_idx, "value": round(p1_val, 4)},
                        {"index": p2_idx, "value": round(p2_val, 4)},
                    ],
                    "indicator_points": [
                        {"index": r1_idx, "value": round(r1_val, 4)},
                        {"index": r2_idx, "value": round(r2_val, 4)},
                    ],
                },
            )
        return None

    def _check_bearish(
        self,
        price_highs: list[tuple[int, float]],
        rsi_highs: list[tuple[int, float]],
    ) -> AnomalyCandidate | None:
        if len(price_highs) < 2 or len(rsi_highs) < 2:
            return None

        p1_idx, p1_val = price_highs[-2]
        p2_idx, p2_val = price_highs[-1]
        r1_idx, r1_val = rsi_highs[-2]
        r2_idx, r2_val = rsi_highs[-1]

        # Price makes higher high, RSI makes lower high
        if p2_val > p1_val and r2_val < r1_val:
            price_diff = abs(p2_val - p1_val) / max(abs(p1_val), 1e-9)
            rsi_diff = abs(r1_val - r2_val)
            magnitude = min(price_diff * 5 + rsi_diff / 100, 1.0)
            score = round(0.65 + magnitude * 0.20, 4)
            score = min(max(score, 0.65), 0.85)
            severity = score_to_severity(score)
            return AnomalyCandidate(
                anomaly_type="divergence",
                severity=severity,
                score=score,
                details={
                    "direction": "bearish",
                    "indicator": "rsi",
                    "price_points": [
                        {"index": p1_idx, "value": round(p1_val, 4)},
                        {"index": p2_idx, "value": round(p2_val, 4)},
                    ],
                    "indicator_points": [
                        {"index": r1_idx, "value": round(r1_val, 4)},
                        {"index": r2_idx, "value": round(r2_val, 4)},
                    ],
                },
            )
        return None
