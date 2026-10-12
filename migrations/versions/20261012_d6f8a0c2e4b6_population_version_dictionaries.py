"""Keep each population version's field dictionary with it

Population-operations P7a. A version's characteristics (each field's block, evidence status
and permitted uses) are read from its dictionary, whose bytes until now lived only beside the
panel on the host. ``population_version_dictionaries`` keeps them, insert-once, so the API can
show them without an asset source and without reading a respondent row. Nothing existing
changes; a version imported before this table has no row until ``population_ops
record-dictionary`` stores it.

Revision ID: d6f8a0c2e4b6
Revises: c4e6a8b0d2f3
Created: 2026-10-12 00:00:00.000000+00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision: str = 'd6f8a0c2e4b6'
down_revision: str | None = 'c4e6a8b0d2f3'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'population_version_dictionaries',
        sa.Column('version_id', sa.String(length=128), nullable=False),
        sa.Column('sha256', sa.String(length=64), nullable=False),
        sa.Column('byte_size', sa.Integer(), nullable=False),
        sa.Column('content', sa.LargeBinary(), nullable=False),
        sa.Column('recorded_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('recorded_by', sa.String(length=64), nullable=False),
        sa.CheckConstraint(
            'byte_size > 0',
            name=op.f('ck_population_version_dictionaries_population_dictionary_bytes_positive'),
        ),
        sa.ForeignKeyConstraint(
            ['version_id'],
            ['population_dataset_versions.version_id'],
            name=op.f('fk_population_version_dictionaries_version_id_population_dataset_versions'),
        ),
        sa.PrimaryKeyConstraint('version_id', name=op.f('pk_population_version_dictionaries')),
    )


def downgrade() -> None:
    op.drop_table('population_version_dictionaries')
