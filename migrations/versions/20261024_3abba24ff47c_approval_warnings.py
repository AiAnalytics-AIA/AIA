"""the warnings a person approved past, on the approval ledger's row

Revision ID: 3abba24ff47c
Revises: 75f40e2e74dd
Created: 2026-10-24

The client report's checks (report-delivery RD0) warn since 2026-10-22, never refuse (the product
owner: "Warnings for all of it"). What the person was warned of and approved past is kept on the
approval's own row, so who approved past which warning stays on record: ``warnings``, a JSON list
of ``{code, where, message}``. Nullable: NULL where nothing is checked, and every row from before.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = '3abba24ff47c'
down_revision: str | None = '75f40e2e74dd'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'approval_decisions',
        sa.Column(
            'warnings',
            sa.JSON().with_variant(postgresql.JSONB(), 'postgresql'),
            nullable=True,
        ),
    )


def downgrade() -> None:
    held = op.get_bind().exec_driver_sql(
        "SELECT count(*) FROM approval_decisions WHERE warnings IS NOT NULL"
    ).scalar()
    if held:
        raise RuntimeError(
            f"{held} approval(s) record the warnings approved past; the ledger is append-only, "
            "and downgrading would erase them"
        )
    op.drop_column('approval_decisions', 'warnings')
