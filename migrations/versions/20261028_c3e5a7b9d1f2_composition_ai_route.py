"""The AI route each worker start composed, beside its Deep Research reach

Plan lead-orchestration LO12b: the API cannot judge a model call's class against the route,
whose facts (zone, the operator's confirmations, retention, approved classes) exist only in the
worker's environment. The worker now records them in the composition row it already writes at
start (deep-research-web-search 52), so the Lead pane and Settings can say which refusal a turn
would meet. Nullable: a row written before this records no route, and reads as unknown.

Revision ID: c3e5a7b9d1f2
Revises: 2bcb06c19987
Created: 2026-10-28 20:00:00.000000+00:00
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "c3e5a7b9d1f2"
down_revision: str | None = "2bcb06c19987"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "deep_research_compositions",
        sa.Column(
            "ai_route", sa.JSON().with_variant(postgresql.JSONB(), "postgresql"), nullable=True
        ),
    )


def downgrade() -> None:
    op.drop_column("deep_research_compositions", "ai_route")
