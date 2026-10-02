"""system prompts as data: immutable versions and an append-only activation log

ADR 0019. A system prompt's instruction can be edited at runtime by an organization
administrator. Each edit is a row in ``ai_prompt_versions`` that is never updated or
deleted; ``ai_prompt_activations`` records which version an organization runs for a
prompt (NULL: the wording shipped in code), newest row wins, and a rollback is a new
row. Nothing existing changes: with no row the code's wording runs, exactly as
before this migration.

The activation's composite foreign key makes "activate a version that does not
exist" a database error as well as an application one. A NULL ``version_number``
(baseline) is not checked against it, by SQL's rule for NULL in a composite key.

Revision ID: 9d1f6b3a4c28
Revises: 7c4e2a91d3b5
Created: 2026-10-02 10:00:00.000000+00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision: str = '9d1f6b3a4c28'
down_revision: str | None = '7c4e2a91d3b5'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'ai_prompt_versions',
        sa.Column('version_id', sa.String(length=64), nullable=False),
        sa.Column('organization_id', sa.String(length=64), nullable=False),
        sa.Column('prompt_id', sa.String(length=128), nullable=False),
        sa.Column('version_number', sa.Integer(), nullable=False),
        sa.Column('text', sa.Text(), nullable=False),
        sa.Column('text_sha256', sa.String(length=64), nullable=False),
        sa.Column('based_on', sa.String(length=64), nullable=False),
        sa.Column('note', sa.String(length=255), nullable=False),
        sa.Column('created_by', sa.String(length=64), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint('version_number >= 1', name='ai_prompt_version_positive'),
        sa.PrimaryKeyConstraint('version_id'),
        sa.UniqueConstraint(
            'organization_id', 'prompt_id', 'version_number', name='uq_ai_prompt_version'
        ),
    )
    op.create_index(
        'ix_ai_prompt_versions_prompt',
        'ai_prompt_versions',
        ['organization_id', 'prompt_id', 'version_number'],
    )
    op.create_table(
        'ai_prompt_activations',
        sa.Column('activation_id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('organization_id', sa.String(length=64), nullable=False),
        sa.Column('prompt_id', sa.String(length=128), nullable=False),
        sa.Column('version_number', sa.Integer(), nullable=True),
        sa.Column('activated_by', sa.String(length=64), nullable=False),
        sa.Column('reason', sa.String(length=255), nullable=False),
        sa.Column('activated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ['organization_id', 'prompt_id', 'version_number'],
            [
                'ai_prompt_versions.organization_id',
                'ai_prompt_versions.prompt_id',
                'ai_prompt_versions.version_number',
            ],
        ),
        sa.PrimaryKeyConstraint('activation_id'),
    )
    op.create_index(
        'ix_ai_prompt_activations_prompt',
        'ai_prompt_activations',
        ['organization_id', 'prompt_id', 'activation_id'],
    )


def downgrade() -> None:
    op.drop_index('ix_ai_prompt_activations_prompt', table_name='ai_prompt_activations')
    op.drop_table('ai_prompt_activations')
    op.drop_index('ix_ai_prompt_versions_prompt', table_name='ai_prompt_versions')
    op.drop_table('ai_prompt_versions')
