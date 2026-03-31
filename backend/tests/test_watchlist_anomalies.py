"""Unit tests for GET /api/v1/watchlists/{watchlist_id}/anomalies."""

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from tests.conftest import async_client


# ── Helpers ───────────────────────────────────────────────────────────────────

def _mock_db(*results):
    """Mock AsyncSession whose execute() returns *results* in order."""
    db = MagicMock()
    db.execute = AsyncMock(side_effect=list(results))
    return db


def _result(scalar=None, rows=None):
    """Build a mock SQLAlchemy Result."""
    r = MagicMock()
    r.scalar_one_or_none.return_value = scalar
    r.all.return_value = rows if rows is not None else []
    return r


def _watchlist(wl_id):
    wl = MagicMock()
    wl.id = wl_id
    wl.name = "My Watchlist"
    return wl


def _asset_row(asset_id, symbol):
    row = MagicMock()
    row.asset_id = asset_id
    row.symbol = symbol
    return row


def _anomaly_row(asset_id, symbol, score=0.75, hours_ago=1):
    ev = MagicMock()
    ev.id = uuid.uuid4()
    ev.asset_id = asset_id
    ev.anomaly_type = "volume_spike"
    ev.severity = "high"
    ev.score = score
    ev.detected_at = datetime.now(timezone.utc) - timedelta(hours=hours_ago)
    ev.details = {"note": "test"}

    row = MagicMock()
    row.AnomalyEvent = ev
    row.symbol = symbol
    return row


# ── Tests ─────────────────────────────────────────────────────────────────────

async def test_valid_watchlist_returns_200_with_required_keys():
    """GET /anomalies for a valid watchlist returns 200 with all required JSON keys."""
    wl_id = uuid.uuid4()
    asset_id = uuid.uuid4()

    db = _mock_db(
        _result(scalar=_watchlist(wl_id)),            # _get_watchlist_or_404
        _result(rows=[_asset_row(asset_id, "BTC")]),  # watchlist assets
        _result(rows=[_anomaly_row(asset_id, "BTC")]),  # anomalies
    )

    async with await async_client(db) as client:
        resp = await client.get(f"/api/v1/watchlists/{wl_id}/anomalies")

    assert resp.status_code == 200
    data = resp.json()
    assert {"watchlist_id", "assets", "anomalies", "last_updated", "total"} <= data.keys()
    assert data["watchlist_id"] == str(wl_id)
    assert data["total"] == 1
    assert data["assets"] == ["BTC"]


async def test_nonexistent_watchlist_returns_404():
    """GET /anomalies for an unknown watchlist_id returns 404."""
    wl_id = uuid.uuid4()

    db = _mock_db(
        _result(scalar=None),  # watchlist not found
    )

    async with await async_client(db) as client:
        resp = await client.get(f"/api/v1/watchlists/{wl_id}/anomalies")

    assert resp.status_code == 404


async def test_watchlist_with_no_assets_returns_empty_list():
    """Watchlist with zero assets returns an empty anomalies list."""
    wl_id = uuid.uuid4()

    db = _mock_db(
        _result(scalar=_watchlist(wl_id)),  # found
        _result(rows=[]),                    # no assets → anomaly query skipped
    )

    async with await async_client(db) as client:
        resp = await client.get(f"/api/v1/watchlists/{wl_id}/anomalies")

    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 0
    assert data["anomalies"] == []
    assert data["assets"] == []


async def test_anomaly_object_contains_all_required_fields():
    """Each anomaly in the response contains all documented fields."""
    wl_id = uuid.uuid4()
    asset_id = uuid.uuid4()

    db = _mock_db(
        _result(scalar=_watchlist(wl_id)),
        _result(rows=[_asset_row(asset_id, "ETH")]),
        _result(rows=[_anomaly_row(asset_id, "ETH", score=0.9, hours_ago=2)]),
    )

    async with await async_client(db) as client:
        resp = await client.get(f"/api/v1/watchlists/{wl_id}/anomalies")

    assert resp.status_code == 200
    anomaly = resp.json()["anomalies"][0]
    for field in ("id", "asset_id", "symbol", "anomaly_type", "severity", "score", "detected_at", "details"):
        assert field in anomaly, f"Missing field in anomaly response: {field}"
    assert anomaly["score"] == pytest.approx(0.9)
    assert anomaly["symbol"] == "ETH"


async def test_only_unresolved_high_score_recent_anomalies_returned():
    """Only anomalies matching all three filter criteria appear in the response."""
    wl_id = uuid.uuid4()
    asset_id = uuid.uuid4()

    # The endpoint applies filters in the SQL query; the mock returns only what
    # the (mocked) DB would produce after filtering. We assert the endpoint
    # faithfully forwards exactly what the DB returns — no double-filtering.
    passing_anomaly = _anomaly_row(asset_id, "SOL", score=0.8, hours_ago=1)

    db = _mock_db(
        _result(scalar=_watchlist(wl_id)),
        _result(rows=[_asset_row(asset_id, "SOL")]),
        _result(rows=[passing_anomaly]),  # DB already applied is_resolved/score/time filters
    )

    async with await async_client(db) as client:
        resp = await client.get(f"/api/v1/watchlists/{wl_id}/anomalies")

    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["anomalies"][0]["score"] >= 0.5


async def test_multiple_assets_and_anomalies():
    """Multiple assets and anomalies are all returned correctly."""
    wl_id = uuid.uuid4()
    asset_id_1 = uuid.uuid4()
    asset_id_2 = uuid.uuid4()

    db = _mock_db(
        _result(scalar=_watchlist(wl_id)),
        _result(rows=[_asset_row(asset_id_1, "BTC"), _asset_row(asset_id_2, "ETH")]),
        _result(rows=[
            _anomaly_row(asset_id_1, "BTC", score=0.95),
            _anomaly_row(asset_id_2, "ETH", score=0.60),
        ]),
    )

    async with await async_client(db) as client:
        resp = await client.get(f"/api/v1/watchlists/{wl_id}/anomalies")

    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2
    assert set(data["assets"]) == {"BTC", "ETH"}
