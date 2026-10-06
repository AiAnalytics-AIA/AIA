"""a paid call's dispatch is recorded on its hold, not only on the attempt

Revision ID: f1a3c5e7b9d2
Revises: e4b7c2d9f6a1
Created: 2026-10-06

``budget_reservations.paid_call_in_flight``: a paid call against this hold was dispatched and its
outcome is not yet recorded. The attempt's single ``paid_call_outcome_known`` flag was closed by
whichever of two concurrent calls answered first, so a worker that died with the other still in
flight was retried instead of being ``RECOVERY_REQUIRED``, and the other call's hold was released
uncharged. The repository now derives "outcome known" from the holds.

Backfill: every open hold of an attempt the old flag calls dispatched-and-unknown is marked in
flight -- the old flag cannot say which hold it meant, so each open one may be it, and recovery
charges them as uncertain exactly as it did before this revision. The column is added with a
server default to fill existing rows, which is then dropped (AGENTS.md § Alembic).

Downgrade drops the column. The attempt's flag is still written from the holds on every metering
write, so after a downgrade it says whether any call was in flight at the last write.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision: str = 'f1a3c5e7b9d2'
down_revision: str | None = 'e4b7c2d9f6a1'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'budget_reservations',
        sa.Column(
            'paid_call_in_flight', sa.Boolean(), nullable=False, server_default=sa.false()
        ),
    )
    op.execute(
        """
        UPDATE budget_reservations
           SET paid_call_in_flight = true
         WHERE status = 'RESERVED'
           AND attempt_id IN (
               SELECT attempt_id FROM step_attempts
                WHERE paid_call_dispatched AND NOT paid_call_outcome_known
           )
        """
    )
    op.alter_column('budget_reservations', 'paid_call_in_flight', server_default=None)


def downgrade() -> None:
    op.drop_column('budget_reservations', 'paid_call_in_flight')
