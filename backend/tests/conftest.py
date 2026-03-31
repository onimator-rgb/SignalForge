"""Shared async test fixtures for MarketPulse AI."""

import pytest
from fastapi import FastAPI
from httpx import AsyncClient, ASGITransport

from app.database import get_db
from app.watchlists.router import router as watchlists_router


def make_test_app(mock_db) -> FastAPI:
    app = FastAPI()
    app.include_router(watchlists_router)

    async def _override_db():
        yield mock_db

    app.dependency_overrides[get_db] = _override_db
    return app


async def async_client(mock_db) -> AsyncClient:
    app = make_test_app(mock_db)
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
