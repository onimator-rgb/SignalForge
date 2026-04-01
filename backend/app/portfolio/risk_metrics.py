"""Pure-function risk metrics computation for closed portfolio positions."""

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime


@dataclass
class RiskMetricsResult:
    """Computed risk and performance metrics from closed positions."""

    sharpe_ratio: float | None
    sortino_ratio: float | None
    max_drawdown_pct: float
    profit_factor: float | None
    avg_hold_hours: float
    total_closed: int
    wins: int
    losses: int
    win_rate: float | None
    avg_win_pct: float | None
    avg_loss_pct: float | None
    best_trade_pct: float | None
    worst_trade_pct: float | None
    breakdown_by_reason: dict[str, int] = field(default_factory=dict)


def _compute_daily_returns(positions: list[object]) -> list[float]:
    """Group positions by closed_at date and sum daily returns as fractions.

    Positions without closed_at are skipped. Returns sorted by date.
    """
    daily: dict[date, float] = defaultdict(float)
    for pos in positions:
        closed_at: datetime | None = getattr(pos, "closed_at", None)
        pnl_pct = getattr(pos, "realized_pnl_pct", None)
        if closed_at is None or pnl_pct is None:
            continue
        day = closed_at.date()
        daily[day] += float(pnl_pct) / 100.0
    return [daily[d] for d in sorted(daily)]


def compute_risk_metrics(
    positions: list[object],
    risk_free_rate: float = 0.0,
) -> RiskMetricsResult:
    """Compute risk metrics from closed portfolio positions.

    Each position must have: realized_pnl_pct (float|None), realized_pnl_usd (float|None),
    closed_at (datetime|None), opened_at (datetime), close_reason (str|None).
    """
    total_closed = len(positions)

    if total_closed == 0:
        return RiskMetricsResult(
            sharpe_ratio=None,
            sortino_ratio=None,
            max_drawdown_pct=0.0,
            profit_factor=None,
            avg_hold_hours=0.0,
            total_closed=0,
            wins=0,
            losses=0,
            win_rate=None,
            avg_win_pct=None,
            avg_loss_pct=None,
            best_trade_pct=None,
            worst_trade_pct=None,
            breakdown_by_reason={},
        )

    # Extract returns as fractions (e.g. 5% -> 0.05)
    returns: list[float] = []
    pnl_values: list[float] = []
    hold_hours: list[float] = []
    breakdown: dict[str, int] = {}
    wins = 0
    losses = 0

    for pos in positions:
        pnl_pct = getattr(pos, "realized_pnl_pct", None)
        pnl_usd = getattr(pos, "realized_pnl_usd", None)
        closed_at: datetime | None = getattr(pos, "closed_at", None)
        opened_at: datetime | None = getattr(pos, "opened_at", None)
        close_reason: str | None = getattr(pos, "close_reason", None)

        if pnl_pct is not None:
            ret = float(pnl_pct) / 100.0
            returns.append(ret)

        if pnl_usd is not None:
            val = float(pnl_usd)
            pnl_values.append(val)
            if val > 0:
                wins += 1
            elif val < 0:
                losses += 1

        if closed_at is not None and opened_at is not None:
            delta = (closed_at - opened_at).total_seconds() / 3600.0
            hold_hours.append(delta)

        reason = close_reason or "unknown"
        breakdown[reason] = breakdown.get(reason, 0) + 1

    # Sharpe ratio (annualized, 252 trading days, using daily returns)
    sharpe: float | None = None
    daily_returns = _compute_daily_returns(positions)
    if len(daily_returns) >= 2:
        mean_daily = sum(daily_returns) / len(daily_returns)
        std_daily = _std(daily_returns)
        if std_daily > 0:
            sharpe = (mean_daily - risk_free_rate / 252) / std_daily * math.sqrt(252)

    # Sortino ratio (annualized, 365 days)
    sortino: float | None = None
    if len(returns) >= 2:
        mean_ret = sum(returns) / len(returns)
        downside_std = _downside_std(returns)
        if downside_std > 0:
            sortino = (mean_ret / downside_std) * math.sqrt(365)

    # Max drawdown from cumulative PnL sequence ordered by closed_at
    max_dd = _max_drawdown(positions)

    # Profit factor
    profit_factor: float | None = None
    if pnl_values:
        gross_profit = sum(v for v in pnl_values if v > 0)
        gross_loss = abs(sum(v for v in pnl_values if v < 0))
        if gross_loss > 0:
            profit_factor = gross_profit / gross_loss

    # Average hold duration
    avg_hold = sum(hold_hours) / len(hold_hours) if hold_hours else 0.0

    # Win rate
    win_rate: float | None = None
    if wins + losses > 0:
        win_rate = (wins / (wins + losses)) * 100.0

    # Avg win/loss and best/worst trade (based on realized_pnl_pct)
    all_pnl_pcts: list[float] = [
        float(getattr(p, "realized_pnl_pct", None))  # type: ignore[arg-type]
        for p in positions
        if getattr(p, "realized_pnl_pct", None) is not None
    ]
    win_pcts = [v for v in all_pnl_pcts if v > 0]
    loss_pcts = [v for v in all_pnl_pcts if v < 0]

    avg_win_pct = round(sum(win_pcts) / len(win_pcts), 4) if win_pcts else None
    avg_loss_pct = round(sum(loss_pcts) / len(loss_pcts), 4) if loss_pcts else None
    best_trade_pct = round(max(all_pnl_pcts), 4) if all_pnl_pcts else None
    worst_trade_pct = round(min(all_pnl_pcts), 4) if all_pnl_pcts else None

    return RiskMetricsResult(
        sharpe_ratio=round(sharpe, 4) if sharpe is not None else None,
        sortino_ratio=round(sortino, 4) if sortino is not None else None,
        max_drawdown_pct=round(max_dd, 4),
        profit_factor=round(profit_factor, 4) if profit_factor is not None else None,
        avg_hold_hours=round(avg_hold, 2),
        total_closed=total_closed,
        wins=wins,
        losses=losses,
        win_rate=round(win_rate, 2) if win_rate is not None else None,
        avg_win_pct=avg_win_pct,
        avg_loss_pct=avg_loss_pct,
        best_trade_pct=best_trade_pct,
        worst_trade_pct=worst_trade_pct,
        breakdown_by_reason=breakdown,
    )


