"""The item revision a revising knowledge proposal was written from

F-K1 (client-knowledge-lifecycle): an approval did not check whether the item had
changed since the proposal was made, so approving an older edit silently replaced a
newer correction. A revising proposal now records ``base_revision``; an approval whose
base is not the item's current revision is refused unless the reviewer names the
current revision. Existing rows keep null: a pending revision filed before this column
is treated as stale, never as current.

Revision ID: d4f6a8c0e2b5
Revises: b3d5f7a9c1e2
Created: 2026-10-14 00:00:00.000000+00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision: str = "d4f6a8c0e2b5"
down_revision: str | None = "b3d5f7a9c1e2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "client_knowledge_proposals", sa.Column("base_revision", sa.Integer(), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("client_knowledge_proposals", "base_revision")
