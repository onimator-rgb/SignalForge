"""Unit tests for trade journal formatting."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.portfolio.journal import format_journal, format_journal_entry


_UNSET = object()


def _pos(
    *,
    pnl_usd: float | None = 10.0,
    pnl_pct: float | None = 2.0,
    close_reason: str | None = "manual",
    opened_at: datetime | None = None,
    closed_at: datetime | None | object = _UNSET,
    exit_context: dict | None = None,
    exit_price: float | None = 105.0,
    exit_value_usd: float | None = 1050.0,
) -> SimpleNamespace:
    base = datetime(2026, 3, 1, 12, 0, tzinfo=timezone.utc)
    return SimpleNamespace(
        id=uuid4(),
        asset_id=uuid4(),
        symbol="BTC/USD",
        entry_price=100.0,
        quantity=10.0,
        entry_value_usd=1000.0,
        exit_price=exit_price,
        exit_value_usd=exit_value_usd,
        realized_pnl_usd=pnl_usd,
        realized_pnl_pct=pnl_pct,
        close_reason=close_reason,
        opened_at=opened_at if opened_at is not None else base,
        closed_at=closed_at if closed_at is not _UNSET else base + timedelta(hours=48),
        exit_context=exit_context,
        status="closed",
    )


def _tx(
    tx_type: str = "buy",
    price: float = 100.0,
    quantity: float = 10.0,
    value_usd: float = 1000.0,
) -> SimpleNamespace:
    return SimpleNamespace(
        tx_type=tx_type,
        price=price,
        quantity=quantity,
        value_usd=value_usd,
        executed_at=datetime(2026, 3, 1, 12, 0, tzinfo=timezone.utc),
    )


class TestHoldDuration:
    def test_computes_hours(self) -> None:
        pos = _pos(
            opened_at=datetime(2026, 3, 1, 0, 0, tzinfo=timezone.utc),
            closed_at=datetime(2026, 3, 2, 12, 0, tzinfo=timezone.utc),
        )
        entry = format_journal_entry(pos, [])
        assert entry["hold_duration_hours"] == 36.0

    def test_none_when_not_closed(self) -> None:
        pos = _pos(closed_at=None)
        entry = format_journal_entry(pos, [])
        assert entry["hold_duration_hours"] is None


class TestCloseReasonLabel:
    @pytest.mark.parametrize(
        "reason,expected",
        [
            ("stop_loss", "Stop Loss Hit"),
            ("take_profit", "Take Profit Hit"),
            ("max_hold", "Max Hold Expired"),
            ("manual", "Manual Close"),
        ],
    )
    def test_known_reasons(self, reason: str, expected: str) -> None:
        pos = _pos(close_reason=reason)
        entry = format_journal_entry(pos, [])
        assert entry["close_reason_label"] == expected

    def test_unknown_reason_title_cased(self) -> None:
        pos = _pos(close_reason="trailing_stop")
        entry = format_journal_entry(pos, [])
        assert entry["close_reason_label"] == "Trailing Stop"

    def test_none_reason(self) -> None:
        pos = _pos(close_reason=None)
        entry = format_journal_entry(pos, [])
        assert entry["close_reason_label"] == "Unknown"


class TestPnlClass:
    def test_profit(self) -> None:
        entry = format_journal_entry(_pos(pnl_usd=50.0), [])
        assert entry["pnl_class"] == "profit"

    def test_loss(self) -> None:
        entry = format_journal_entry(_pos(pnl_usd=-10.0), [])
        assert entry["pnl_class"] == "loss"

    def test_breakeven(self) -> None:
        entry = format_journal_entry(_pos(pnl_usd=0.0), [])
        assert entry["pnl_class"] == "breakeven"

    def test_none_pnl_is_breakeven(self) -> None:
        entry = format_journal_entry(_pos(pnl_usd=None), [])
        assert entry["pnl_class"] == "breakeven"


class TestSignalExtraction:
    def test_extracts_entry_and_exit(self) -> None:
        ctx = {
            "entry_snapshot": {"rsi": 30, "regime": "bull"},
            "exit_snapshot": {"rsi": 75, "regime": "bear"},
        }
        entry = format_journal_entry(_pos(exit_context=ctx), [])
        assert entry["entry_signals"] == {"rsi": 30, "regime": "bull"}
        assert entry["exit_signals"] == {"rsi": 75, "regime": "bear"}

    def test_none_when_absent(self) -> None:
        entry = format_journal_entry(_pos(exit_context=None), [])
        assert entry["entry_signals"] is None
        assert entry["exit_signals"] is None

    def test_partial_context(self) -> None:
        ctx = {"exit_snapshot": {"rsi": 80}}
        entry = format_journal_entry(_pos(exit_context=ctx), [])
        assert entry["entry_signals"] is None
        assert entry["exit_signals"] == {"rsi": 80}


class TestFormatJournal:
    def test_sorted_by_closed_at_desc(self) -> None:
        base = datetime(2026, 3, 1, 0, 0, tzinfo=timezone.utc)
        p1 = _pos(closed_at=base + timedelta(hours=1))
        p2 = _pos(closed_at=base + timedelta(hours=3))
        p3 = _pos(closed_at=base + timedelta(hours=2))

        result = format_journal([p1, p2, p3], {})
        closed_times = [e["closed_at"] for e in result]
        assert closed_times == sorted(closed_times, reverse=True)

    def test_transactions_attached(self) -> None:
        pos = _pos()
        tx = _tx()
        txs_by_pos = {str(pos.id): [tx]}
        entries = format_journal([pos], txs_by_pos)
        assert len(entries) == 1
        assert len(entries[0]["transactions"]) == 1
        assert entries[0]["transactions"][0]["tx_type"] == "buy"


class TestFormatJournalEntry:
    def test_full_entry_fields(self) -> None:
        pos = _pos()
        tx = _tx()
        entry = format_journal_entry(pos, [tx])

        assert entry["position_id"] == str(pos.id)
        assert entry["symbol"] == "BTC/USD"
        assert entry["entry_price"] == 100.0
        assert entry["exit_price"] == 105.0
        assert entry["quantity"] == 10.0
        assert entry["entry_value_usd"] == 1000.0
        assert entry["exit_value_usd"] == 1050.0
        assert entry["realized_pnl_usd"] == 10.0
        assert entry["realized_pnl_pct"] == 2.0
        assert entry["close_reason"] == "manual"
        assert entry["opened_at"] is not None
        assert entry["closed_at"] is not None
        assert len(entry["transactions"]) == 1
