"""Pin client knowledge edit proposals to their approved base revision.

Revision ID: c8b4e1d9a602
Revises: a7c3e9b1d5f2
"""

import sqlalchemy as sa
from alembic import op

revision = "c8b4e1d9a602"
down_revision = "a7c3e9b1d5f2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Legacy pending edits have no knowable base: leave NULL and require a fresh
    # proposal. Backfilling the current revision would authorize a stale edit.
    op.add_column(
        "client_knowledge_proposals", sa.Column("base_revision", sa.Integer(), nullable=True)
    )
    op.create_check_constraint(
        "knowledge_proposal_base_revision_positive",
        "client_knowledge_proposals",
        "base_revision >= 1",
    )


def downgrade() -> None:
    op.drop_constraint(
        op.f("ck_client_knowledge_proposals_knowledge_proposal_base_revision_positive"),
        "client_knowledge_proposals",
        type_="check",
    )
    op.drop_column("client_knowledge_proposals", "base_revision")
