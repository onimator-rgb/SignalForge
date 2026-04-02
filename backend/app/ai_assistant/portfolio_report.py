"""Pure-logic portfolio analysis report generator.

Produces a multi-section plain-text report from portfolio positions,
risk metrics, recent trades, and market regime.  No LLM calls — uses
template-based string formatting.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PositionSummary:
    symbol: str
    entry_price: float
    current_price: float | None
    quantity: float
    unrealized_pnl_pct: float | None
    status: str  # "open" | "closed"
    close_reason: str | None = None
    realized_pnl_pct: float | None = None


@dataclass(frozen=True)
class RiskSnapshot:
    sharpe_ratio: float | None
    sortino_ratio: float | None
    max_drawdown_pct: float
    profit_factor: float | None
    win_rate: float | None
    total_closed: int
    wins: int
    losses: int
    avg_hold_hours: float
    best_trade_pct: float | None = None
    worst_trade_pct: float | None = None


@dataclass(frozen=True)
class TradeSummary:
    symbol: str
    action: str  # "buy" | "sell"
    price: float
    quantity: float
    value_usd: float


def _fmt(value: float | None, suffix: str = "") -> str:
    if value is None:
        return "N/A"
    return f"{value:.2f}{suffix}"


def _portfolio_summary(
    positions: list[PositionSummary],
    current_cash: float,
    initial_capital: float,
) -> str:
    open_positions = [p for p in positions if p.status == "open"]
    closed_positions = [p for p in positions if p.status == "closed"]

    open_value = sum(
        (p.current_price if p.current_price is not None else p.entry_price) * p.quantity
        for p in open_positions
    )
    total_value = current_cash + open_value

    if initial_capital == 0:
        total_return_pct = 0.0
        utilization_pct = 0.0
    else:
        total_return_pct = (total_value - initial_capital) / initial_capital * 100
        utilization_pct = open_value / initial_capital * 100

    lines = [
        "PORTFOLIO SUMMARY",
        "=" * 40,
        f"Open positions: {len(open_positions)}",
        f"Closed positions: {len(closed_positions)}",
        f"Total return: {total_return_pct:.2f}%",
        f"Cash remaining: ${current_cash:.2f}",
        f"Capital utilization: {utilization_pct:.2f}%",
    ]
    return "\n".join(lines)


def _open_positions_section(positions: list[PositionSummary]) -> str:
    open_positions = [p for p in positions if p.status == "open"]
    lines = ["OPEN POSITIONS", "=" * 40]
    if not open_positions:
        lines.append("No open positions.")
        return "\n".join(lines)
    for p in open_positions:
        current = _fmt(p.current_price, "")
        pnl = _fmt(p.unrealized_pnl_pct, "%")
        lines.append(
            f"  {p.symbol}: entry ${p.entry_price:.2f}, "
            f"current ${current}, unrealized P&L {pnl}"
        )
    return "\n".join(lines)


def _sharpe_interpretation(sharpe: float | None) -> str:
    if sharpe is None:
        return "Sharpe ratio: N/A (insufficient data)."
    if sharpe > 2.0:
        return f"Your Sharpe ratio of {sharpe:.2f} indicates excellent risk-adjusted returns."
    if sharpe > 1.0:
        return f"Your Sharpe ratio of {sharpe:.2f} indicates good risk-adjusted returns."
    if sharpe < 0:
        return f"Your Sharpe ratio of {sharpe:.2f} indicates poor risk-adjusted returns."
    return f"Your Sharpe ratio of {sharpe:.2f} indicates moderate risk-adjusted returns."


def _drawdown_assessment(dd_pct: float) -> str:
    if dd_pct > 25:
        return f"Max drawdown of {dd_pct:.2f}% is critical — significant capital at risk."
    if dd_pct > 15:
        return f"Max drawdown of {dd_pct:.2f}% is a warning — monitor risk exposure closely."
    return f"Max drawdown of {dd_pct:.2f}% is within acceptable limits."


def _profit_factor_comment(pf: float | None) -> str:
    if pf is None:
        return "Profit factor: N/A (insufficient data)."
    if pf > 1.0:
        return f"Profit factor of {pf:.2f} — gains outweigh losses."
    return f"Profit factor of {pf:.2f} — losses outweigh gains."


def _risk_assessment(risk: RiskSnapshot) -> str:
    lines = [
        "RISK ASSESSMENT",
        "=" * 40,
        _sharpe_interpretation(risk.sharpe_ratio),
        _drawdown_assessment(risk.max_drawdown_pct),
        _profit_factor_comment(risk.profit_factor),
        f"Win rate: {_fmt(risk.win_rate, '%')} ({risk.wins}W / {risk.losses}L of {risk.total_closed} closed).",
    ]
    return "\n".join(lines)


def _recent_activity(trades: list[TradeSummary]) -> str:
    lines = ["RECENT ACTIVITY", "=" * 40]
    if not trades:
        lines.append("No recent trades.")
        return "\n".join(lines)
    for t in trades[:5]:
        lines.append(
            f"  {t.action.upper()} {t.symbol}: {t.quantity:.2f} @ ${t.price:.2f} (${t.value_usd:.2f})"
        )
    return "\n".join(lines)


_REGIME_TEXT = {
    "bullish": "Market regime is bullish — favorable conditions for maintaining positions.",
    "bearish": "Market regime is bearish — consider tightening stop-losses and reducing exposure.",
    "neutral": "Market regime is neutral — maintain current strategy and watch for trend signals.",
}


def _regime_commentary(regime: str) -> str:
    lines = [
        "REGIME COMMENTARY",
        "=" * 40,
        _REGIME_TEXT.get(regime, f"Unknown regime '{regime}' — no specific guidance available."),
    ]
    return "\n".join(lines)


def generate_portfolio_report(
    positions: list[PositionSummary],
    risk: RiskSnapshot,
    recent_trades: list[TradeSummary],
    regime: str,
    current_cash: float,
    initial_capital: float,
) -> str:
    """Generate a multi-section plain-text portfolio analysis report."""
    sections = [
        _portfolio_summary(positions, current_cash, initial_capital),
        _open_positions_section(positions),
        _risk_assessment(risk),
        _recent_activity(recent_trades),
        _regime_commentary(regime),
    ]
    return "\n\n".join(sections) + "\n"
