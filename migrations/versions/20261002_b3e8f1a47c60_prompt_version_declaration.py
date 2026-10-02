"""a prompt version records its author's declaration that it holds no client data

ADR 0020 decision 8. A stored prompt edit is free text, so it needs a data class before it can
be sent to a model. The author's declaration, made when they save the version, classifies it
automatically; the declared class, who made it and when are kept on the version.

All three columns are nullable and existing rows keep NULL: a version saved before this
change has no declaration, and "no declaration" must never read as "declared". Such a version
stays unclassified, and so unsent, until an operator classifies its exact text. Adding
nullable columns is a metadata change on PostgreSQL; nothing is rewritten.

Revision ID: b3e8f1a47c60
Revises: 9d1f6b3a4c28
Created: 2026-10-02 19:00:00.000000+00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision: str = 'b3e8f1a47c60'
down_revision: str | None = '9d1f6b3a4c28'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'ai_prompt_versions', sa.Column('declared_class', sa.String(length=64), nullable=True)
    )
    op.add_column(
        'ai_prompt_versions', sa.Column('declared_by', sa.String(length=64), nullable=True)
    )
    op.add_column(
        'ai_prompt_versions', sa.Column('declared_at', sa.DateTime(timezone=True), nullable=True)
    )


def downgrade() -> None:
    with op.batch_alter_table('ai_prompt_versions', schema=None) as batch_op:
        batch_op.drop_column('declared_at')
        batch_op.drop_column('declared_by')
        batch_op.drop_column('declared_class')
