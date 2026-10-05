"""the approval ledger admits an AI proposal's accept

Revision ID: e4b7c2d9f6a1
Revises: d8e2f4a6b1c3
Created: 2026-10-05

``approval_decisions.subject_type`` admits ``'ai_proposal'``, so a person accepting what a research
agent proposed (ADR 0019 gate 1) is recorded in the same append-only ledger as a gate, a sign-off,
a budget lift and a spend confirmation (plan two-roles-human-ai-gates, 5b.3). The constraint is
named with ``op.f`` on drop and on create: the metadata's naming convention would otherwise prefix
the existing name a second time (AGENTS.md § Alembic).
"""

from __future__ import annotations

from alembic import op


revision: str = 'e4b7c2d9f6a1'
down_revision: str | None = 'd8e2f4a6b1c3'
branch_labels = None
depends_on = None

_LEDGER = 'ck_approval_decisions_approval_subject_type_known'


def upgrade() -> None:
    op.drop_constraint(op.f(_LEDGER), 'approval_decisions', type_='check')
    op.create_check_constraint(
        op.f(_LEDGER),
        'approval_decisions',
        "subject_type in ('gate','artifact','budget','spend','ai_proposal')",
    )


def downgrade() -> None:
    held = op.get_bind().exec_driver_sql(
        "SELECT count(*) FROM approval_decisions WHERE subject_type = 'ai_proposal'"
    ).scalar()
    if held:
        raise RuntimeError(
            f"{held} AI proposal accept(s) are in the approval ledger, which is append-only; "
            "downgrading would erase them"
        )
    op.drop_constraint(op.f(_LEDGER), 'approval_decisions', type_='check')
    op.create_check_constraint(
        op.f(_LEDGER), 'approval_decisions', "subject_type in ('gate','artifact','budget','spend')"
    )
