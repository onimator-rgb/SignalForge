"""Tests for strategy CRUD endpoints."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.strategies.router import router, _strategies_store


def _build_app() -> FastAPI:
    app = FastAPI()
    app.include_router(router)
    return app


@pytest.fixture(autouse=True)
def _clear_store() -> None:  # type: ignore[misc]
    """Ensure store is empty before each test."""
    _strategies_store.clear()


def _valid_rule() -> dict:  # type: ignore[type-arg]
    return {
        "condition": {
            "indicator": "rsi",
            "operator": "gt",
            "value": 70.0,
        },
        "action": {
            "action": "sell",
            "weight": 1.0,
        },
        "description": "Sell when RSI > 70",
    }


def _valid_payload() -> dict:  # type: ignore[type-arg]
    return {
        "name": "My Strategy",
        "description": "Test strategy",
        "rules": [_valid_rule()],
        "profile_name": "aggressive",
    }


# ---------------------------------------------------------------------------
# POST /api/v1/strategies
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_strategy_success() -> None:
    app = _build_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/api/v1/strategies", json=_valid_payload())

    assert resp.status_code == 201
    body = resp.json()
    assert "id" in body
    assert body["name"] == "My Strategy"
    assert body["num_rules"] == 1
    assert body["is_preset"] is False


@pytest.mark.asyncio
async def test_create_strategy_invalid_rules_empty() -> None:
    app = _build_app()
    payload = _valid_payload()
    payload["rules"] = []
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/api/v1/strategies", json=payload)

    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_strategy_bad_rule_schema() -> None:
    app = _build_app()
    payload = _valid_payload()
    payload["rules"] = [{"bad_field": "value"}]
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/api/v1/strategies", json=payload)

    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# GET /api/v1/strategies (list)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_strategies_empty() -> None:
    app = _build_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/v1/strategies")

    assert resp.status_code == 200
    body = resp.json()
    assert body["count"] == 0
    assert body["strategies"] == []


@pytest.mark.asyncio
async def test_list_strategies_with_items() -> None:
    app = _build_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post("/api/v1/strategies", json=_valid_payload())
        payload2 = _valid_payload()
        payload2["name"] = "Second Strategy"
        await client.post("/api/v1/strategies", json=payload2)

        resp = await client.get("/api/v1/strategies")

    assert resp.status_code == 200
    body = resp.json()
    assert body["count"] == 2
    assert len(body["strategies"]) == 2


# ---------------------------------------------------------------------------
# GET /api/v1/strategies/{id}
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_strategy_success() -> None:
    app = _build_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        create_resp = await client.post("/api/v1/strategies", json=_valid_payload())
        strategy_id = create_resp.json()["id"]

        resp = await client.get(f"/api/v1/strategies/{strategy_id}")

    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == strategy_id
    assert body["name"] == "My Strategy"


@pytest.mark.asyncio
async def test_get_strategy_not_found() -> None:
    app = _build_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/v1/strategies/nonexistent-id")

    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# DELETE /api/v1/strategies/{id}
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_strategy_success() -> None:
    app = _build_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        create_resp = await client.post("/api/v1/strategies", json=_valid_payload())
        strategy_id = create_resp.json()["id"]

        del_resp = await client.delete(f"/api/v1/strategies/{strategy_id}")
        assert del_resp.status_code == 204

        get_resp = await client.get(f"/api/v1/strategies/{strategy_id}")
        assert get_resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_strategy_not_found() -> None:
    app = _build_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.delete("/api/v1/strategies/nonexistent-id")

    assert resp.status_code == 404
