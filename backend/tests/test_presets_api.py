"""Tests for the preset strategies API endpoints."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.strategies.router import router

app = FastAPI()
app.include_router(router)
client = TestClient(app)

BASE = "/api/v1/strategies"


# ---------- GET /presets ----------

def test_list_presets_returns_200_with_three_presets() -> None:
    resp = client.get(f"{BASE}/presets")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 3
    types = {p["preset_type"] for p in data}
    assert types == {"grid", "dca", "btd"}


def test_list_presets_contains_required_fields() -> None:
    resp = client.get(f"{BASE}/presets")
    for preset in resp.json():
        assert "preset_type" in preset
        assert "display_name" in preset
        assert "description" in preset
        assert "params" in preset
        assert isinstance(preset["params"], list)
        for param in preset["params"]:
            assert "name" in param
            assert "type" in param
            assert "description" in param


# ---------- POST /from-preset (valid) ----------

def test_generate_dca_rules() -> None:
    resp = client.post(f"{BASE}/from-preset", json={
        "preset_type": "dca",
        "params": {"interval_hours": 4, "amount_per_buy": 50, "max_buys": 10},
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["preset_type"] == "dca"
    assert isinstance(data["rules"], list)
    assert data["num_rules"] == len(data["rules"])
    assert data["num_rules"] >= 2


def test_generate_grid_rules() -> None:
    resp = client.post(f"{BASE}/from-preset", json={
        "preset_type": "grid",
        "params": {"lower_price": 100, "upper_price": 200, "num_grids": 4, "amount_per_grid": 10},
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["preset_type"] == "grid"
    assert data["num_rules"] >= 4


def test_generate_btd_rules() -> None:
    resp = client.post(f"{BASE}/from-preset", json={
        "preset_type": "btd",
        "params": {"dip_pct": 5, "recovery_pct": 2, "take_profit_pct": 10},
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["preset_type"] == "btd"
    assert data["num_rules"] >= 2


# ---------- POST /from-preset (errors) ----------

def test_unknown_preset_type_returns_422() -> None:
    resp = client.post(f"{BASE}/from-preset", json={
        "preset_type": "unknown",
        "params": {},
    })
    assert resp.status_code == 422
    assert "unknown" in resp.json()["detail"].lower()


def test_invalid_params_negative_amount_returns_422() -> None:
    resp = client.post(f"{BASE}/from-preset", json={
        "preset_type": "dca",
        "params": {"interval_hours": 4, "amount_per_buy": -50, "max_buys": 10},
    })
    assert resp.status_code == 422
    assert "amount_per_buy" in resp.json()["detail"]
