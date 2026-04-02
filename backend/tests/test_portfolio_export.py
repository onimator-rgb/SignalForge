"""Tests for portfolio trade journal CSV export."""

from __future__ import annotations

import csv
import io

from app.portfolio.export import CSV_COLUMNS, format_journal_csv


def _sample_entry(**overrides: object) -> dict:
    """Return a realistic journal entry dict (matches format_journal output)."""
    base: dict = {
        "position_id": "pos-1",
        "symbol": "BTC-USD",
        "entry_price": 50000.0,
        "exit_price": 52000.0,
        "quantity": 0.1,
        "entry_value_usd": 5000.0,
        "exit_value_usd": 5200.0,
        "realized_pnl_usd": 200.0,
        "realized_pnl_pct": 4.0,
        "pnl_class": "profit",
        "close_reason": "take_profit",
        "close_reason_label": "Take Profit Hit",
        "opened_at": "2026-03-01T10:00:00",
        "closed_at": "2026-03-02T10:00:00",
        "hold_duration_hours": 24.0,
        "entry_signals": None,
        "exit_signals": None,
        "transactions": [],
    }
    base.update(overrides)
    return base


class TestFormatJournalCsv:
    """Tests for the format_journal_csv pure function."""

    def test_empty_list_returns_header_only(self) -> None:
        result = format_journal_csv([])
        lines = result.strip().splitlines()
        assert len(lines) == 1
        assert lines[0] == ",".join(CSV_COLUMNS)

    def test_three_entries_returns_four_lines(self) -> None:
        entries = [_sample_entry(symbol=f"SYM-{i}") for i in range(3)]
        result = format_journal_csv(entries)
        lines = result.strip().splitlines()
        assert len(lines) == 4  # 1 header + 3 data

    def test_header_contains_all_twelve_columns(self) -> None:
        result = format_journal_csv([])
        reader = csv.reader(io.StringIO(result))
        header = next(reader)
        assert len(header) == 12
        assert header == CSV_COLUMNS

    def test_none_values_produce_empty_strings(self) -> None:
        entry = _sample_entry(exit_price=None, exit_value_usd=None, realized_pnl_usd=None)
        result = format_journal_csv([entry])
        reader = csv.reader(io.StringIO(result))
        next(reader)  # skip header
        row = next(reader)
        # exit_price is column index 2, exit_value_usd is 5, realized_pnl_usd is 6
        assert row[2] == ""
        assert row[5] == ""
        assert row[6] == ""

    def test_csv_roundtrip_with_csv_reader(self) -> None:
        entries = [_sample_entry(), _sample_entry(symbol="ETH-USD", quantity=1.5)]
        result = format_journal_csv(entries)
        reader = csv.reader(io.StringIO(result))
        rows = list(reader)
        assert len(rows) == 3  # header + 2 data
        assert rows[0] == CSV_COLUMNS
        assert rows[1][0] == "BTC-USD"
        assert rows[2][0] == "ETH-USD"

    def test_column_count_matches_in_data_rows(self) -> None:
        entries = [_sample_entry()]
        result = format_journal_csv(entries)
        reader = csv.reader(io.StringIO(result))
        header = next(reader)
        data_row = next(reader)
        assert len(data_row) == len(header) == 12

    def test_all_none_values_produce_all_empty_cells(self) -> None:
        entry = _sample_entry(**{col: None for col in CSV_COLUMNS})
        result = format_journal_csv([entry])
        reader = csv.reader(io.StringIO(result))
        next(reader)  # skip header
        row = next(reader)
        assert all(cell == "" for cell in row)

    def test_numeric_values_preserved(self) -> None:
        entry = _sample_entry(entry_price=123.456, quantity=0.001)
        result = format_journal_csv([entry])
        reader = csv.reader(io.StringIO(result))
        next(reader)
        row = next(reader)
        assert row[1] == "123.456"  # entry_price
        assert row[3] == "0.001"    # quantity
