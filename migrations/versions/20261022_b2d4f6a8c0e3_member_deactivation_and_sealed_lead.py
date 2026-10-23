"""A membership deactivated in its organization, and the member's Lead sealed

Plan settings-backends SB2 (D-27, ADR 0030): an OWNER or ADMIN deactivates a member of their
own organization (not the account everywhere, S15); the member's Research Lead is sealed at
once, unreadable by anyone, and erased after 30 days (the owner's answer, 2026-10-22); a
reactivation within the 30 days unseals it for that member.

Revision ID: b2d4f6a8c0e3
Revises: f4b6d8a0c2e3
Created: 2026-10-22 00:00:00.000000+00:00
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "b2d4f6a8c0e3"
down_revision: str | None = "f4b6d8a0c2e3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "organization_members", sa.Column("deactivated_at", sa.DateTime(timezone=True))
    )
    op.add_column("organization_members", sa.Column("deactivated_by", sa.String(64)))
    op.add_column("researcher_leads", sa.Column("sealed_at", sa.DateTime(timezone=True)))
    op.add_column("researcher_leads", sa.Column("erase_after", sa.DateTime(timezone=True)))
    op.create_index("ix_researcher_leads_erase_after", "researcher_leads", ["erase_after"])


def downgrade() -> None:
    op.drop_index("ix_researcher_leads_erase_after", table_name="researcher_leads")
    op.drop_column("researcher_leads", "erase_after")
    op.drop_column("researcher_leads", "sealed_at")
    op.drop_column("organization_members", "deactivated_by")
    op.drop_column("organization_members", "deactivated_at")
