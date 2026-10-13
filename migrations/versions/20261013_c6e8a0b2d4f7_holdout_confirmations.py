"""Record a validation Study's confirmation run, once per respondent system

Panel-grounded respondents 7e3 (plans/panel-grounded-respondents.md). When a validation Study's
confirmation run starts, ``holdout_confirmations`` records it with the preregistration it runs
and the respondent system it confirms. A unique constraint on the organization and the system's
fingerprint means a system is confirmed once: several Studies cannot each preregister one system
and keep the run that passed. Insert-once. Nothing existing changes.

Revision ID: c6e8a0b2d4f7
Revises: b4d6f8a0c2e5
Created: 2026-10-13 00:00:00.000000+00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision: str = 'c6e8a0b2d4f7'
down_revision: str | None = 'b4d6f8a0c2e5'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'holdout_confirmations',
        sa.Column('study_id', sa.String(length=64), nullable=False),
        sa.Column('organization_id', sa.String(length=64), nullable=False),
        sa.Column('client_id', sa.String(length=64), nullable=False),
        sa.Column('respondent_system_fingerprint', sa.String(length=64), nullable=False),
        sa.Column('preregistration_sha256', sa.String(length=64), nullable=False),
        sa.Column('run_id', sa.String(length=64), nullable=False),
        sa.Column('started_by', sa.String(length=64), nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ['client_id'],
            ['clients.client_id'],
            name=op.f('fk_holdout_confirmations_client_id_clients'),
            ondelete='CASCADE',
        ),
        sa.ForeignKeyConstraint(
            ['study_id'],
            ['holdout_preregistrations.study_id'],
            name=op.f('fk_holdout_confirmations_study_id_holdout_preregistrations'),
            ondelete='CASCADE',
        ),
        sa.PrimaryKeyConstraint('study_id', name=op.f('pk_holdout_confirmations')),
        sa.UniqueConstraint(
            'organization_id',
            'respondent_system_fingerprint',
            name='holdout_confirmation_once_per_system',
        ),
    )


def downgrade() -> None:
    op.drop_table('holdout_confirmations')
