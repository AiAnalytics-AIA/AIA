"""the approval ledger admits an answerability acknowledgement

Revision ID: d2f4a6c8e0b3
Revises: c5e7a9b1d3f6
Created: 2026-10-16

``approval_decisions.subject_type`` admits ``'answerability'``: a person starting a research run
whose research questions the run cannot all answer (``domain.answerability``; plan
``research-integrity-report`` chunk 1) is recorded in the same append-only ledger as a spend
confirmation. The constraint is named with ``op.f`` on drop and on create (AGENTS.md § Alembic).
"""

from __future__ import annotations

from alembic import op

revision: str = "d2f4a6c8e0b3"
down_revision: str | None = "c5e7a9b1d3f6"
branch_labels = None
depends_on = None

_LEDGER = "ck_approval_decisions_approval_subject_type_known"
_BEFORE = "('gate','artifact','budget','spend','ai_proposal','design_research')"
_AFTER = "('gate','artifact','budget','spend','ai_proposal','design_research','answerability')"


def upgrade() -> None:
    op.drop_constraint(op.f(_LEDGER), "approval_decisions", type_="check")
    op.create_check_constraint(op.f(_LEDGER), "approval_decisions", f"subject_type in {_AFTER}")


def downgrade() -> None:
    held = (
        op.get_bind()
        .exec_driver_sql(
            "SELECT count(*) FROM approval_decisions WHERE subject_type = 'answerability'"
        )
        .scalar()
    )
    if held:
        raise RuntimeError(
            f"{held} answerability acknowledgement(s) are in the approval ledger, which is "
            "append-only; downgrading would erase them"
        )
    op.drop_constraint(op.f(_LEDGER), "approval_decisions", type_="check")
    op.create_check_constraint(op.f(_LEDGER), "approval_decisions", f"subject_type in {_BEFORE}")
