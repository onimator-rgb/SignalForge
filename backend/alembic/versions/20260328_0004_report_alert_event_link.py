"""Add alert_event_id to analysis_reports for alert→report traceability.

Revision ID: 0004
Revises: 0003
Create Date: 2026-03-28
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "analysis_reports",
        sa.Column(
            "alert_event_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("alert_events.id"),
            nullable=True,
        ),
    )
    op.create_index(
        "idx_report_alert_event", "analysis_reports", ["alert_event_id"]
    )


def downgrade() -> None:
    op.drop_index("idx_report_alert_event", table_name="analysis_reports")
    op.drop_column("analysis_reports", "alert_event_id")
