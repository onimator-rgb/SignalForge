"""Tests for the webhook signal receiver endpoints."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient
from fastapi import FastAPI

from app.signals.webhook import router, _signal_buffer


def _build_app() -> FastAPI:
    app = FastAPI()
    app.include_router(router)
    return app


@pytest.fixture(autouse=True)
def _clear_buffer() -> None:  # type: ignore[misc]
    """Ensure buffer is empty before each test."""
    _signal_buffer.clear()


def _valid_payload(*, symbol: str = "BTC/USD", action: str = "buy") -> dict:
    return {
        "symbol": symbol,
        "action": action,
        "source": "tradingview",
        "confidence": 0.85,
    }


# ---------------------------------------------------------------------------
# POST /api/v1/signals/webhook
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_post_valid_signal_returns_201() -> None:
    app = _build_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/api/v1/signals/webhook", json=_valid_payload())

    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == "accepted"
    assert "id" in body


@pytest.mark.asyncio
async def test_post_signal_missing_field_returns_422() -> None:
    app = _build_app()
    payload = {"symbol": "BTC/USD", "action": "buy"}  # missing source & confidence
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/api/v1/signals/webhook", json=payload)

    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_post_signal_invalid_action_returns_422() -> None:
    app = _build_app()
    payload = _valid_payload()
    payload["action"] = "hold"
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/api/v1/signals/webhook", json=payload)

    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_post_signal_confidence_out_of_range_returns_422() -> None:
    app = _build_app()
    for bad_value in [-0.1, 1.1]:
        payload = _valid_payload()
        payload["confidence"] = bad_value
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.post("/api/v1/signals/webhook", json=payload)
        assert resp.status_code == 422, f"Expected 422 for confidence={bad_value}"


# ---------------------------------------------------------------------------
# GET /api/v1/signals/
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_signals_empty_returns_empty_list() -> None:
    app = _build_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/v1/signals/")

    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_get_signals_returns_posted_signals_newest_first() -> None:
    app = _build_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        ids: list[str] = []
        for sym in ["AAA", "BBB", "CCC"]:
            r = await client.post(
                "/api/v1/signals/webhook", json=_valid_payload(symbol=sym)
            )
            ids.append(r.json()["id"])

        resp = await client.get("/api/v1/signals/")

    body = resp.json()
    assert len(body) == 3
    # newest first
    assert body[0]["symbol"] == "CCC"
    assert body[2]["symbol"] == "AAA"
    # ids match
    returned_ids = [s["id"] for s in body]
    assert returned_ids == list(reversed(ids))


@pytest.mark.asyncio
async def test_get_signals_limit_param() -> None:
    app = _build_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        for i in range(5):
            await client.post(
                "/api/v1/signals/webhook", json=_valid_payload(symbol=f"SYM{i}")
            )
        resp = await client.get("/api/v1/signals/", params={"limit": 2})

    assert len(resp.json()) == 2


# ---------------------------------------------------------------------------
# Buffer capacity
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_buffer_capacity_evicts_oldest() -> None:
    app = _build_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Post 1001 signals
        first_resp = await client.post(
            "/api/v1/signals/webhook", json=_valid_payload(symbol="OLDEST")
        )
        first_id = first_resp.json()["id"]

        for i in range(1000):
            await client.post(
                "/api/v1/signals/webhook", json=_valid_payload(symbol=f"S{i}")
            )

        # Buffer should be capped at 1000
        resp = await client.get("/api/v1/signals/", params={"limit": 1000})

    body = resp.json()
    assert len(body) == 1000
    all_ids = {s["id"] for s in body}
    assert first_id not in all_ids, "Oldest signal should have been evicted"
