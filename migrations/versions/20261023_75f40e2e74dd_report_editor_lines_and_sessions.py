"""The report editor's lines, versions and sessions (artifact-report RPT8c)

A line starts at a draft code composed (its koncept 1, the composer's artifact, whose id is the
line's) and each save the Document Server sends is its next version, an artifact of its own
beside what it changed. A line's editing session has one document key, so every researcher who
opens it joins the same co-editing session; at most one is open per line. Every artifact a row
names cascades to it, so a deleted study's versions and sessions go with its artifacts. Both
tables are new and empty: the downgrade drops them.

Revision ID: 75f40e2e74dd
Revises: f6b8d0e2a4c7
Created: 2026-10-23 07:48:40.954591+00:00
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "75f40e2e74dd"
down_revision: str | None = "f6b8d0e2a4c7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "report_editor_sessions",
        sa.Column("document_key", sa.String(length=128), nullable=False),
        sa.Column("line_id", sa.String(length=64), nullable=False),
        sa.Column("session_no", sa.Integer(), nullable=False),
        sa.Column("version_artifact_id", sa.String(length=64), nullable=False),
        sa.Column("organization_id", sa.String(length=64), nullable=False),
        sa.Column("client_id", sa.String(length=64), nullable=False),
        sa.Column("study_id", sa.String(length=64), nullable=False),
        sa.Column("run_id", sa.String(length=64), nullable=False),
        sa.Column(
            "users", sa.JSON().with_variant(postgresql.JSONB(), "postgresql"), nullable=False
        ),
        sa.Column("opened_by", sa.String(length=64), nullable=False),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closed_reason", sa.String(length=16), nullable=True),
        sa.Column("last_problem", sa.String(length=64), nullable=True),
        sa.Column("last_problem_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["line_id"],
            ["project_artifacts.artifact_id"],
            name=op.f("fk_report_editor_sessions_line_id_project_artifacts"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["study_id"],
            ["studies.study_id"],
            name=op.f("fk_report_editor_sessions_study_id_studies"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["version_artifact_id"],
            ["project_artifacts.artifact_id"],
            name=op.f("fk_report_editor_sessions_version_artifact_id_project_artifacts"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("document_key", name=op.f("pk_report_editor_sessions")),
        sa.UniqueConstraint("line_id", "session_no", name="uq_report_editor_sessions_no"),
    )
    op.create_index(
        "uq_report_editor_sessions_open",
        "report_editor_sessions",
        ["line_id"],
        unique=True,
        postgresql_where=sa.text("closed_at IS NULL"),
        sqlite_where=sa.text("closed_at IS NULL"),
    )
    op.create_table(
        "report_editor_versions",
        sa.Column("artifact_id", sa.String(length=64), nullable=False),
        sa.Column("line_id", sa.String(length=64), nullable=False),
        sa.Column("koncept", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.String(length=64), nullable=False),
        sa.Column("client_id", sa.String(length=64), nullable=False),
        sa.Column("study_id", sa.String(length=64), nullable=False),
        sa.Column("run_id", sa.String(length=64), nullable=False),
        sa.Column("variant", sa.String(length=16), nullable=False),
        sa.Column("deep_research_run_id", sa.String(length=64), nullable=True),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("changes_artifact_id", sa.String(length=64), nullable=True),
        sa.Column(
            "authors", sa.JSON().with_variant(postgresql.JSONB(), "postgresql"), nullable=False
        ),
        sa.Column("saved_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "variant IN ('internal', 'context')",
            name=op.f("ck_report_editor_versions_report_editor_version_variant"),
        ),
        sa.CheckConstraint(
            "koncept >= 1",
            name=op.f("ck_report_editor_versions_report_editor_version_koncept_positive"),
        ),
        sa.ForeignKeyConstraint(
            ["artifact_id"],
            ["project_artifacts.artifact_id"],
            name=op.f("fk_report_editor_versions_artifact_id_project_artifacts"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["changes_artifact_id"],
            ["project_artifacts.artifact_id"],
            name=op.f("fk_report_editor_versions_changes_artifact_id_project_artifacts"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["line_id"],
            ["project_artifacts.artifact_id"],
            name=op.f("fk_report_editor_versions_line_id_project_artifacts"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["study_id"],
            ["studies.study_id"],
            name=op.f("fk_report_editor_versions_study_id_studies"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("artifact_id", name=op.f("pk_report_editor_versions")),
        sa.UniqueConstraint("line_id", "koncept", name="uq_report_editor_versions_koncept"),
        sa.UniqueConstraint("line_id", "sha256", name="uq_report_editor_versions_sha256"),
    )
    op.create_index(
        "ix_report_editor_versions_run",
        "report_editor_versions",
        ["study_id", "run_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_report_editor_versions_run", table_name="report_editor_versions")
    op.drop_table("report_editor_versions")
    op.drop_index(
        "uq_report_editor_sessions_open",
        table_name="report_editor_sessions",
        postgresql_where=sa.text("closed_at IS NULL"),
        sqlite_where=sa.text("closed_at IS NULL"),
    )
    op.drop_table("report_editor_sessions")