def _std(values: list[float]) -> float:
    """Population standard deviation."""
    n = len(values)
    if n < 2:
        return 0.0
    mean = sum(values) / n
    variance = sum((x - mean) ** 2 for x in values) / (n - 1)
    return math.sqrt(variance)


def _downside_std(returns: list[float]) -> float:
    """Downside deviation (semi-deviation of negative returns)."""
    n = len(returns)
    if n < 2:
        return 0.0
    downside_sq = [(min(r, 0.0)) ** 2 for r in returns]
    return math.sqrt(sum(downside_sq) / (n - 1))


def _max_drawdown(positions: list[object]) -> float:
    """Max drawdown % from cumulative PnL sequence ordered by closed_at."""
    # Sort by closed_at
    sorted_pos = sorted(
        positions,
        key=lambda p: getattr(p, "closed_at", None) or datetime.min,
    )

    cum_pnl = 0.0
    peak = 0.0
    max_dd = 0.0

    for pos in sorted_pos:
        pnl_usd = getattr(pos, "realized_pnl_usd", None)
        if pnl_usd is not None:
            cum_pnl += float(pnl_usd)
        if cum_pnl > peak:
            peak = cum_pnl
        drawdown = peak - cum_pnl
        if drawdown > max_dd:
            max_dd = drawdown

    # Express as percentage of peak (if peak > 0)
    if peak > 0:
        return (max_dd / peak) * 100.0
    elif max_dd > 0:
        # All losses — 100% drawdown from zero
        return 100.0
    return 0.0
