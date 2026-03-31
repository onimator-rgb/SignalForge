"""Local template-based report provider — no external API calls."""

from __future__ import annotations

from .base import BaseLLMProvider, LLMResponse


def _fmt_price(val) -> str:
    if val is None:
        return "N/A"
    return f"${val:,.2f}" if isinstance(val, (int, float)) else f"${val}"


def _fmt_pct(val) -> str:
    if val is None:
        return "N/A"
    v = float(val)
    sign = "+" if v >= 0 else ""
    return f"{sign}{v:.2f}%"


def _rsi_interpretation(rsi) -> str:
    if rsi is None:
        return "Brak danych RSI."
    rsi = float(rsi)
    if rsi >= 80:
        return f"RSI ({rsi:.1f}) wskazuje na **silne wykupienie**."
    if rsi >= 70:
        return f"RSI ({rsi:.1f}) wskazuje na **wykupienie**."
    if rsi <= 20:
        return f"RSI ({rsi:.1f}) wskazuje na **silne wyprzedanie**."
    if rsi <= 30:
        return f"RSI ({rsi:.1f}) wskazuje na **wyprzedanie**."
    return f"RSI ({rsi:.1f}) jest w **strefie neutralnej**."


def _severity_label(severity: str) -> str:
    return {"low": "niska", "medium": "umiarkowana", "high": "wysoka", "critical": "krytyczna"}.get(severity, severity)


def _anomaly_type_label(atype: str) -> str:
    labels = {
        "price_spike": "Gwaltowna zmiana ceny",
        "volume_surge": "Skok wolumenu",
        "rsi_extreme": "Ekstremalny RSI",
        "price_drop": "Gwaltowny spadek ceny",
        "volatility_spike": "Skok zmiennosci",
    }
    return labels.get(atype, atype.replace("_", " ").title())


def _generate_asset_brief(ctx: dict) -> str:
    asset = ctx["asset"]
    price = ctx.get("latest_price", {})
    indicators = ctx.get("indicators", {})
    anomalies = ctx.get("recent_anomalies", [])
    ohlcv = ctx.get("ohlcv_summary", {})
    asset_type = "Akcja" if asset.get("asset_class") == "stock" else "Kryptowaluta"
    rsi = indicators.get("rsi_14")
    change = price.get("change_24h_pct")
    trend = "brak danych"
    if change is not None:
        change = float(change)
        if change > 5: trend = "silny wzrost"
        elif change > 1: trend = "umiarkowany wzrost"
        elif change > -1: trend = "stabilizacja"
        elif change > -5: trend = "umiarkowany spadek"
        else: trend = "silny spadek"

    anomaly_lines = "Brak wykrytych anomalii."
    if anomalies:
        items = [f"- **{_anomaly_type_label(a['anomaly_type'])}** — waznosc: {_severity_label(a['severity'])}, score: {a['score']:.2f}" for a in anomalies[:5]]
        anomaly_lines = "\n".join(items)

    return f"""# Briefing: {asset['symbol']} ({asset['name']})

**Typ:** {asset_type} | **Ranking:** {asset.get('market_cap_rank', 'N/A')}

## Kontekst cenowy
| Metryka | Wartosc |
|---------|---------|
| Cena | {_fmt_price(price.get('close'))} |
| Zmiana 24h | {_fmt_pct(price.get('change_24h_pct'))} |
| Maks. 48h | {_fmt_price(ohlcv.get('high'))} |
| Min. 48h | {_fmt_price(ohlcv.get('low'))} |

**Trend:** {trend}

## Sygnaly techniczne
{_rsi_interpretation(rsi)}
**MACD:** {indicators.get('macd', 'Brak danych')}

## Anomalie
{anomaly_lines}

---
*Raport wygenerowany automatycznie. Nie stanowi porady inwestycyjnej.*
"""


def _generate_anomaly_explanation(ctx: dict) -> str:
    anomaly = ctx["anomaly"]
    asset = ctx["asset"]
    price = ctx.get("latest_price", {})
    indicators = ctx.get("indicators", {})
    sev = anomaly.get("severity", "medium")
    sev_text = {"critical": "Sytuacja wymaga natychmiastowej uwagi.", "high": "Anomalia o wysokiej waznosci.", "medium": "Anomalia o umiarkowanej waznosci.", "low": "Anomalia o niskiej waznosci."}.get(sev, "")
    details = anomaly.get("details", {})
    details_lines = "\n".join(f"- **{k}:** {v}" for k, v in details.items()) if details else "Brak szczegolowych metryk."

    return f"""# Anomalia: {_anomaly_type_label(anomaly['anomaly_type'])} — {asset['symbol']}

**Wykryto:** {anomaly['detected_at']} | **Score:** {anomaly['score']:.2f} | **Waznosc:** {_severity_label(anomaly['severity'])}

## Co sie stalo
Wykryto anomalie typu **{_anomaly_type_label(anomaly['anomaly_type'])}** dla {asset['symbol']}.

## Metryki
{details_lines}

## Ocena
{sev_text}
Cena: {_fmt_price(price.get('close'))}, zmiana 24h: {_fmt_pct(price.get('change_24h_pct'))}.
{_rsi_interpretation(indicators.get('rsi_14'))}

---
*Raport wygenerowany automatycznie. Nie stanowi porady inwestycyjnej.*
"""


