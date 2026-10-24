"""the edit starts a report editor's pages report (artifact-report RPT8f)

Revision ID: 9c1e3a5b7d2f
Revises: 3abba24ff47c
Created: 2026-10-24

An edited report's approval is decided by the server: each page reports its edit starts (its own
count from 1) and when its changes reached the Document Server; AIA keeps the newest of each per
session and page with the time it received it, and an approval is refused (409
``report_edits_unsaved``) while one is held by no save of the version. ``report_editor_versions``
gains ``content_at`` and ``last_saved_at``: what the latest save of a version's exact bytes said it
holds, so a later save that changed nothing still releases the hold. None of it is a decision,
only the editor's working state: the downgrade drops it.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "9c1e3a5b7d2f"
down_revision: str | None = "3abba24ff47c"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for column in ("content_at", "last_saved_at"):
        op.add_column(
            "report_editor_versions", sa.Column(column, sa.DateTime(timezone=True), nullable=True)
        )
    op.create_table(
        "report_editor_edits",
        sa.Column("document_key", sa.String(length=128), nullable=False),
        sa.Column("page", sa.String(length=64), nullable=False),
        sa.Column("organization_id", sa.String(length=64), nullable=False),
        sa.Column("client_id", sa.String(length=64), nullable=False),
        sa.Column("study_id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("clean_seq", sa.Integer(), nullable=False),
        sa.Column("clean_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["document_key"],
            ["report_editor_sessions.document_key"],
            name=op.f("fk_report_editor_edits_document_key_report_editor_sessions"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("document_key", "page", name=op.f("pk_report_editor_edits")),
    )


def downgrade() -> None:
    op.drop_table("report_editor_edits")
    op.drop_column("report_editor_versions", "last_saved_at")
    op.drop_column("report_editor_versions", "content_at")
