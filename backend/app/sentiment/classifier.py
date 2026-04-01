"""Keyword-based sentiment classifier for financial headlines."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class SentimentResult:
    score: float
    label: str
    matched_words: list[str] = field(default_factory=list)


POSITIVE_WORDS: set[str] = {
    "bullish", "surge", "rally", "gains", "soars",
    "breakout", "upgrade", "adoption", "growth", "recovery",
    "optimistic", "profit", "buy", "boost", "milestone",
    "approval", "partnership", "innovation", "record", "momentum",
}

NEGATIVE_WORDS: set[str] = {
    "bearish", "crash", "plunge", "decline", "loss",
    "dump", "hack", "ban", "fraud", "lawsuit",
    "risk", "sell", "warning", "fear", "downturn",
    "recession", "default", "bankruptcy", "scam", "volatility",
}


def classify_headline(headline: str) -> SentimentResult:
    """Score a single headline using keyword matching."""
    words = headline.lower().split()
    matched_positive = [w for w in words if w in POSITIVE_WORDS]
    matched_negative = [w for w in words if w in NEGATIVE_WORDS]

    pos_count = len(matched_positive)
    neg_count = len(matched_negative)
    total = pos_count + neg_count

    score = (pos_count - neg_count) / max(total, 1)
    score = max(-1.0, min(1.0, score))

    if score > 0.1:
        label = "positive"
    elif score < -0.1:
        label = "negative"
    else:
        label = "neutral"

    return SentimentResult(
        score=score,
        label=label,
        matched_words=matched_positive + matched_negative,
    )


def classify_batch(headlines: list[str], symbol: str | None = None) -> SentimentResult:
    """Classify multiple headlines and return an aggregated result."""
    if symbol is not None:
        sym_lower = symbol.lower()
        headlines = [h for h in headlines if sym_lower in h.lower()]

    if not headlines:
        return SentimentResult(score=0.0, label="neutral", matched_words=[])

    results = [classify_headline(h) for h in headlines]
    avg_score = sum(r.score for r in results) / len(results)
    avg_score = max(-1.0, min(1.0, avg_score))

    all_matched: list[str] = []
    for r in results:
        all_matched.extend(r.matched_words)

    if avg_score > 0.1:
        label = "positive"
    elif avg_score < -0.1:
        label = "negative"
    else:
        label = "neutral"

    return SentimentResult(score=avg_score, label=label, matched_words=all_matched)
