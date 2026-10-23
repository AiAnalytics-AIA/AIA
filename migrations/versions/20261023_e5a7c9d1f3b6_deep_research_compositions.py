"""What each worker's Deep Research composition reaches, recorded at its start

Plan deep-research-web-search 52, settings-backends SB6 (Dosah): which routes and connectors a
run can use was written by hand in the docs and was wrong; only the worker's composition knows.
Each worker start keeps one row: the routes the code builds, each active, built (not composed,
by which switch) or refused, with its classes and price. Settings reads the newest.

Revision ID: e5a7c9d1f3b6
Revises: d4f6b8c0e2a5
Created: 2026-10-23 02:00:00.000000+00:00
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "e5a7c9d1f3b6"
down_revision: str | None = "d4f6b8c0e2a5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "deep_research_compositions",
        sa.Column("composition_id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("worker", sa.String(128), nullable=False),
        sa.Column("build_sha", sa.String(64), nullable=True),
        sa.Column("composed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("agent_directed", sa.Boolean, nullable=False),
        sa.Column("class_gates", sa.String(16), nullable=True),
        sa.Column("routes", sa.JSON().with_variant(postgresql.JSONB(), "postgresql"), nullable=False),
    )
    op.create_index(
        "ix_deep_research_compositions_composed_at", "deep_research_compositions", ["composed_at"]
    )


def downgrade() -> None:
    op.drop_index(
        "ix_deep_research_compositions_composed_at", table_name="deep_research_compositions"
    )
    op.drop_table("deep_research_compositions")
