"""client knowledge proposals and revisions

ADR 0015 decision 7. A client's own knowledge -- sources, documents, datasets,
approved facts and findings, terminology, entities, dimensions, audiences,
artifacts -- belongs to the client, not to one study: the narrow amendment to
ADR 0004 rule 1. Every row carries organization_id and client_id.

A study never writes an item. It proposes (client_knowledge_proposals); a
person decides; an approval creates or revises an item and appends a revision
(client_knowledge_revisions, append-only), numbering the client's knowledge as
a whole by context_revision. Nothing to backfill: no knowledge existed before.

Revision ID: 9c44542f28cc
Revises: 7de3366d0542
Created: 2026-09-24 16:31:58.388617+00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '9c44542f28cc'
down_revision: str | None = '7de3366d0542'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('client_knowledge_items',
    sa.Column('item_id', sa.String(length=64), nullable=False),
    sa.Column('organization_id', sa.String(length=64), nullable=False),
    sa.Column('client_id', sa.String(length=64), nullable=False),
    sa.Column('kind', sa.String(length=32), nullable=False),
    sa.Column('title', sa.String(length=255), nullable=False),
    sa.Column('summary', sa.Text(), nullable=False),
    sa.Column('content', sa.JSON().with_variant(postgresql.JSONB(), "postgresql"), nullable=False),
    sa.Column('status', sa.String(length=16), nullable=False),
    sa.Column('current_revision', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('modified_at', sa.DateTime(timezone=True), nullable=False),
    sa.CheckConstraint("kind in ('SOURCE','DOCUMENT','DATASET','FACT','FINDING','TERM','ENTITY','DIMENSION','AUDIENCE','ARTIFACT')", name=op.f('ck_client_knowledge_items_knowledge_item_kind_known')),
    sa.CheckConstraint("status in ('ACTIVE','RETIRED')", name=op.f('ck_client_knowledge_items_knowledge_item_status_known')),
    sa.CheckConstraint('current_revision >= 1', name=op.f('ck_client_knowledge_items_knowledge_item_revision_positive')),
    sa.ForeignKeyConstraint(['client_id'], ['clients.client_id'], name=op.f('fk_client_knowledge_items_client_id_clients'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('item_id', name=op.f('pk_client_knowledge_items'))
    )
    op.create_index('ix_client_knowledge_items_client', 'client_knowledge_items', ['client_id', 'kind', 'status'], unique=False)
    op.create_table('client_knowledge_proposals',
    sa.Column('proposal_id', sa.String(length=64), nullable=False),
    sa.Column('organization_id', sa.String(length=64), nullable=False),
    sa.Column('client_id', sa.String(length=64), nullable=False),
    sa.Column('study_id', sa.String(length=64), nullable=True),
    sa.Column('item_id', sa.String(length=64), nullable=True),
    sa.Column('kind', sa.String(length=32), nullable=False),
    sa.Column('title', sa.String(length=255), nullable=False),
    sa.Column('summary', sa.Text(), nullable=False),
    sa.Column('content', sa.JSON().with_variant(postgresql.JSONB(), "postgresql"), nullable=False),
    sa.Column('provenance', sa.JSON().with_variant(postgresql.JSONB(), "postgresql"), nullable=False),
    sa.Column('status', sa.String(length=16), nullable=False),
    sa.Column('proposed_by', sa.String(length=64), nullable=False),
    sa.Column('proposed_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('decided_by', sa.String(length=64), nullable=True),
    sa.Column('decided_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('decision_note', sa.Text(), nullable=False),
    sa.Column('revision', sa.Integer(), nullable=True),
    sa.CheckConstraint("kind in ('SOURCE','DOCUMENT','DATASET','FACT','FINDING','TERM','ENTITY','DIMENSION','AUDIENCE','ARTIFACT')", name=op.f('ck_client_knowledge_proposals_knowledge_proposal_kind_known')),
    sa.CheckConstraint("status in ('PROPOSED','APPROVED','REJECTED')", name=op.f('ck_client_knowledge_proposals_knowledge_proposal_status_known')),
    sa.ForeignKeyConstraint(['client_id'], ['clients.client_id'], name=op.f('fk_client_knowledge_proposals_client_id_clients'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['item_id'], ['client_knowledge_items.item_id'], name=op.f('fk_client_knowledge_proposals_item_id_client_knowledge_items'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['study_id'], ['studies.study_id'], name=op.f('fk_client_knowledge_proposals_study_id_studies'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('proposal_id', name=op.f('pk_client_knowledge_proposals'))
    )
    op.create_index('ix_client_knowledge_proposals_client', 'client_knowledge_proposals', ['client_id', 'status'], unique=False)
    op.create_table('client_knowledge_revisions',
    sa.Column('item_id', sa.String(length=64), nullable=False),
    sa.Column('revision', sa.Integer(), nullable=False),
    sa.Column('organization_id', sa.String(length=64), nullable=False),
    sa.Column('client_id', sa.String(length=64), nullable=False),
    sa.Column('context_revision', sa.Integer(), nullable=False),
    sa.Column('title', sa.String(length=255), nullable=False),
    sa.Column('summary', sa.Text(), nullable=False),
    sa.Column('content', sa.JSON().with_variant(postgresql.JSONB(), "postgresql"), nullable=False),
    sa.Column('status', sa.String(length=16), nullable=False),
    sa.Column('provenance', sa.JSON().with_variant(postgresql.JSONB(), "postgresql"), nullable=False),
    sa.Column('proposal_id', sa.String(length=64), nullable=True),
    sa.Column('approved_by', sa.String(length=64), nullable=False),
    sa.Column('approved_at', sa.DateTime(timezone=True), nullable=False),
    sa.CheckConstraint("status in ('ACTIVE','RETIRED')", name=op.f('ck_client_knowledge_revisions_knowledge_revision_status_known')),
    sa.ForeignKeyConstraint(['client_id'], ['clients.client_id'], name=op.f('fk_client_knowledge_revisions_client_id_clients'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['item_id'], ['client_knowledge_items.item_id'], name=op.f('fk_client_knowledge_revisions_item_id_client_knowledge_items'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('item_id', 'revision', name=op.f('pk_client_knowledge_revisions')),
    sa.UniqueConstraint('client_id', 'context_revision', name='knowledge_context_revision_unique')
    )


def downgrade() -> None:
    op.drop_table('client_knowledge_revisions')
    op.drop_index('ix_client_knowledge_proposals_client', table_name='client_knowledge_proposals')
    op.drop_table('client_knowledge_proposals')
    op.drop_index('ix_client_knowledge_items_client', table_name='client_knowledge_items')
    op.drop_table('client_knowledge_items')
