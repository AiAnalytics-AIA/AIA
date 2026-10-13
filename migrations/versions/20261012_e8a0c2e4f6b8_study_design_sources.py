"""Record where a reused research design came from

Project memory M3 (plans/project-memory-reuse.md). A past study's design may start a new or
empty research Study of the same client; ``study_design_sources`` keeps, once per Study, which
study and Design Revision it came from, that revision's content hash, and the labels derived
from every run of it (fictional data, draft report, never run) with the runs and reports they
were read from. Insert-once. Nothing existing changes; a Study that did not reuse a design has
no row.

Revision ID: e8a0c2e4f6b8
Revises: d6f8a0c2e4b6
Created: 2026-10-12 00:00:00.000000+00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = 'e8a0c2e4f6b8'
down_revision: str | None = 'd6f8a0c2e4b6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'study_design_sources',
        sa.Column('study_id', sa.String(length=64), nullable=False),
        sa.Column('organization_id', sa.String(length=64), nullable=False),
        sa.Column('client_id', sa.String(length=64), nullable=False),
        sa.Column('revision_id', sa.String(length=64), nullable=False),
        sa.Column('source_study_id', sa.String(length=64), nullable=False),
        sa.Column('source_revision_id', sa.String(length=64), nullable=False),
        sa.Column('source_revision', sa.Integer(), nullable=False),
        sa.Column('source_content_sha256', sa.String(length=64), nullable=False),
        sa.Column(
            'labels', sa.JSON().with_variant(postgresql.JSONB(), "postgresql"), nullable=False
        ),
        sa.Column('created_by', sa.String(length=64), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            'source_study_id <> study_id',
            name=op.f('ck_study_design_sources_study_design_source_not_itself'),
        ),
        sa.ForeignKeyConstraint(
            ['client_id'],
            ['clients.client_id'],
            name=op.f('fk_study_design_sources_client_id_clients'),
            ondelete='CASCADE',
        ),
        sa.ForeignKeyConstraint(
            ['study_id'],
            ['studies.study_id'],
            name=op.f('fk_study_design_sources_study_id_studies'),
            ondelete='CASCADE',
        ),
        sa.PrimaryKeyConstraint('study_id', name=op.f('pk_study_design_sources')),
    )


def downgrade() -> None:
    op.drop_table('study_design_sources')
