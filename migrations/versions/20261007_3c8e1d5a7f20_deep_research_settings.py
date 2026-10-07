"""Deep Research settings as data: immutable versions and an append-only approval log

ADR 0022. Deep Research's policy values (the search provider's terms and price, budgets and
caps, request limits, the light model, quotas, retention, the register and weights, the
extraction denylist and rules) are settings an organization administrator approves. Each
proposed value is a row in ``deep_research_setting_versions`` that is never updated or
deleted; ``deep_research_setting_approvals`` records which version is in force (NULL: the
code's proposed default), newest row wins, and a withdrawal is a new row. Nothing existing
changes: with no row every setting is the code's default, exactly as before this migration.

Revision ID: 3c8e1d5a7f20
Revises: ef96e7f732a2
Created: 2026-10-07 12:00:00.000000+00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = '3c8e1d5a7f20'
down_revision: str | None = 'ef96e7f732a2'
branch_labels = None
depends_on = None

JSON = sa.JSON().with_variant(postgresql.JSONB(), 'postgresql')


def upgrade() -> None:
    op.create_table(
        'deep_research_setting_versions',
        sa.Column('version_id', sa.String(length=64), nullable=False),
        sa.Column('organization_id', sa.String(length=64), nullable=False),
        sa.Column('setting_key', sa.String(length=128), nullable=False),
        sa.Column('version_number', sa.Integer(), nullable=False),
        sa.Column('value', JSON, nullable=False),
        sa.Column('value_sha256', sa.String(length=64), nullable=False),
        sa.Column('source_url', sa.String(length=500), nullable=False),
        sa.Column('note', sa.String(length=255), nullable=False),
        sa.Column('created_by', sa.String(length=64), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint('version_number >= 1', name='dr_setting_version_positive'),
        sa.PrimaryKeyConstraint('version_id'),
        sa.UniqueConstraint(
            'organization_id', 'setting_key', 'version_number', name='uq_dr_setting_version'
        ),
    )
    op.create_index(
        'ix_dr_setting_versions_key',
        'deep_research_setting_versions',
        ['organization_id', 'setting_key', 'version_number'],
    )
    op.create_table(
        'deep_research_setting_approvals',
        sa.Column('approval_id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('organization_id', sa.String(length=64), nullable=False),
        sa.Column('setting_key', sa.String(length=128), nullable=False),
        sa.Column('version_number', sa.Integer(), nullable=True),
        sa.Column('approved_by', sa.String(length=64), nullable=False),
        sa.Column('reason', sa.String(length=255), nullable=False),
        sa.Column('approved_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ['organization_id', 'setting_key', 'version_number'],
            [
                'deep_research_setting_versions.organization_id',
                'deep_research_setting_versions.setting_key',
                'deep_research_setting_versions.version_number',
            ],
        ),
        sa.PrimaryKeyConstraint('approval_id'),
    )
    op.create_index(
        'ix_dr_setting_approvals_key',
        'deep_research_setting_approvals',
        ['organization_id', 'setting_key', 'approval_id'],
    )


def downgrade() -> None:
    op.drop_index('ix_dr_setting_approvals_key', table_name='deep_research_setting_approvals')
    op.drop_table('deep_research_setting_approvals')
    op.drop_index('ix_dr_setting_versions_key', table_name='deep_research_setting_versions')
    op.drop_table('deep_research_setting_versions')
