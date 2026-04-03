"""Integration tests for the full portfolio evaluation cycle.

Tests evaluate_portfolio() by mocking the three sub-phases:
_check_exits, _check_dca, _check_entries.
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest


@pytest.fixture()
def mock_db():
    db = AsyncMock()
    db.flush = AsyncMock()
    db.commit = AsyncMock()
    return db


def _mock_portfolio():
    """Lightweight mock that satisfies evaluate_portfolio's attribute access."""
    from unittest.mock import MagicMock
    p = MagicMock()
    p.updated_at = None
    p.current_cash = 9000.0
    return p


SERVICE = "app.portfolio.service"


@pytest.mark.asyncio
class TestEvaluatePortfolioCycle:

    async def test_returns_dict_with_counts(self, mock_db):
        from app.portfolio.service import evaluate_portfolio

        with patch(f"{SERVICE}.get_or_create_portfolio", return_value=_mock_portfolio()), \
             patch(f"{SERVICE}._check_exits", return_value=0), \
             patch(f"{SERVICE}._check_dca", return_value=0), \
             patch(f"{SERVICE}._check_entries", return_value=0):
            result = await evaluate_portfolio(mock_db)

        assert isinstance(result, dict)
        assert result["closed"] == 0
        assert result["dca_buys"] == 0
        assert result["opened"] == 0

    async def test_reports_closed_positions(self, mock_db):
        from app.portfolio.service import evaluate_portfolio

        with patch(f"{SERVICE}.get_or_create_portfolio", return_value=_mock_portfolio()), \
             patch(f"{SERVICE}._check_exits", return_value=3), \
             patch(f"{SERVICE}._check_dca", return_value=0), \
             patch(f"{SERVICE}._check_entries", return_value=0):
            result = await evaluate_portfolio(mock_db)

        assert result["closed"] == 3

    async def test_reports_dca_buys(self, mock_db):
        from app.portfolio.service import evaluate_portfolio

        with patch(f"{SERVICE}.get_or_create_portfolio", return_value=_mock_portfolio()), \
             patch(f"{SERVICE}._check_exits", return_value=0), \
             patch(f"{SERVICE}._check_dca", return_value=2), \
             patch(f"{SERVICE}._check_entries", return_value=0):
            result = await evaluate_portfolio(mock_db)

        assert result["dca_buys"] == 2

    async def test_reports_opened_positions(self, mock_db):
        from app.portfolio.service import evaluate_portfolio

        with patch(f"{SERVICE}.get_or_create_portfolio", return_value=_mock_portfolio()), \
             patch(f"{SERVICE}._check_exits", return_value=0), \
             patch(f"{SERVICE}._check_dca", return_value=0), \
             patch(f"{SERVICE}._check_entries", return_value=4):
            result = await evaluate_portfolio(mock_db)

        assert result["opened"] == 4

    async def test_updates_portfolio_timestamp(self, mock_db):
        from app.portfolio.service import evaluate_portfolio

        portfolio = _mock_portfolio()
        with patch(f"{SERVICE}.get_or_create_portfolio", return_value=portfolio), \
             patch(f"{SERVICE}._check_exits", return_value=0), \
             patch(f"{SERVICE}._check_dca", return_value=0), \
             patch(f"{SERVICE}._check_entries", return_value=0):
            await evaluate_portfolio(mock_db)

        assert portfolio.updated_at is not None
        mock_db.flush.assert_called()
        mock_db.commit.assert_called()

    async def test_runs_phases_in_order(self, mock_db):
        from app.portfolio.service import evaluate_portfolio

        call_order = []

        async def mock_exits(*a, **kw):
            call_order.append("exits")
            return 1

        async def mock_dca(*a, **kw):
            call_order.append("dca")
            return 1

        async def mock_entries(*a, **kw):
            call_order.append("entries")
            return 1

        with patch(f"{SERVICE}.get_or_create_portfolio", return_value=_mock_portfolio()), \
             patch(f"{SERVICE}._check_exits", side_effect=mock_exits), \
             patch(f"{SERVICE}._check_dca", side_effect=mock_dca), \
             patch(f"{SERVICE}._check_entries", side_effect=mock_entries):
            result = await evaluate_portfolio(mock_db)

        assert call_order == ["exits", "dca", "entries"]
        assert result == {"closed": 1, "dca_buys": 1, "opened": 1}

    async def test_mixed_activity(self, mock_db):
        from app.portfolio.service import evaluate_portfolio

        with patch(f"{SERVICE}.get_or_create_portfolio", return_value=_mock_portfolio()), \
             patch(f"{SERVICE}._check_exits", return_value=2), \
             patch(f"{SERVICE}._check_dca", return_value=1), \
             patch(f"{SERVICE}._check_entries", return_value=3):
            result = await evaluate_portfolio(mock_db)

        assert result == {"closed": 2, "dca_buys": 1, "opened": 3}
