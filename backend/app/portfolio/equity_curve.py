"""Equity curve computation — pure function + Pydantic schema."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from pydantic import BaseModel


@dataclass(frozen=True)
class EquityPoint:
    """Single point on the equity curve."""

    timestamp: datetime
    equity: float
    cash: float
    positions_value: float
    drawdown_pct: float
    trade_number: int


def build_equity_curve(
    transactions: list[dict[str, object]],
    initial_capital: float = 1000.0,
) -> list[EquityPoint]:
    """Replay transactions chronologically and compute cumulative equity.

    Args:
        transactions: list of dicts with keys tx_type ('buy'|'sell'),
            value_usd (float), executed_at (datetime).
        initial_capital: starting cash value.

    Returns:
        List of EquityPoint, starting with an initial point.
    """
    sorted_txs = sorted(transactions, key=lambda t: str(t["executed_at"]))

    # Initial point: 1s before first tx, or epoch if empty
    if sorted_txs:
        first_ts: datetime = sorted_txs[0]["executed_at"]  # type: ignore[assignment]
        init_ts = first_ts - timedelta(seconds=1)
    else:
        init_ts = datetime(1970, 1, 1, tzinfo=timezone.utc)

    points: list[EquityPoint] = [
        EquityPoint(
            timestamp=init_ts,
            equity=initial_capital,
            cash=initial_capital,
            positions_value=0.0,
            drawdown_pct=0.0,
            trade_number=0,
        )
    ]

    cash = initial_capital
    positions_value = 0.0
    peak = initial_capital

    for i, tx in enumerate(sorted_txs, start=1):
        tx_type: str = tx["tx_type"]  # type: ignore[assignment]
        value_usd: float = float(tx["value_usd"])  # type: ignore[arg-type]
        executed_at: datetime = tx["executed_at"]  # type: ignore[assignment]

        if tx_type == "buy":
            cash -= value_usd
            positions_value += value_usd
        elif tx_type == "sell":
            cash += value_usd
            positions_value -= min(value_usd, positions_value)

        equity = cash + positions_value
        if equity > peak:
            peak = equity
        drawdown_pct = (equity - peak) / peak if peak != 0 else 0.0

        points.append(
            EquityPoint(
                timestamp=executed_at,
                equity=round(equity, 2),
                cash=round(cash, 2),
                positions_value=round(positions_value, 2),
                drawdown_pct=round(drawdown_pct, 6),
                trade_number=i,
            )
        )

    return points


class EquityCurveOut(BaseModel):
    """Response schema for GET /equity-curve."""

    points: list[dict[str, object]]
    total_points: int
    current_equity: float
    max_drawdown_pct: float
