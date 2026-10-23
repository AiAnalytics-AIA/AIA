"""A proposed Deep Research setting is withdrawn or declined, on the record

Plan settings-backends (the Settings redesign's "Stáhnout návrh"): a setting version is
immutable (ADR 0022) and the approval log names only what was put in force, so a proposal
nobody wanted stayed "pending" for ever, and nothing recorded that someone turned it down.
One row per version, at most once: WITHDRAWN when its proposer takes it back, DECLINED when
another administrator turns it down; append-only, never updated, and a version with one is
never approved.

Revision ID: d4f6b8c0e2a5
Revises: f4b6d8a0c2e3
Created: 2026-10-23 01:00:00.000000+00:00
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "d4f6b8c0e2a5"
down_revision: str | None = "f4b6d8a0c2e3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "deep_research_setting_declines",
        sa.Column("decline_id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("organization_id", sa.String(64), nullable=False),
        sa.Column("setting_key", sa.String(128), nullable=False),
        sa.Column("version_number", sa.Integer, nullable=False),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("declined_by", sa.String(64), nullable=False),
        sa.Column("reason", sa.String(255), nullable=False),
        sa.Column("declined_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["organization_id", "setting_key", "version_number"],
            [
                "deep_research_setting_versions.organization_id",
                "deep_research_setting_versions.setting_key",
                "deep_research_setting_versions.version_number",
            ],
            name="fk_dr_setting_declines_version",
        ),
        sa.CheckConstraint(
            "kind in ('WITHDRAWN', 'DECLINED')",
            name=op.f("ck_deep_research_setting_declines_dr_setting_decline_kind"),
        ),
        sa.UniqueConstraint(
            "organization_id", "setting_key", "version_number", name="uq_dr_setting_decline"
        ),
    )


def downgrade() -> None:
    op.drop_table("deep_research_setting_declines")
