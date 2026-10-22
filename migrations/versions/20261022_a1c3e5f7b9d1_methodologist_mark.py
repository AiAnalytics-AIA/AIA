"""The Metodik mark on a membership

Plan settings-backends SB1 (D-14): only a member an OWNER marked "Metodik" stores and puts in
force a methodology version; an OWNER or ADMIN without the mark reads it. The mark is a column
of the membership, not a role. At ship only the product owner holds it (the owner's answer,
2026-10-22): his memberships are marked here where his user exists; an OWNER grants it to others.

Revision ID: a1c3e5f7b9d1
Revises: f4b6d8a0c2e3
Created: 2026-10-22 00:00:00.000000+00:00
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "a1c3e5f7b9d1"
down_revision: str | None = "f4b6d8a0c2e3"
branch_labels = None
depends_on = None

_PRODUCT_OWNER = "nigelblount@art-chain.io"


def upgrade() -> None:
    op.add_column(
        "organization_members",
        sa.Column("methodologist", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    if op.get_bind().dialect.name != "sqlite":  # SQLite cannot alter a column's default
        op.alter_column("organization_members", "methodologist", server_default=None)
    op.execute(
        sa.text(
            "UPDATE organization_members SET methodologist = :yes WHERE user_id IN "
            "(SELECT user_id FROM users WHERE lower(email) = :email)"
        ).bindparams(yes=True, email=_PRODUCT_OWNER)
    )


def downgrade() -> None:
    op.drop_column("organization_members", "methodologist")
