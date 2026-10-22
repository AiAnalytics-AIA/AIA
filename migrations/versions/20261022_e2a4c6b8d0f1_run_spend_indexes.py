"""A run's spend is read by its run, not by scanning its study

artifact-fieldwork FLD4: a research run's Progress reads the run's own usage-ledger rows and
budget holds on every poll. Both tables were indexed by study, attempt and person, never by run,
so each read walked the study's whole history. Indexes only; no row changes.

Revision ID: e2a4c6b8d0f1
Revises: d1f3a5c7e9b2
Created: 2026-10-22 00:00:00.000000+00:00
"""

from __future__ import annotations

from alembic import op


revision: str = "e2a4c6b8d0f1"
down_revision: str | None = "d1f3a5c7e9b2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index("ix_usage_run", "ai_usage_events", ["run_id"])
    op.create_index("ix_reservations_run", "budget_reservations", ["run_id"])


def downgrade() -> None:
    op.drop_index("ix_reservations_run", table_name="budget_reservations")
    op.drop_index("ix_usage_run", table_name="ai_usage_events")
