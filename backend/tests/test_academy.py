"""Tests for the Academy module — content functions and API router."""

import pytest
from fastapi import FastAPI
from httpx import AsyncClient, ASGITransport

from app.academy.content import get_articles, get_article_by_slug, ARTICLES
from app.academy.router import router as academy_router


# --------------- Unit tests for content functions ---------------


def test_get_articles_returns_all() -> None:
    articles = get_articles()
    assert len(articles) == 5


def test_get_articles_filter_risk() -> None:
    articles = get_articles(category="risk")
    assert len(articles) == 2
    assert all(a.category == "risk" for a in articles)


def test_get_articles_filter_nonexistent() -> None:
    articles = get_articles(category="nonexistent")
    assert articles == []


def test_get_article_by_slug_found() -> None:
    article = get_article_by_slug("what-is-rsi")
    assert article is not None
    assert article.slug == "what-is-rsi"
    assert article.category == "indicators"


def test_get_article_by_slug_not_found() -> None:
    assert get_article_by_slug("nonexistent") is None


def test_all_articles_have_content() -> None:
    for article in ARTICLES:
        assert article.body, f"{article.slug} has empty body"
        assert article.summary, f"{article.slug} has empty summary"


def test_all_slugs_unique() -> None:
    slugs = [a.slug for a in ARTICLES]
    assert len(slugs) == len(set(slugs))


# --------------- API router tests ---------------


@pytest.fixture
def app() -> FastAPI:
    _app = FastAPI()
    _app.include_router(academy_router)
    return _app


@pytest.mark.asyncio
async def test_list_articles_endpoint(app: FastAPI) -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/api/v1/academy/articles")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 5
    # body must NOT be present in list items
    for item in data:
        assert "body" not in item
        assert "slug" in item
        assert "title" in item
        assert "summary" in item


@pytest.mark.asyncio
async def test_list_articles_filter_category(app: FastAPI) -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/api/v1/academy/articles?category=strategies")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    assert all(item["category"] == "strategies" for item in data)


@pytest.mark.asyncio
async def test_get_article_detail(app: FastAPI) -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/api/v1/academy/articles/what-is-rsi")
    assert resp.status_code == 200
    data = resp.json()
    assert data["slug"] == "what-is-rsi"
    assert "body" in data
    assert len(data["body"]) > 0


@pytest.mark.asyncio
async def test_get_article_not_found(app: FastAPI) -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/api/v1/academy/articles/nonexistent")
    assert resp.status_code == 404
