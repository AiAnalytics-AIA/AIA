"""the approval ledger admits a Design Research proposal's accept

Revision ID: a7c3e9b1d5f2
Revises: ef96e7f732a2
Created: 2026-10-07

``approval_decisions.subject_type`` admits ``'design_research'``, so a person accepting what a
Design Research run proposed into a new Design Revision (ADR 0019 gate 1, ADR 0021 decision 1;
``deep-research-web-search.md`` chunk 29) is recorded in the same append-only ledger as an agent
job's accept. The constraint is named with ``op.f`` on drop and on create (AGENTS.md § Alembic).
"""

from __future__ import annotations

from alembic import op

revision: str = 'a7c3e9b1d5f2'
down_revision: str | None = 'ef96e7f732a2'
branch_labels = None
depends_on = None

_LEDGER = 'ck_approval_decisions_approval_subject_type_known'


def upgrade() -> None:
    op.drop_constraint(op.f(_LEDGER), 'approval_decisions', type_='check')
    op.create_check_constraint(
        op.f(_LEDGER),
        'approval_decisions',
        "subject_type in ('gate','artifact','budget','spend','ai_proposal','design_research')",
    )


def downgrade() -> None:
    held = op.get_bind().exec_driver_sql(
        "SELECT count(*) FROM approval_decisions WHERE subject_type = 'design_research'"
    ).scalar()
    if held:
        raise RuntimeError(
            f"{held} Design Research accept(s) are in the approval ledger, which is append-only; "
            "downgrading would erase them"
        )
    op.drop_constraint(op.f(_LEDGER), 'approval_decisions', type_='check')
    op.create_check_constraint(
        op.f(_LEDGER),
        'approval_decisions',
        "subject_type in ('gate','artifact','budget','spend','ai_proposal')",
    )
