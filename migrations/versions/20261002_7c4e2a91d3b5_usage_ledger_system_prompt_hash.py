"""usage ledger: the hash of the system prompt exactly as sent

The ledger recorded which prompt *version* a call used (``prompt_id``,
``prompt_version``) and, in ``input_fingerprint``, a hash of everything the call sent.
It could not say which system-prompt bytes ran. With system prompts editable at
runtime (ADR 0020) a version label is no longer enough on its own.

A nullable column: NULL is "not recorded" and is what every existing row keeps. The
ledger is append-only and nothing is rewritten, so no row is stamped with a guess.
``ADD COLUMN`` of a nullable column is a metadata change on PostgreSQL and on SQLite.

Revision ID: 7c4e2a91d3b5
Revises: 5b1d0f3e9a21
Created: 2026-10-02 09:00:00.000000+00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision: str = '7c4e2a91d3b5'
down_revision: str | None = '5b1d0f3e9a21'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'ai_usage_events',
        sa.Column('system_prompt_sha256', sa.String(length=64), nullable=True),
    )


def downgrade() -> None:
    with op.batch_alter_table('ai_usage_events', schema=None) as batch_op:
        batch_op.drop_column('system_prompt_sha256')
