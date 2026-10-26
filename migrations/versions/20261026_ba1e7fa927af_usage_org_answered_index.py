"""each activity's last answered call: the answered rows indexed by organization and agent

Revision ID: ba1e7fa927af
Revises: 7db4e0f96181
Created: 2026-10-26 01:00:00+00:00

settings-redesign F14 (OI-75 (a), the product owner 2026-10-25): Settings → AI běh shows each
activity's last answered call, an organization-level aggregate of the usage ledger. The ledger is
append-only and grows with every model call; without an index the aggregate reads the
organization's whole ledger on every open. This partial index holds the ``SUCCEEDED`` rows alone,
by organization, agent and time, so each agent's newest answered call is one index lookup. No row
changes; the downgrade drops the index.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "ba1e7fa927af"
down_revision: str | None = "7db4e0f96181"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "ix_usage_org_answered",
        "ai_usage_events",
        ["organization_id", "agent_id", "occurred_at"],
        postgresql_where=sa.text("outcome = 'SUCCEEDED'"),
        sqlite_where=sa.text("outcome = 'SUCCEEDED'"),
    )


def downgrade() -> None:
    op.drop_index("ix_usage_org_answered", table_name="ai_usage_events")
