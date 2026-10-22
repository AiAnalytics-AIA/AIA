"""A research run's fieldwork keeps every answered respondent block

run-qc-and-checkpoint RQC0 (OI-64): an attempt began at the first respondent and stored its
dataset only at the end, so an interrupted fieldwork step, or a retry of the run, paid again for
every respondent already answered. Each answer is now kept the moment it returns, keyed by the
study, the run's lineage and a fingerprint of what was sent. This revision adds the table only;
nothing writes it until the executor reads it.

Revision ID: d1f3a5c7e9b2
Revises: 568761e1c719
Created: 2026-10-22 00:00:00.000000+00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "d1f3a5c7e9b2"
down_revision: str | None = "568761e1c719"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "fieldwork_journal",
        sa.Column("journal_id", sa.String(64), primary_key=True),
        sa.Column("organization_id", sa.String(64), nullable=False),
        sa.Column("study_id", sa.String(64), nullable=False),
        sa.Column("lineage_run_id", sa.String(64), nullable=False),
        sa.Column("request_key", sa.String(64), nullable=False),
        sa.Column("run_id", sa.String(64), nullable=False),
        sa.Column(
            "payload",
            sa.JSON().with_variant(postgresql.JSONB(), "postgresql"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["study_id"],
            ["studies.study_id"],
            name=op.f("fk_fieldwork_journal_study_id_studies"),
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "study_id",
            "lineage_run_id",
            "request_key",
            name="fieldwork_journal_request",
        ),
    )


def downgrade() -> None:
    op.drop_table("fieldwork_journal")
