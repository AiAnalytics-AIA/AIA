"""A client deleted: its content gone, its ledgers kept under its id

Plan settings-backends SB5 (study-data-lifecycle SDL3, client part; the owner, 2026-10-22):
deleting a client removes its studies' content, working copies, knowledge, sources, files and
run artifacts, and keeps the money ledger, the approval ledger and the audit with the client's
name replaced by its id. The client and study rows stay as tombstones, so every kept row still
resolves; ``deleted_at`` marks one. A deletion is confirmed by a one-time ticket the preview
issues to the person who asked, for ten minutes; only its hash is kept.

Revision ID: f6b8d0e2a4c7
Revises: e5a7c9d1f3b6
Created: 2026-10-23 03:00:00.000000+00:00
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "f6b8d0e2a4c7"
down_revision: str | None = "e5a7c9d1f3b6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("clients", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("clients", sa.Column("deleted_by", sa.String(64), nullable=True))
    op.create_table(
        "client_deletion_tickets",
        sa.Column("token_sha256", sa.String(64), primary_key=True),
        sa.Column("organization_id", sa.String(64), nullable=False),
        sa.Column("client_id", sa.String(64), nullable=False),
        sa.Column("actor_id", sa.String(64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("spent_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_client_deletion_tickets_client", "client_deletion_tickets", ["client_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_client_deletion_tickets_client", table_name="client_deletion_tickets")
    op.drop_table("client_deletion_tickets")
    op.drop_column("clients", "deleted_by")
    op.drop_column("clients", "deleted_at")
