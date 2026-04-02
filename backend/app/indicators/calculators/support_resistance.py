"""Support & Resistance Level Calculator.

Identifies key support and resistance price levels from historical OHLC bars
using local minima/maxima detection with proximity clustering.
"""

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class SRLevel:
    price: float
    level_type: str  # 'support' or 'resistance'
    touch_count: int
    strength: float


def find_support_resistance(
    highs: pd.Series,
    lows: pd.Series,
    closes: pd.Series,
    window: int = 5,
    cluster_pct: float = 0.02,
    max_levels: int = 10,
) -> list[SRLevel]:
    """Identify support and resistance levels from OHLC price data.

    Uses local minima/maxima detection with proximity clustering to find
    and merge nearby price levels.

    Args:
        highs: Series of high prices, oldest first.
        lows: Series of low prices, oldest first.
        closes: Series of close prices, oldest first.
        window: Half-window size for local extrema detection.
        cluster_pct: Percentage threshold for clustering nearby levels.
        max_levels: Maximum number of levels to return.

    Returns:
        List of SRLevel sorted by touch_count descending, up to max_levels.
        Empty list if fewer than 2*window+1 bars provided.
    """
    min_bars = 2 * window + 1
    n = len(highs)
    if n < min_bars or len(lows) < min_bars or len(closes) < min_bars:
        return []

    candidates: list[tuple[float, str]] = []

    # Find local minima in lows (support candidates)
    for i in range(window, n - window):
        segment = lows.iloc[i - window : i + window + 1]
        if lows.iloc[i] == segment.min():
            candidates.append((float(lows.iloc[i]), "support"))

    # Find local maxima in highs (resistance candidates)
    for i in range(window, n - window):
        segment = highs.iloc[i - window : i + window + 1]
        if highs.iloc[i] == segment.max():
            candidates.append((float(highs.iloc[i]), "resistance"))

    if not candidates:
        return []

    # Cluster nearby levels
    clusters: list[list[tuple[float, str]]] = []
    used = [False] * len(candidates)

    # Sort by price for efficient clustering
    indexed = sorted(enumerate(candidates), key=lambda x: x[1][0])

    for idx, (price, ltype) in indexed:
        if used[idx]:
            continue
        cluster = [(price, ltype)]
        used[idx] = True
        for idx2, (price2, ltype2) in indexed:
            if used[idx2]:
                continue
            avg_price = sum(p for p, _ in cluster) / len(cluster)
            if avg_price > 0 and abs(price2 - avg_price) / avg_price <= cluster_pct:
                cluster.append((price2, ltype2))
                used[idx2] = True
        clusters.append(cluster)

    # Build merged levels
    total_bars = n
    levels: list[SRLevel] = []
    for cluster in clusters:
        avg_price = sum(p for p, _ in cluster) / len(cluster)
        touch_count = len(cluster)
        support_count = sum(1 for _, lt in cluster if lt == "support")
        resistance_count = touch_count - support_count
        level_type = "support" if support_count >= resistance_count else "resistance"
        strength = round(touch_count / total_bars, 4)
        levels.append(
            SRLevel(
                price=round(avg_price, 4),
                level_type=level_type,
                touch_count=touch_count,
                strength=strength,
            )
        )

    # Sort by touch_count descending, limit to max_levels
    levels.sort(key=lambda lv: lv.touch_count, reverse=True)
    return levels[:max_levels]
