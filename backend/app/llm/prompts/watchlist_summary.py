"""Watchlist summary prompt template v1 — personalized watchlist intelligence."""

VERSION = "v1.0"

SYSTEM = """\
You are a financial market analyst assistant for MarketPulse AI.
Your job is to produce a concise watchlist summary based ONLY on the data provided below.

Rules:
- Base your analysis ONLY on the provided context data.
- If data is insufficient, say so explicitly.
- Use cautious, analytical language. This is a demo/educational tool.
- Never give imperative financial advice (no "buy", "sell", "you should").
- Write in clear, structured markdown with headers.
- Keep the summary under 500 words.
- Write in English.
- Focus on the specific watchlist provided.
"""


def build_user_prompt(context: dict) -> str:
    wl = context.get("watchlist", {})
    assets = context.get("assets", [])
    recs = context.get("recommendations", [])
    portfolio_overlap = context.get("portfolio_overlap", [])
    anomalies = context.get("anomalies", [])

    assets_text = "None."
    if assets:
        lines = []
        for a in assets[:15]:
            price = f"${a['price']:.2f}" if a.get('price') else "N/A"
            chg = f"{a['change_24h_pct']:+.1f}%" if a.get('change_24h_pct') is not None else "N/A"
            lines.append(f"- {a['symbol']} [{a['asset_class']}]: {price} ({chg})")
        assets_text = "\n".join(lines)

    recs_text = "No active recommendations."
    if recs:
        lines = []
        for r in recs[:10]:
            lines.append(f"- {r['symbol']}: {r['type']} (score={r['score']:.0f}, conf={r['confidence']}, risk={r['risk']})")
        recs_text = "\n".join(lines)

    portfolio_text = "None in portfolio."
    if portfolio_overlap:
        lines = [f"- {p['symbol']}: {p['pnl_pct']:+.2f}%" for p in portfolio_overlap]
        portfolio_text = "\n".join(lines)

    anomalies_text = "No active anomalies."
    if anomalies:
        lines = [f"- {a['symbol']}: {a['type']} ({a['severity']})" for a in anomalies[:10]]
        anomalies_text = "\n".join(lines)

    return f"""\
Generate a summary for the watchlist: "{wl.get('name', 'Watchlist')}".

## Watchlist Overview
- Total assets: {wl.get('total', 0)}
- Crypto: {wl.get('crypto', 0)} | Stocks: {wl.get('stock', 0)}

## Assets
{assets_text}

## Active Recommendations
{recs_text}

## Portfolio Overlap
{portfolio_text}

## Active Anomalies
{anomalies_text}

Write the summary with these sections:
1. **Watchlist Overview** — composition and current state
2. **Strongest Signals** — which assets show the most promising technical setup
3. **Risk Factors** — which assets carry elevated risk or negative signals
4. **Portfolio Context** — overlap with demo portfolio positions
5. **Key Watchouts** — what to monitor going forward
"""
