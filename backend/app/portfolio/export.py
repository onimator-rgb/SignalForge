"""Trade journal CSV export — pure formatting function."""

from __future__ import annotations

import csv
import io
from typing import Any

CSV_COLUMNS: list[str] = [
    "symbol",
    "entry_price",
    "exit_price",
    "quantity",
    "entry_value_usd",
    "exit_value_usd",
    "realized_pnl_usd",
    "realized_pnl_pct",
    "close_reason",
    "opened_at",
    "closed_at",
    "hold_duration_hours",
]


def format_journal_csv(entries: list[dict[str, Any]]) -> str:
    """Convert journal entry dicts into a CSV string.

    Takes the output of ``format_journal()`` and returns a CSV with a header
    row followed by one data row per entry.  ``None`` values are written as
    empty strings.
    """
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(CSV_COLUMNS)
    for entry in entries:
        row = [entry.get(col) if entry.get(col) is not None else "" for col in CSV_COLUMNS]
        writer.writerow(row)
    return buf.getvalue()
