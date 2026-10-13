"""Keep a validation Study's preregistration

Panel-grounded respondents 7e2 (plans/panel-grounded-respondents.md). Before a confirmation run
of the respondent system's validation makes its first call, everything that decides its verdict
is fixed in one record; ``holdout_preregistrations`` keeps it once per Study, as its canonical
JSON bytes with their SHA-256, beside the respondent system it validates and that system's
population version. Insert-once. Nothing existing changes.

Revision ID: b4d6f8a0c2e5
Revises: a2c4e6f8b0d3
Created: 2026-10-13 00:00:00.000000+00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision: str = 'b4d6f8a0c2e5'
down_revision: str | None = 'a2c4e6f8b0d3'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'holdout_preregistrations',
        sa.Column('study_id', sa.String(length=64), nullable=False),
        sa.Column('organization_id', sa.String(length=64), nullable=False),
        sa.Column('client_id', sa.String(length=64), nullable=False),
        sa.Column('sha256', sa.String(length=64), nullable=False),
        sa.Column('respondent_system_fingerprint', sa.String(length=64), nullable=False),
        sa.Column('population_version', sa.String(length=128), nullable=False),
        sa.Column('content', sa.LargeBinary(), nullable=False),
        sa.Column('created_by', sa.String(length=64), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ['client_id'],
            ['clients.client_id'],
            name=op.f('fk_holdout_preregistrations_client_id_clients'),
            ondelete='CASCADE',
        ),
        sa.ForeignKeyConstraint(
            ['study_id'],
            ['studies.study_id'],
            name=op.f('fk_holdout_preregistrations_study_id_studies'),
            ondelete='CASCADE',
        ),
        sa.PrimaryKeyConstraint('study_id', name=op.f('pk_holdout_preregistrations')),
    )
    op.create_index(
        'ix_holdout_preregistrations_system',
        'holdout_preregistrations',
        ['organization_id', 'respondent_system_fingerprint'],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index('ix_holdout_preregistrations_system', table_name='holdout_preregistrations')
    op.drop_table('holdout_preregistrations')
