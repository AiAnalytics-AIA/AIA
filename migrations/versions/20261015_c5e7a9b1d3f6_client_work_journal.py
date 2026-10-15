"""The client's own work keeps every answered model request

lifecycle K2d: a document's proposals are asked batch by batch. A step resumed after
its budget was lifted, or after a worker released it, began again at the first batch
and paid for the answered ones again. Each answer is now kept the moment it returns,
keyed by the client and a fingerprint of what was sent, and replayed before anything
is asked.

Revision ID: c5e7a9b1d3f6
Revises: a9c1e3b5d7f2
Created: 2026-10-15 00:00:00.000000+00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "c5e7a9b1d3f6"
down_revision: str | None = "a9c1e3b5d7f2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "client_work_journal",
        sa.Column("journal_id", sa.String(64), primary_key=True),
        sa.Column("organization_id", sa.String(64), nullable=False),
        sa.Column("client_id", sa.String(64), nullable=False),
        sa.Column("request_key", sa.String(64), nullable=False),
        sa.Column("run_id", sa.String(64), nullable=False),
        sa.Column(
            "payload",
            sa.JSON().with_variant(postgresql.JSONB(), "postgresql"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["client_id"],
            ["clients.client_id"],
            name=op.f("fk_client_work_journal_client_id_clients"),
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "client_id",
            "request_key",
            name="client_work_journal_request",
        ),
    )


def downgrade() -> None:
    op.drop_table("client_work_journal")
