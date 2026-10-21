"""Typed knowledge proposals and decisions: author, decision, reviewed revision

Lifecycle K3 (client-knowledge-lifecycle). A proposal said who wrote it only through
free-form provenance keys, and a decision only through its status and note; an approval
did not record which item revision the reviewer had named. Three nullable columns on
``client_knowledge_proposals``:

* ``author`` -- PERSON, STUDY or AI (``domain.knowledge.KnowledgeAuthor``);
* ``decision`` -- AUTHORED, ACCEPTED, ACCEPTED_OVER or REJECTED (``KnowledgeDecision``),
  checked against the status it settled;
* ``reviewed_revision`` -- the item revision the reviewer named.

Existing rows keep null: nothing is backfilled from notes or provenance, because that would
stamp a guess. The read model reads a null author from the provenance's explicit markers or
as UNKNOWN, and a null decision as unknown. The constraints are named with ``op.f`` (AGENTS.md
§ Alembic). The downgrade drops the columns and what they recorded with them; the decisions'
statuses, notes and revisions stay.

Revision ID: a3c5e7f9b1d4
Revises: 5054d4d610c2
Created: 2026-10-21 00:00:00.000000+00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision: str = "a3c5e7f9b1d4"
down_revision: str | None = "5054d4d610c2"
branch_labels = None
depends_on = None

_TABLE = "client_knowledge_proposals"
_AUTHOR = "ck_client_knowledge_proposals_knowledge_proposal_author_known"
_DECISION = "ck_client_knowledge_proposals_knowledge_proposal_decision_known"


def upgrade() -> None:
    op.add_column(_TABLE, sa.Column("author", sa.String(16), nullable=True))
    op.add_column(_TABLE, sa.Column("decision", sa.String(16), nullable=True))
    op.add_column(_TABLE, sa.Column("reviewed_revision", sa.Integer(), nullable=True))
    op.create_check_constraint(
        op.f(_AUTHOR), _TABLE, "author is null or author in ('PERSON','STUDY','AI')"
    )
    op.create_check_constraint(
        op.f(_DECISION),
        _TABLE,
        "decision is null"
        " or (status = 'REJECTED' and decision = 'REJECTED')"
        " or (status = 'APPROVED' and decision in ('AUTHORED','ACCEPTED','ACCEPTED_OVER'))",
    )


def downgrade() -> None:
    op.drop_constraint(op.f(_DECISION), _TABLE, type_="check")
    op.drop_constraint(op.f(_AUTHOR), _TABLE, type_="check")
    op.drop_column(_TABLE, "reviewed_revision")
    op.drop_column(_TABLE, "decision")
    op.drop_column(_TABLE, "author")