def _generate_market_summary(ctx: dict) -> str:
    top_movers = ctx.get("top_movers", [])
    anomaly_stats = ctx.get("anomaly_stats", {})
    active_anomalies = ctx.get("active_anomalies", [])
    asset_count = ctx.get("asset_count", 0)
    unresolved = anomaly_stats.get("unresolved", 0)

    movers_rows = ""
    for m in top_movers[:10]:
        cls = "Crypto" if m.get("asset_class") == "crypto" else "Stock"
        movers_rows += f"| {m['symbol']} | {cls} | {_fmt_price(m.get('close'))} | {_fmt_pct(m.get('change_24h_pct'))} |\n"

    anom_lines = "Brak aktywnych anomalii."
    if active_anomalies:
        anom_lines = "\n".join(f"- **{a['asset_symbol']}**: {_anomaly_type_label(a['anomaly_type'])} ({_severity_label(a['severity'])})" for a in active_anomalies[:10])

    return f"""# Przeglad rynku

**Monitorowane aktywa:** {asset_count} | **Anomalie aktywne:** {unresolved}

## Najaktywniejsze aktywa (24h)
| Symbol | Typ | Cena | Zmiana 24h |
|--------|-----|------|------------|
{movers_rows}
## Aktywne anomalie
{anom_lines}

---
*Raport wygenerowany automatycznie. Nie stanowi porady inwestycyjnej.*
"""


def _generate_watchlist_summary(ctx: dict) -> str:
    wl = ctx.get("watchlist", {})
    assets = ctx.get("assets", [])
    recs = ctx.get("recommendations", [])
    portfolio_overlap = ctx.get("portfolio_overlap", [])
    anomalies = ctx.get("anomalies", [])

    assets_rows = ""
    for a in assets[:15]:
        cls = "Crypto" if a.get("asset_class") == "crypto" else "Stock"
        assets_rows += f"| {a['symbol']} | {cls} | {_fmt_price(a.get('price'))} | {_fmt_pct(a.get('change_24h_pct'))} |\n"

    recs_lines = "Brak aktywnych rekomendacji."
    if recs:
        recs_lines = "\n".join(f"- **{r['symbol']}**: {r['type']} (score: {r['score']:.0f}, ryzyko: {r['risk']})" for r in recs[:10])

    port_lines = "Brak pokrycia z portfelem."
    if portfolio_overlap:
        port_lines = "\n".join(f"- **{p['symbol']}**: P/L {p['pnl_pct']:+.2f}%" for p in portfolio_overlap)

    anom_lines = "Brak aktywnych anomalii."
    if anomalies:
        anom_lines = "\n".join(f"- **{a['symbol']}**: {_anomaly_type_label(a['type'])} ({_severity_label(a['severity'])})" for a in anomalies[:10])

    return f"""# Watchlist: {wl.get('name', 'Watchlist')}

**Aktywa:** {wl.get('total', 0)} (Crypto: {wl.get('crypto', 0)} | Akcje: {wl.get('stock', 0)})

## Aktywa
| Symbol | Typ | Cena | Zmiana 24h |
|--------|-----|------|------------|
{assets_rows}
## Rekomendacje
{recs_lines}

## Anomalie
{anom_lines}

## Portfel
{port_lines}

---
*Raport wygenerowany automatycznie. Nie stanowi porady inwestycyjnej.*
"""


GENERATORS = {
    "asset_brief": _generate_asset_brief,
    "anomaly_explanation": _generate_anomaly_explanation,
    "market_summary": _generate_market_summary,
    "watchlist_summary": _generate_watchlist_summary,
}


class LocalTemplateProvider(BaseLLMProvider):
    """Generates reports from structured templates — no external API needed."""

    @property
    def provider_name(self) -> str:
        return "local"

    async def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        model: str | None = None,
        temperature: float = 0.3,
        max_tokens: int = 4000,
        *,
        report_type: str = "",
        context: dict | None = None,
    ) -> LLMResponse:
        if report_type and context and report_type in GENERATORS:
            content = GENERATORS[report_type](context)
        else:
            content = "Raport nie mogl zostac wygenerowany."

        return LLMResponse(
            content=content,
            model="local-template-v1",
            provider="local",
            input_tokens=0,
            output_tokens=0,
        )
