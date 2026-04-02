"""Tests for Strategy CRUD API endpoints."""

import pytest
from fastapi.testclient import TestClient

from app.strategies.router import router, store

# Minimal app with only the strategies router for isolated testing.
from fastapi import FastAPI

_app = FastAPI()
_app.include_router(router)
client = TestClient(_app)

SAMPLE_RULE = {
    "condition": {"indicator": "rsi", "operator": "gt", "value": 70},
    "action": {"action": "sell"},
}


@pytest.fixture(autouse=True)
def _clear_store() -> None:  # type: ignore[misc]
    store.clear()


def test_create_strategy() -> None:
    resp = client.post(
        "/api/v1/strategies/",
        json={
            "name": "RSI Overbought",
            "description": "Sell when RSI > 70",
            "rules": [SAMPLE_RULE],
            "profile_name": "aggressive",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "RSI Overbought"
    assert data["profile_name"] == "aggressive"
    assert "id" in data
    assert len(data["rules"]) == 1


def test_list_strategies_empty() -> None:
    resp = client.get("/api/v1/strategies/")
    assert resp.status_code == 200
    assert resp.json() == []


def test_list_strategies() -> None:
    client.post("/api/v1/strategies/", json={"name": "A", "rules": [SAMPLE_RULE]})
    client.post("/api/v1/strategies/", json={"name": "B", "rules": [SAMPLE_RULE]})
    resp = client.get("/api/v1/strategies/")
    assert resp.status_code == 200
    assert len(resp.json()) == 2


def test_get_strategy() -> None:
    create_resp = client.post(
        "/api/v1/strategies/",
        json={"name": "Test", "rules": [SAMPLE_RULE]},
    )
    sid = create_resp.json()["id"]
    resp = client.get(f"/api/v1/strategies/{sid}")
    assert resp.status_code == 200
    assert resp.json()["id"] == sid
    assert resp.json()["name"] == "Test"


def test_get_strategy_not_found() -> None:
    resp = client.get("/api/v1/strategies/nonexistent")
    assert resp.status_code == 404


def test_delete_strategy() -> None:
    create_resp = client.post(
        "/api/v1/strategies/",
        json={"name": "To Delete", "rules": [SAMPLE_RULE]},
    )
    sid = create_resp.json()["id"]
    resp = client.delete(f"/api/v1/strategies/{sid}")
    assert resp.status_code == 200
    assert resp.json()["deleted"] is True
    # Verify it's gone
    assert client.get(f"/api/v1/strategies/{sid}").status_code == 404


def test_delete_strategy_not_found() -> None:
    resp = client.delete("/api/v1/strategies/nonexistent")
    assert resp.status_code == 404
