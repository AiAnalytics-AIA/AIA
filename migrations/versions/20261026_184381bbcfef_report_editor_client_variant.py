"""the client report opens in the report editor (artifact-report RPT13)

Revision ID: 184381bbcfef
Revises: 124dedc8f7b1
Created: 2026-10-26

The product owner decided B2 (a) on 2026-10-26: the client report is edited in the editor too, and
the client deliverable's checks (RD0) are read again on every saved version before its approval.
A report editor line's variant may now be ``client``. The downgrade restores the two variants; it
fails while a client line exists, rather than drop a version a person saved.
"""

from __future__ import annotations

from alembic import op

revision: str = "184381bbcfef"
down_revision: str | None = "124dedc8f7b1"
branch_labels = None
depends_on = None

_NAME = "ck_report_editor_versions_report_editor_version_variant"


def _variants(allowed: str) -> None:
    with op.batch_alter_table("report_editor_versions") as batch:
        batch.drop_constraint(op.f(_NAME), type_="check")
        batch.create_check_constraint(op.f(_NAME), f"variant IN ({allowed})")


def upgrade() -> None:
    _variants("'internal', 'context', 'client'")


def downgrade() -> None:
    _variants("'internal', 'context'")
