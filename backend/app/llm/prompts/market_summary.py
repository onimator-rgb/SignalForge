"""Market summary prompt template v2 — multi-asset aware."""

VERSION = "v2.0"

SYSTEM = """\
You are a financial market analyst assistant for MarketPulse AI.
Your job is to produce a concise market overview based ONLY on the data provided below.
The platform monitors both cryptocurrencies and stocks.

Rules:
- Base your analysis ONLY on the provided context data.
- If data is insufficient, say so explicitly.
- Use cautious, analytical language.
- Never give imperative financial advice.
- Write in clear, structured markdown.
- Keep the summary under 500 words.
- Write in English.
"""


def build_user_prompt(context: dict) -> str:
    top_movers = context.get("top_movers", [])
    anomaly_stats = context.get("anomaly_stats", {})
    active_anomalies = context.get("active_anomalies", [])
    asset_count = context.get("asset_count", 0)

    movers_text = "No data available."
    if top_movers:
        lines = []
        for m in top_movers[:10]:
            chg = m.get('change_24h_pct', 'N/A')
            class_tag = f"[{m.get('asset_class', '?')}]" if m.get('asset_class') else ""
            lines.append(
                f"- {m['symbol']} {class_tag}: ${m['close']} "
                f"({'+' if isinstance(chg, (int, float)) and chg >= 0 else ''}{chg}%)"
            )
        movers_text = "\n".join(lines)

    anomalies_text = "No active anomalies."
    if active_anomalies:
        lines = []
        for a in active_anomalies[:10]:
            class_tag = f"[{a.get('asset_class', '?')}]" if a.get('asset_class') else ""
            lines.append(
                f"- {a['asset_symbol']} {class_tag}: "
                f"{a['anomaly_type']} (severity={a['severity']})"
            )
        anomalies_text = "\n".join(lines)

    return f"""\
Generate a market overview for all monitored assets (crypto and stocks).

## Market Scope
- Tracked assets: {asset_count}
- Total anomalies detected: {anomaly_stats.get('total', 0)}
- Active (unresolved) anomalies: {anomaly_stats.get('unresolved', 0)}

## Top Movers (24h change)
{movers_text}

## Active Anomalies
{anomalies_text}

Write the summary with these sections:
1. **Market Overview** — general state of the monitored assets across crypto and stocks
2. **Notable Movers** — which assets stand out and why
3. **Anomaly Signals** — active anomalies and what they suggest
4. **Market Outlook** — cautious interpretation of the signals
"""
