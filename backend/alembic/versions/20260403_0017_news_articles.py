"""Add news_articles table for multi-source news aggregation.

Revision ID: 0017
Revises: 0016
Create Date: 2026-04-03
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0017"
down_revision: Union[str, None] = "0016"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "news_articles",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("source", sa.String(50), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("content_snippet", sa.Text(), nullable=True),
        sa.Column("original_url", sa.Text(), nullable=True),
        sa.Column("symbols_mentioned", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("asset_class", sa.String(10), nullable=True),
        sa.Column("source_sentiment", sa.String(20), nullable=True),
        sa.Column("source_sentiment_score", sa.Float(), nullable=True),
        sa.Column("reliability_score", sa.Float(), nullable=False, server_default="0.5"),
        sa.Column("cross_source_count", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("is_verified", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("duplicate_of_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("ai_sentiment", sa.String(20), nullable=True),
        sa.Column("ai_sentiment_score", sa.Float(), nullable=True),
        sa.Column("ai_impact_level", sa.String(20), nullable=True),
        sa.Column("ai_analysis", sa.Text(), nullable=True),
        sa.Column("language", sa.String(5), nullable=True, server_default="en"),
        sa.Column("categories", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("raw_data", postgresql.JSONB(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index("idx_news_fetched", "news_articles", ["fetched_at"])
    op.create_index("idx_news_source", "news_articles", ["source", "fetched_at"])
    op.create_index("idx_news_reliability", "news_articles", ["reliability_score"])
    op.create_index("idx_news_symbols", "news_articles", ["symbols_mentioned"], postgresql_using="gin")


def downgrade() -> None:
    op.drop_index("idx_news_symbols", table_name="news_articles")
    op.drop_index("idx_news_reliability", table_name="news_articles")
    op.drop_index("idx_news_source", table_name="news_articles")
    op.drop_index("idx_news_fetched", table_name="news_articles")
    op.drop_table("news_articles")
