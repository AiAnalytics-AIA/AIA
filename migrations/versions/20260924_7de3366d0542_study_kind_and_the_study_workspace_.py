"""study kind and the study workspace bridge

ADR 0015. ``studies.kind`` says whether a study is a research or a simulation:
both are studies, with the same scope, lifecycle, permissions, costs and
provenance; only the workflow beneath differs. Existing studies are research,
which is what every study created so far is.

``study_workspaces`` is the AIA-owned binding from a study to the 18.6.6 unit
project holding its working content while the research stages still use the
unit's store: a temporary migration bridge (OI-58), dropped when stage state
moves into AIA's own storage.

Revision ID: 7de3366d0542
Revises: 1cd2a5acd29f
Created: 2026-09-24 16:25:20.517095+00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision: str = '7de3366d0542'
down_revision: str | None = '1cd2a5acd29f'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('study_workspaces',
    sa.Column('study_id', sa.String(length=64), nullable=False),
    sa.Column('organization_id', sa.String(length=64), nullable=False),
    sa.Column('client_id', sa.String(length=64), nullable=False),
    sa.Column('unit_project_id', sa.String(length=160), nullable=False),
    sa.Column('last_stage', sa.String(length=32), nullable=True),
    sa.Column('bound_by', sa.String(length=64), nullable=False),
    sa.Column('bound_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('modified_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['client_id'], ['clients.client_id'], name=op.f('fk_study_workspaces_client_id_clients'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['study_id'], ['studies.study_id'], name=op.f('fk_study_workspaces_study_id_studies'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('study_id', name=op.f('pk_study_workspaces')),
    sa.UniqueConstraint('unit_project_id', name='study_workspace_unit_project_unique')
    )
    op.create_index('ix_study_workspaces_client', 'study_workspaces', ['client_id', 'modified_at'], unique=False)
    op.add_column('studies', sa.Column('kind', sa.String(length=16), server_default='RESEARCH', nullable=False))
    op.create_check_constraint(
        op.f('ck_studies_study_kind_known'), 'studies', "kind in ('RESEARCH','SIMULATION')"
    )


def downgrade() -> None:
    op.drop_constraint(op.f('ck_studies_study_kind_known'), 'studies', type_='check')
    op.drop_column('studies', 'kind')
    op.drop_index('ix_study_workspaces_client', table_name='study_workspaces')
    op.drop_table('study_workspaces')
