"""Trade journal — pure formatting for closed positions into rich journal entries."""

from __future__ import annotations

from typing import Any


_CLOSE_REASON_LABELS: dict[str, str] = {
    "stop_loss": "Stop Loss Hit",
    "take_profit": "Take Profit Hit",
    "max_hold": "Max Hold Expired",
    "manual": "Manual Close",
}


def _close_reason_label(reason: str | None) -> str:
    """Map raw close_reason to a human-readable label."""
    if reason is None:
        return "Unknown"
    return _CLOSE_REASON_LABELS.get(reason, reason.replace("_", " ").title())


def _pnl_class(pnl: float | None) -> str:
    if pnl is None:
        return "breakeven"
    if pnl > 0:
        return "profit"
    if pnl < 0:
        return "loss"
    return "breakeven"


def format_journal_entry(
    position: Any,
    transactions: list[Any],
) -> dict[str, Any]:
    """Format a single closed position into a journal entry dict.

    Works with ORM objects or any duck-typed object with the expected attributes.
    """
    opened_at = position.opened_at
    closed_at = getattr(position, "closed_at", None)

    hold_duration_hours: float | None = None
    if opened_at is not None and closed_at is not None:
        hold_duration_hours = (closed_at - opened_at).total_seconds() / 3600

    exit_context: dict[str, Any] | None = getattr(position, "exit_context", None)
    entry_signals: dict[str, Any] | None = None
    exit_signals: dict[str, Any] | None = None
    if exit_context and isinstance(exit_context, dict):
        entry_signals = exit_context.get("entry_snapshot")
        exit_signals = exit_context.get("exit_snapshot")

    tx_list = [
        {
            "tx_type": tx.tx_type,
            "price": float(tx.price),
            "quantity": float(tx.quantity),
            "value_usd": float(tx.value_usd),
            "executed_at": tx.executed_at.isoformat() if tx.executed_at else None,
        }
        for tx in transactions
    ]

    close_reason = getattr(position, "close_reason", None)
    realized_pnl_usd = getattr(position, "realized_pnl_usd", None)
    realized_pnl_pct = getattr(position, "realized_pnl_pct", None)
    exit_price = getattr(position, "exit_price", None)
    exit_value_usd = getattr(position, "exit_value_usd", None)

    return {
        "position_id": str(position.id),
        "symbol": getattr(position, "symbol", None) or str(position.asset_id),
        "entry_price": float(position.entry_price),
        "exit_price": float(exit_price) if exit_price is not None else None,
        "quantity": float(position.quantity),
        "entry_value_usd": float(position.entry_value_usd),
        "exit_value_usd": float(exit_value_usd) if exit_value_usd is not None else None,
        "realized_pnl_usd": float(realized_pnl_usd) if realized_pnl_usd is not None else None,
        "realized_pnl_pct": float(realized_pnl_pct) if realized_pnl_pct is not None else None,
        "pnl_class": _pnl_class(float(realized_pnl_usd) if realized_pnl_usd is not None else None),
        "close_reason": close_reason,
        "close_reason_label": _close_reason_label(close_reason),
        "opened_at": opened_at.isoformat() if opened_at else None,
        "closed_at": closed_at.isoformat() if closed_at else None,
        "hold_duration_hours": round(hold_duration_hours, 4) if hold_duration_hours is not None else None,
        "entry_signals": entry_signals,
        "exit_signals": exit_signals,
        "transactions": tx_list,
    }


def format_journal(
    positions: list[Any],
    transactions_by_position: dict[str, list[Any]],
) -> list[dict[str, Any]]:
    """Format multiple closed positions, sorted by closed_at descending."""
    entries = [
        format_journal_entry(pos, transactions_by_position.get(str(pos.id), []))
        for pos in positions
    ]
    entries.sort(key=lambda e: e["closed_at"] or "", reverse=True)
    return entries
