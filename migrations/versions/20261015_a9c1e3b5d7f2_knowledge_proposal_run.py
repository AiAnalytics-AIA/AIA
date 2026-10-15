"""The run that proposed a client knowledge proposal

lifecycle K2d2: AI proposals from a client's document are filed by a run of the client's
own work, once per run, so a retried step never files them twice. Every other proposal
keeps null.

Revision ID: a9c1e3b5d7f2
Revises: b3d5f7a9c1e4
Created: 2026-10-15 00:00:00.000000+00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision: str = "a9c1e3b5d7f2"
down_revision: str | None = "b3d5f7a9c1e4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "client_knowledge_proposals", sa.Column("run_id", sa.String(64), nullable=True)
    )
    op.create_index(
        "ix_client_knowledge_proposals_run", "client_knowledge_proposals", ["run_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_client_knowledge_proposals_run", table_name="client_knowledge_proposals")
    op.drop_column("client_knowledge_proposals", "run_id")
