"""Tests for marketplace copy-trading endpoint (marketpulse-task-2026-04-02-0039)."""

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


async def _create_and_publish(client: AsyncClient, name: str = "test") -> dict:
    resp = await client.post(
        "/api/v1/strategies/",
        json={"name": name, "rules": [SAMPLE_RULE]},
    )
    assert resp.status_code == 200
    data = resp.json()
    pub = await client.post(f"/api/v1/strategies/{data['id']}/publish")
    assert pub.status_code == 200
    return pub.json()


async def test_copy_public_strategy() -> None:
    app = _build_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        original = await _create_and_publish(client, "Alpha")

        resp = await client.post(f"/api/v1/marketplace/{original['id']}/copy")
        assert resp.status_code == 200
        copied = resp.json()

        assert copied["id"] != original["id"]
        assert copied["name"] == "Copy of Alpha"
        assert copied["is_public"] is False

        # Check original's copy_count incremented
        orig_resp = await client.get(f"/api/v1/strategies/{original['id']}")
        assert orig_resp.json()["copy_count"] == 1


async def test_copy_increments_count() -> None:
    app = _build_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        original = await _create_and_publish(client, "Beta")

        await client.post(f"/api/v1/marketplace/{original['id']}/copy")
        await client.post(f"/api/v1/marketplace/{original['id']}/copy")

        orig_resp = await client.get(f"/api/v1/strategies/{original['id']}")
        assert orig_resp.json()["copy_count"] == 2


async def test_copy_nonexistent_404() -> None:
    app = _build_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/api/v1/marketplace/nonexistent/copy")
        assert resp.status_code == 404


async def test_copy_private_strategy_400() -> None:
    app = _build_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/api/v1/strategies/",
            json={"name": "Private", "rules": [SAMPLE_RULE]},
        )
        sid = resp.json()["id"]

        resp = await client.post(f"/api/v1/marketplace/{sid}/copy")
        assert resp.status_code == 400
        assert "not public" in resp.json()["detail"]


async def test_copy_preserves_rules() -> None:
    app = _build_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        original = await _create_and_publish(client, "Gamma")

        resp = await client.post(f"/api/v1/marketplace/{original['id']}/copy")
        copied = resp.json()

        assert copied["rules"] == original["rules"]


async def test_copy_is_independent() -> None:
    app = _build_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        original = await _create_and_publish(client, "Delta")

        resp = await client.post(f"/api/v1/marketplace/{original['id']}/copy")
        copied = resp.json()

        # Modifying the copied strategy's rules in the store should not affect the original
        copy_obj = store.get(copied["id"])
        assert copy_obj is not None
        copy_obj.name = "Modified Copy"

        orig_obj = store.get(original["id"])
        assert orig_obj is not None
        assert orig_obj.name == "Delta"
