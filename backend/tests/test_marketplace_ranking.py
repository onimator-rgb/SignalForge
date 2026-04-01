"""Tests for marketplace ranking endpoint (marketpulse-task-2026-04-02-0041)."""

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


async def _create_and_publish(client: AsyncClient, name: str = "test") -> dict:
    data = await _create_strategy(client, name)
    await client.post(f"/api/v1/strategies/{data['id']}/publish")
    return data


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


async def test_ranking_empty() -> None:
    """Empty store returns empty list."""
    app = _build_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/v1/marketplace/ranking")
        assert resp.status_code == 200
        assert resp.json() == []


async def test_ranking_returns_only_public() -> None:
    """Only published strategies appear in ranking."""
    app = _build_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await _create_strategy(client, "private1")
        await _create_and_publish(client, "public1")
        await _create_and_publish(client, "public2")

        resp = await client.get("/api/v1/marketplace/ranking")
        assert resp.status_code == 200
        items = resp.json()
        assert len(items) == 2


async def test_ranking_sorted_by_sharpe_descending() -> None:
    """Default sort is sharpe_ratio descending."""
    app = _build_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        for i in range(5):
            await _create_and_publish(client, f"strat-{i}")

        resp = await client.get("/api/v1/marketplace/ranking")
        assert resp.status_code == 200
        items = resp.json()
        sharpes = [item["sharpe_ratio"] for item in items]
        assert sharpes == sorted(sharpes, reverse=True)


async def test_sort_by_copy_count() -> None:
    """sort_by=copy_count sorts by copy_count descending."""
    app = _build_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        for i in range(5):
            await _create_and_publish(client, f"strat-{i}")

        resp = await client.get("/api/v1/marketplace/ranking?sort_by=copy_count")
        assert resp.status_code == 200
        items = resp.json()
        counts = [item["copy_count"] for item in items]
        assert counts == sorted(counts, reverse=True)


async def test_sort_by_total_return() -> None:
    """sort_by=total_return_pct sorts by total_return_pct descending."""
    app = _build_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        for i in range(5):
            await _create_and_publish(client, f"strat-{i}")

        resp = await client.get("/api/v1/marketplace/ranking?sort_by=total_return_pct")
        assert resp.status_code == 200
        items = resp.json()
        returns = [item["total_return_pct"] for item in items]
        assert returns == sorted(returns, reverse=True)


async def test_limit_parameter() -> None:
    """limit caps the result list."""
    app = _build_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        for i in range(10):
            await _create_and_publish(client, f"strat-{i}")

        resp = await client.get("/api/v1/marketplace/ranking?limit=3")
        assert resp.status_code == 200
        items = resp.json()
        assert len(items) == 3


async def test_metrics_deterministic() -> None:
    """Same strategy id produces identical metrics across calls."""
    app = _build_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await _create_and_publish(client, "deterministic-test")

        resp1 = await client.get("/api/v1/marketplace/ranking")
        resp2 = await client.get("/api/v1/marketplace/ranking")
        assert resp1.json() == resp2.json()


async def test_ranked_strategy_fields_present() -> None:
    """All RankedStrategy fields are present in the response."""
    app = _build_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await _create_and_publish(client, "field-check")

        resp = await client.get("/api/v1/marketplace/ranking")
        assert resp.status_code == 200
        items = resp.json()
        assert len(items) == 1

        item = items[0]
        expected_fields = {
            "strategy_id",
            "name",
            "profile_name",
            "total_return_pct",
            "max_drawdown_pct",
            "sharpe_ratio",
            "win_rate_pct",
            "copy_count",
            "rule_count",
        }
        assert expected_fields.issubset(item.keys())


async def test_metrics_in_valid_ranges() -> None:
    """Mock metrics fall within specified ranges."""
    app = _build_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await _create_and_publish(client, "range-check")

        resp = await client.get("/api/v1/marketplace/ranking")
        item = resp.json()[0]

        assert -20 <= item["total_return_pct"] <= 80
        assert -40 <= item["max_drawdown_pct"] <= -2
        assert -0.5 <= item["sharpe_ratio"] <= 3.0
        assert 25 <= item["win_rate_pct"] <= 75
        assert 0 <= item["copy_count"] <= 500
        assert item["rule_count"] >= 1
