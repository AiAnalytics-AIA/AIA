"""the approval ledger admits finding reviews

Revision ID: b7d1f3a5c9e2
Revises: 46d0bf6b5121
Created: 2026-10-26 13:00:00+00:00

``approval_decisions.subject_type`` admits ``analysis_finding``: a person's accept, edit, drop or
undo of one key finding of a run (``artifact-analysis`` ANL11, research build spec ``szz/A7``),
subject_id ``<run>:<module>:<index>``. Its writer lands with it.

The set is listed literally here, as it is when this runs; the model builds it from
``domain/approval_ledger.py``. The constraint is named with ``op.f`` on drop and on create
(AGENTS.md § Alembic), and the downgrade refuses while the append-only ledger holds a finding
review, which it would no longer admit.
"""

from __future__ import annotations

from alembic import op

revision: str = "b7d1f3a5c9e2"
down_revision: str | None = "46d0bf6b5121"
branch_labels = None
depends_on = None

_LEDGER = "ck_approval_decisions_approval_subject_type_known"
_BEFORE = (
    "gate",
    "artifact",
    "budget",
    "spend",
    "ai_proposal",
    "design_research",
    "answerability",
    "lead_edit",
    "lead_job_request",
    "lead_self_update",
    "wallet",
    "lead_plan",
    "plan_step",
    "chat_start",
    "data_contract",
    "map_snapshot",
    "sociomap_unlock",
)
_ADDED = ("analysis_finding",)


def _check(subjects: tuple[str, ...]) -> str:
    return "subject_type in (" + ",".join(f"'{s}'" for s in subjects) + ")"


def upgrade() -> None:
    op.drop_constraint(op.f(_LEDGER), "approval_decisions", type_="check")
    op.create_check_constraint(op.f(_LEDGER), "approval_decisions", _check(_BEFORE + _ADDED))


def downgrade() -> None:
    held = (
        op.get_bind()
        .exec_driver_sql(
            "SELECT count(*) FROM approval_decisions WHERE subject_type = 'analysis_finding'"
        )
        .scalar()
    )
    if held:
        raise RuntimeError(
            f"{held} finding review(s) are in the approval ledger, which is append-only; "
            "downgrading would erase them"
        )
    op.drop_constraint(op.f(_LEDGER), "approval_decisions", type_="check")
    op.create_check_constraint(op.f(_LEDGER), "approval_decisions", _check(_BEFORE))
