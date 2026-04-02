"""Academy API router — read-only endpoints for educational articles."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.academy.content import get_articles, get_article_by_slug

router = APIRouter(prefix="/api/v1/academy", tags=["academy"])


class ArticleListItem(BaseModel):
    slug: str
    title: str
    category: str
    summary: str


class ArticleDetail(BaseModel):
    slug: str
    title: str
    category: str
    summary: str
    body: str


@router.get("/articles", response_model=list[ArticleListItem])
def list_articles(category: str | None = None) -> list[ArticleListItem]:
    """List all articles (without body). Optionally filter by category."""
    articles = get_articles(category)
    return [
        ArticleListItem(
            slug=a.slug, title=a.title, category=a.category, summary=a.summary
        )
        for a in articles
    ]


@router.get("/articles/{slug}", response_model=ArticleDetail)
def get_article(slug: str) -> ArticleDetail:
    """Get a single article with full body content."""
    article = get_article_by_slug(slug)
    if article is None:
        raise HTTPException(status_code=404, detail="Article not found")
    return ArticleDetail(
        slug=article.slug,
        title=article.title,
        category=article.category,
        summary=article.summary,
        body=article.body,
    )
