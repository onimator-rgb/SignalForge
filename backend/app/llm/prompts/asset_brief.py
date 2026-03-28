"""Asset brief prompt template v2 — multi-asset aware."""

VERSION = "v2.0"

SYSTEM = """\
You are a financial market analyst assistant for MarketPulse AI.
Your job is to produce a concise asset briefing based ONLY on the data provided below.

Rules:
- Base your analysis ONLY on the provided context data. Do not reference external news or events.
- If data is insufficient, say so explicitly.
- Use cautious, analytical language. Describe signals and observations, not guarantees.
- Never give imperative financial advice (no "buy", "sell", "you should").
- Write in clear, structured markdown with headers.
- Keep the briefing under 600 words.
- Write in English.
- Adapt your language to the asset class (cryptocurrency vs stock).
"""


def build_user_prompt(context: dict) -> str:
    asset = context["asset"]
    price = context.get("latest_price", {})
    indicators = context.get("indicators", {})
    anomalies = context.get("recent_anomalies", [])
    ohlcv_summary = context.get("ohlcv_summary", {})

    asset_class = asset.get("asset_class", "crypto")
    asset_type_label = "stock" if asset_class == "stock" else "cryptocurrency"
    exchange_info = ""
    if asset.get("exchange"):
        exchange_info = f"\n- Exchange: {asset['exchange']}"
    if asset.get("currency"):
        exchange_info += f"\n- Currency: {asset['currency']}"

    anomaly_text = "None detected recently."
    if anomalies:
        lines = []
        for a in anomalies[:5]:
            lines.append(f"- {a['anomaly_type']} (severity={a['severity']}, score={a['score']})")
        anomaly_text = "\n".join(lines)

    return f"""\
Generate an asset briefing for the following {asset_type_label}.

## Asset
- Symbol: {asset['symbol']}
- Name: {asset['name']}
- Type: {asset_type_label}
- Market cap rank: {asset.get('market_cap_rank', 'N/A')}{exchange_info}

## Current Price
- Close: ${price.get('close', 'N/A')}
- 24h change: {price.get('change_24h_pct', 'N/A')}%
- Bar time: {price.get('bar_time', 'N/A')}

## OHLCV Summary (last 48 bars, 1h interval)
- High: ${ohlcv_summary.get('high', 'N/A')}
- Low: ${ohlcv_summary.get('low', 'N/A')}
- Avg volume: {ohlcv_summary.get('avg_volume', 'N/A')}

## Technical Indicators
- RSI(14): {indicators.get('rsi_14', 'N/A')}
- MACD: {indicators.get('macd', 'N/A')}
- Bollinger Bands: upper={indicators.get('bb_upper', 'N/A')}, middle={indicators.get('bb_middle', 'N/A')}, lower={indicators.get('bb_lower', 'N/A')}

## Recent Anomalies
{anomaly_text}

Write the briefing with these sections:
1. **Price Context** — current price position and recent trend
2. **Technical Signals** — what indicators suggest
3. **Anomaly Summary** — any flagged events and their significance
4. **Key Watchouts** — what to monitor going forward
"""
