"""Methodology as data: immutable versions and an append-only activation log

ADR 0023. The methodologist's edits to a method module (its whole specification and any
formula expression it replaces) are rows in ``methodology_versions`` that are never updated
or deleted; ``methodology_activations`` records which version is in force (NULL: the code's
preset), newest row wins, and going back is a new row. Nothing existing changes: with no row
every module runs its code preset, exactly as before this migration.

Revision ID: c4e6a8b0d2f3
Revises: b2d4f6a8c0e1
Created: 2026-10-11 12:00:00.000000+00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = 'c4e6a8b0d2f3'
down_revision: str | None = 'b2d4f6a8c0e1'
branch_labels = None
depends_on = None

JSON = sa.JSON().with_variant(postgresql.JSONB(), 'postgresql')


def upgrade() -> None:
    op.create_table(
        'methodology_versions',
        sa.Column('version_id', sa.String(length=64), nullable=False),
        sa.Column('organization_id', sa.String(length=64), nullable=False),
        sa.Column('module_id', sa.String(length=64), nullable=False),
        sa.Column('version_number', sa.Integer(), nullable=False),
        sa.Column('base_preset', sa.String(length=64), nullable=False),
        sa.Column('payload', JSON, nullable=False),
        sa.Column('payload_sha256', sa.String(length=64), nullable=False),
        sa.Column('note', sa.String(length=500), nullable=False),
        sa.Column('created_by', sa.String(length=64), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint('version_number >= 1', name='methodology_version_positive'),
        sa.PrimaryKeyConstraint('version_id'),
        sa.UniqueConstraint(
            'organization_id', 'module_id', 'version_number', name='uq_methodology_version'
        ),
    )
    op.create_index(
        'ix_methodology_versions_module',
        'methodology_versions',
        ['organization_id', 'module_id', 'version_number'],
    )
    op.create_table(
        'methodology_activations',
        sa.Column('activation_id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('organization_id', sa.String(length=64), nullable=False),
        sa.Column('module_id', sa.String(length=64), nullable=False),
        sa.Column('version_number', sa.Integer(), nullable=True),
        sa.Column('activated_by', sa.String(length=64), nullable=False),
        sa.Column('reason', sa.String(length=500), nullable=False),
        sa.Column('activated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ['organization_id', 'module_id', 'version_number'],
            [
                'methodology_versions.organization_id',
                'methodology_versions.module_id',
                'methodology_versions.version_number',
            ],
        ),
        sa.PrimaryKeyConstraint('activation_id'),
    )
    op.create_index(
        'ix_methodology_activations_module',
        'methodology_activations',
        ['organization_id', 'module_id', 'activation_id'],
    )


def downgrade() -> None:
    op.drop_index('ix_methodology_activations_module', table_name='methodology_activations')
    op.drop_table('methodology_activations')
    op.drop_index('ix_methodology_versions_module', table_name='methodology_versions')
    op.drop_table('methodology_versions')
