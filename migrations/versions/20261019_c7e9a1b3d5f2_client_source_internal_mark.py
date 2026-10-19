"""a client source a person marks "Interní dokument"

The product owner's decision of 2026-10-19 (ADR 0008 amendment): a client's uploaded source is
Class A, unless a person marks it "Interní dokument" -- an internal AIA document holding
nothing of the client's -- which makes it Class C. ``client_sources`` keeps who marked it and
when; both are null while the source is the client's, and a check keeps them whole. Every mark
and unmark is also an ``access_audit`` row (``CLIENT_SOURCE_MARKED_INTERNAL`` /
``CLIENT_SOURCE_UNMARKED_INTERNAL``).

Existing sources stay unmarked: Class A, as they were. Downgrade drops the two columns and with
them every mark; the audit rows stay.

Revision ID: c7e9a1b3d5f2
Revises: 7b3c32892aa9
Created: 2026-10-19
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "c7e9a1b3d5f2"
down_revision: str | None = "7b3c32892aa9"
branch_labels = None
depends_on = None

_CHECK = "ck_client_sources_internal_mark_whole"


def upgrade() -> None:
    op.add_column("client_sources", sa.Column("internal_marked_by", sa.String(64)))
    op.add_column(
        "client_sources", sa.Column("internal_marked_at", sa.DateTime(timezone=True))
    )
    op.create_check_constraint(
        op.f(_CHECK),
        "client_sources",
        "(internal_marked_by is null) = (internal_marked_at is null)",
    )


def downgrade() -> None:
    op.drop_constraint(op.f(_CHECK), "client_sources", type_="check")
    op.drop_column("client_sources", "internal_marked_at")
    op.drop_column("client_sources", "internal_marked_by")
