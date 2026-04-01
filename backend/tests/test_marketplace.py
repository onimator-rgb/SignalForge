"""Tests for marketplace publish/unpublish/list endpoints (marketpulse-task-2026-04-02-0037)."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.strategies.marketplace import router as marketplace_router
from app.strategies.router import router as strategies_router, store

SAMPLE_RULE = {
    "condition": {"indicator": "rsi", "operator": "gt", "value": 70},
    "action": {"action": "sell"},
}


def _build_app() -> FastAPI:
    app = FastAPI()
    app.include_router(strategies_router)
    app.include_router(marketplace_router)
    return app


@pytest.fixture(autouse=True)
def _clear_store() -> None:  # type: ignore[misc]
    store.clear()


async def _create_strategy(client: AsyncClient, name: str = "test") -> dict:
    resp = await client.post(
        "/api/v1/strategies/",
        json={"name": name, "rules": [SAMPLE_RULE]},
    )
    assert resp.status_code == 200
    return resp.json()


async def test_publish_strategy() -> None:
    app = _build_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        data = await _create_strategy(client)
        sid = data["id"]

        resp = await client.post(f"/api/v1/strategies/{sid}/publish")
        assert resp.status_code == 200
        assert resp.json()["is_public"] is True


async def test_unpublish_strategy() -> None:
    app = _build_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        data = await _create_strategy(client)
        sid = data["id"]

        await client.post(f"/api/v1/strategies/{sid}/publish")
        resp = await client.post(f"/api/v1/strategies/{sid}/unpublish")
        assert resp.status_code == 200
        assert resp.json()["is_public"] is False


async def test_list_marketplace_empty() -> None:
    app = _build_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/v1/marketplace")
        assert resp.status_code == 200
        assert resp.json() == []


async def test_list_marketplace_returns_only_public() -> None:
    app = _build_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        s1 = await _create_strategy(client, "alpha")
        s2 = await _create_strategy(client, "beta")
        s3 = await _create_strategy(client, "gamma")

        # Publish only s2
        await client.post(f"/api/v1/strategies/{s2['id']}/publish")

        resp = await client.get("/api/v1/marketplace")
        assert resp.status_code == 200
        items = resp.json()
        assert len(items) == 1
        assert items[0]["id"] == s2["id"]
        assert items[0]["is_public"] is True


async def test_publish_nonexistent_404() -> None:
    app = _build_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/api/v1/strategies/nonexistent/publish")
        assert resp.status_code == 404


async def test_unpublish_nonexistent_404() -> None:
    app = _build_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/api/v1/strategies/nonexistent/unpublish")
        assert resp.status_code == 404


async def test_publish_idempotent() -> None:
    app = _build_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        data = await _create_strategy(client)
        sid = data["id"]

        resp1 = await client.post(f"/api/v1/strategies/{sid}/publish")
        assert resp1.status_code == 200
        resp2 = await client.post(f"/api/v1/strategies/{sid}/publish")
        assert resp2.status_code == 200
        assert resp2.json()["is_public"] is True
