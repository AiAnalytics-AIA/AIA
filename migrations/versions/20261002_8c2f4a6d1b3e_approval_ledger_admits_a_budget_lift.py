"""approval ledger admits a budget lift: a person lifts a step's budget wait

Plan ``two-roles-human-ai-gates`` chunk 5b.1. A step that stopped at the study's
budget cap (``AWAITING_BUDGET``) could never go on: nothing resumed it. A person now
lifts the wait, and the decision is written to the append-only ``approval_decisions``
ledger like a gate or a sign-off. The ledger's ``subject_type`` CHECK admitted only
``'gate'`` and ``'artifact'``, so it admits ``'budget'`` too. Nothing else changes and
no row is rewritten.

The downgrade is refused while a ``'budget'`` row exists: the ledger is append-only,
and narrowing the CHECK under such a row would either fail or require deleting a
decision somebody made. It is reversible on a database that holds none.

Revision ID: 8c2f4a6d1b3e
Revises: 5b1d0f3e9a21
Created: 2026-10-02 18:10:00.000000+00:00
"""

from __future__ import annotations

from alembic import op


revision: str = '8c2f4a6d1b3e'
down_revision: str | None = '5b1d0f3e9a21'
branch_labels = None
depends_on = None

_NAME = 'ck_approval_decisions_approval_subject_type_known'


def upgrade() -> None:
    op.drop_constraint(op.f(_NAME), 'approval_decisions', type_='check')
    op.create_check_constraint(
        op.f(_NAME), 'approval_decisions', "subject_type in ('gate','artifact','budget')"
    )


def downgrade() -> None:
    held = op.get_bind().exec_driver_sql(
        "SELECT count(*) FROM approval_decisions WHERE subject_type = 'budget'"
    ).scalar()
    if held:
        raise RuntimeError(
            f"{held} budget decision(s) are in the approval ledger, which is append-only; "
            "downgrading would erase them"
        )
    op.drop_constraint(op.f(_NAME), 'approval_decisions', type_='check')
    op.create_check_constraint(
        op.f(_NAME), 'approval_decisions', "subject_type in ('gate','artifact')"
    )
