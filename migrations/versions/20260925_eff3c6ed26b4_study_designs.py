"""study designs: where a research Study's Design Revisions live

ADR 0016 decision 1. One row per research Study, created on its first submitted
design, pointing at the AIA project whose immutable revisions are the Study's
Design Revisions. ``project_id`` is unique, and RESTRICT on delete: the design a
run executed may not vanish from under the run.

Revision ID: eff3c6ed26b4
Revises: 9c44542f28cc
Created: 2026-09-25 06:58:16.899433+00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision: str = 'eff3c6ed26b4'
down_revision: str | None = '9c44542f28cc'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('study_designs',
    sa.Column('study_id', sa.String(length=64), nullable=False),
    sa.Column('organization_id', sa.String(length=64), nullable=False),
    sa.Column('client_id', sa.String(length=64), nullable=False),
    sa.Column('project_id', sa.String(length=64), nullable=False),
    sa.Column('created_by', sa.String(length=64), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['client_id'], ['clients.client_id'], name=op.f('fk_study_designs_client_id_clients'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['project_id'], ['projects.project_id'], name=op.f('fk_study_designs_project_id_projects'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['study_id'], ['studies.study_id'], name=op.f('fk_study_designs_study_id_studies'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('study_id', name=op.f('pk_study_designs')),
    sa.UniqueConstraint('project_id', name='study_design_project_unique')
    )


def downgrade() -> None:
    op.drop_table('study_designs')
