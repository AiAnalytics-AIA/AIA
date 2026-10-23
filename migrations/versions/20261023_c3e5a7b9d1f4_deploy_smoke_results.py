"""A deployment's smoke results, kept for Settings → Stav systému

Plan settings-backends SB4: ``bin/smoke.sh`` proves each develop deploy and prints one line
per check; nothing kept them, so Settings could not say whether the running deployment
passed. One row per check per smoke run: its label, its result (ok / FAIL / NOT_RUNNABLE)
and its place in the run. No detail line, URL or response body is kept.

Revision ID: c3e5a7b9d1f4
Revises: f4b6d8a0c2e3
Created: 2026-10-23 00:00:00.000000+00:00
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "c3e5a7b9d1f4"
down_revision: str | None = "f4b6d8a0c2e3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "deploy_smoke_results",
        sa.Column("result_id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("run_id", sa.String(64), nullable=False),
        sa.Column("build_sha", sa.String(64), nullable=False),
        sa.Column("position", sa.Integer, nullable=False),
        sa.Column("check_label", sa.String(300), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("ran_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status in ('ok', 'FAIL', 'NOT_RUNNABLE')",
            name=op.f("ck_deploy_smoke_results_status_known"),
        ),
        sa.UniqueConstraint(
            "run_id", "position", name=op.f("uq_deploy_smoke_results_run_id_position")
        ),
    )
    op.create_index("ix_deploy_smoke_results_ran_at", "deploy_smoke_results", ["ran_at"])


def downgrade() -> None:
    op.drop_index("ix_deploy_smoke_results_ran_at", table_name="deploy_smoke_results")
    op.drop_table("deploy_smoke_results")
