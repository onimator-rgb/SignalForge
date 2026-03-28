"""Anomaly explanation prompt template v1."""

VERSION = "v1.0"

SYSTEM = """\
You are a crypto market analyst assistant for MarketPulse AI.
Your job is to explain a specific market anomaly based ONLY on the data provided below.

Rules:
- Base your explanation ONLY on the provided context data.
- If data is insufficient, say so explicitly.
- Use cautious, analytical language. Describe what happened, not what will happen.
- Never give imperative financial advice.
- Write in clear, structured markdown.
- Keep the explanation under 400 words.
- Write in English.
"""


def build_user_prompt(context: dict) -> str:
    anomaly = context["anomaly"]
    asset = context["asset"]
    price = context.get("latest_price", {})
    indicators = context.get("indicators", {})

    details = anomaly.get("details", {})
    details_text = "\n".join(f"- {k}: {v}" for k, v in details.items())

    return f"""\
Explain the following market anomaly.

## Asset
- Symbol: {asset['symbol']}
- Name: {asset['name']}

## Anomaly
- Type: {anomaly['anomaly_type']}
- Severity: {anomaly['severity']}
- Score: {anomaly['score']}
- Detected at: {anomaly['detected_at']}
- Timeframe: {anomaly['timeframe']}

## Anomaly Details (metrics that triggered it)
{details_text}

## Current Price Context
- Close: ${price.get('close', 'N/A')}
- 24h change: {price.get('change_24h_pct', 'N/A')}%

## Current Indicators
- RSI(14): {indicators.get('rsi_14', 'N/A')}
- MACD histogram: {indicators.get('macd_histogram', 'N/A')}

Write the explanation with these sections:
1. **What Happened** — describe the anomaly in plain language
2. **Why It Was Flagged** — which metrics triggered detection
3. **Severity Assessment** — how serious does this look based on the data
4. **What to Monitor** — what to watch for next
"""
