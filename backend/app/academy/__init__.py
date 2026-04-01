"""Academy module — static educational articles about trading concepts."""

from app.academy.content import Article, get_articles, get_article_by_slug

__all__ = ["Article", "get_articles", "get_article_by_slug"]
