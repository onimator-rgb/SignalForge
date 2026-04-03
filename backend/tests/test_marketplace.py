"""Tests for marketplace endpoints — publish, unpublish, list, ranking."""

import pytest
from fastapi.testclient import TestClient
from fastapi import FastAPI

from app.strategies.models import Strategy, StrategyRule, StrategyCondition, StrategyStore
from app.strategies.marketplace import router as marketplace_router, compute_mock_metrics
from app.strategies import router as strategies_module


def _make_strategy(name: str = "Test RSI", **overrides) -> Strategy:
    return Strategy(
        name=name,
        rules=[StrategyRule(
            conditions=[StrategyCondition(indicator="rsi", operator="gt", value=70)],
            action="sell",
            weight=1.0,
        )],
        **overrides,
    )


@pytest.fixture(autouse=True)
def _clean_store():
    """Reset the global store before each test."""
    strategies_module.store.clear()
    yield
    strategies_module.store.clear()


@pytest.fixture()
def client() -> TestClient:
    app = FastAPI()
    app.include_router(marketplace_router)
    return TestClient(app)


class TestPublish:
    def test_publish_sets_is_public(self, client: TestClient):
        s = _make_strategy()
        strategies_module.store.add(s)
        resp = client.post(f"/api/v1/strategies/{s.id}/publish")
        assert resp.status_code == 200
        assert resp.json()["is_public"] is True

    def test_publish_not_found(self, client: TestClient):
        resp = client.post("/api/v1/strategies/nonexistent/publish")
        assert resp.status_code == 404

    def test_unpublish_sets_is_public_false(self, client: TestClient):
        s = _make_strategy(is_public=True)
        strategies_module.store.add(s)
        resp = client.post(f"/api/v1/strategies/{s.id}/unpublish")
        assert resp.status_code == 200
        assert resp.json()["is_public"] is False

    def test_unpublish_not_found(self, client: TestClient):
        resp = client.post("/api/v1/strategies/nonexistent/unpublish")
        assert resp.status_code == 404


class TestListMarketplace:
    def test_empty_marketplace(self, client: TestClient):
        resp = client.get("/api/v1/marketplace")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_only_public_strategies_returned(self, client: TestClient):
        public = _make_strategy("Public", is_public=True)
        private = _make_strategy("Private", is_public=False)
        strategies_module.store.add(public)
        strategies_module.store.add(private)
        resp = client.get("/api/v1/marketplace")
        names = [s["name"] for s in resp.json()]
        assert "Public" in names
        assert "Private" not in names

    def test_sorted_by_created_at_desc(self, client: TestClient):
        from datetime import datetime, timezone, timedelta
        old = _make_strategy("Old", is_public=True,
                             created_at=datetime(2025, 1, 1, tzinfo=timezone.utc))
        new = _make_strategy("New", is_public=True,
                             created_at=datetime(2026, 1, 1, tzinfo=timezone.utc))
        strategies_module.store.add(old)
        strategies_module.store.add(new)
        resp = client.get("/api/v1/marketplace")
        names = [s["name"] for s in resp.json()]
        assert names == ["New", "Old"]


class TestRanking:
    def test_ranking_returns_ranked_strategies(self, client: TestClient):
        s = _make_strategy(is_public=True)
        strategies_module.store.add(s)
        resp = client.get("/api/v1/marketplace/ranking")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert "sharpe_ratio" in data[0]
        assert "strategy_id" in data[0]

    def test_ranking_empty_when_no_public(self, client: TestClient):
        s = _make_strategy(is_public=False)
        strategies_module.store.add(s)
        resp = client.get("/api/v1/marketplace/ranking")
        assert resp.json() == []

    def test_ranking_sort_by_total_return(self, client: TestClient):
        for i in range(3):
            s = _make_strategy(f"Strat {i}", is_public=True)
            strategies_module.store.add(s)
        resp = client.get("/api/v1/marketplace/ranking?sort_by=total_return_pct")
        assert resp.status_code == 200
        returns = [r["total_return_pct"] for r in resp.json()]
        assert returns == sorted(returns, reverse=True)

    def test_ranking_limit(self, client: TestClient):
        for i in range(5):
            s = _make_strategy(f"Strat {i}", is_public=True)
            strategies_module.store.add(s)
        resp = client.get("/api/v1/marketplace/ranking?limit=2")
        assert len(resp.json()) == 2

    def test_mock_metrics_deterministic(self):
        s = _make_strategy()
        m1 = compute_mock_metrics(s)
        m2 = compute_mock_metrics(s)
        assert m1.sharpe_ratio == m2.sharpe_ratio
        assert m1.total_return_pct == m2.total_return_pct
