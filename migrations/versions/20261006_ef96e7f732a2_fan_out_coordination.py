"""host politeness and model concurrency slots, shared by every worker process

Revision ID: ef96e7f732a2
Revises: f1a3c5e7b9d2
Created: 2026-10-06

Deep Research fan-out (plan ``deep-research-web-search.md`` chunk 21,
``docs/architecture/deep-research-fan-out.md``). Two tables, each written only by
``infrastructure/fan_out_coordination.py``, in short transactions of their own:

* ``host_politeness`` -- one row per public host: the request holding it now
  (``holder_token``, ``held_until``) and the earliest instant the next may start
  (``next_allowed_at``). Keyed by host alone: a crawl delay is owed by AIA's user agent.
* ``model_concurrency_slots`` -- one row per ``(pool, slot)``: free, or held by one
  request of one attempt (``holder_attempt_id``, ``holder_token``).

Neither holds study data and neither references another table: a slot's holder is read
for its liveness only, so a deleted attempt is simply not live. Both start empty and
fill themselves; nothing is backfilled. Downgrade drops both: they hold only what is in
flight now, and a worker that loses them waits nothing and limits nothing -- which is why
the fan-out switch must be off before a downgrade.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision: str = 'ef96e7f732a2'
down_revision: str | None = 'f1a3c5e7b9d2'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'host_politeness',
        sa.Column('host', sa.String(length=255), nullable=False),
        sa.Column('next_allowed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('holder_token', sa.String(length=64), nullable=True),
        sa.Column('held_until', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('host'),
    )
    op.create_index('ix_host_politeness_updated', 'host_politeness', ['updated_at'])
    op.create_table(
        'model_concurrency_slots',
        sa.Column('pool', sa.String(length=128), nullable=False),
        sa.Column('slot', sa.Integer(), nullable=False),
        sa.Column('holder_attempt_id', sa.String(length=64), nullable=True),
        sa.Column('holder_token', sa.String(length=64), nullable=True),
        sa.Column('acquired_at', sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint('slot >= 0', name='model_slot_non_negative'),
        sa.PrimaryKeyConstraint('pool', 'slot'),
    )


def downgrade() -> None:
    op.drop_table('model_concurrency_slots')
    op.drop_index('ix_host_politeness_updated', table_name='host_politeness')
    op.drop_table('host_politeness')
