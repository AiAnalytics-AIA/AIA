"""the approval ledger admits the MVP lane's subjects

Revision ID: 5054d4d610c2
Revises: 57eaa96a5538
Created: 2026-10-20 23:49:12.899441+00:00

Migration M3 of the MVP's lane (``lead-orchestration`` LO16; ``mvp-development-plan.md`` §4),
its first: ``approval_decisions.subject_type`` admits the seven subjects the lane's later chunks
write, all at once, so that no later migration edits the same constraint:

* ``wallet`` -- a wallet raise (LO1, ADR 0028 decision 2);
* ``lead_plan`` -- a plan approved once (LO4, ADR 0028 decision 4);
* ``plan_step`` -- a step the plan authority started (LO3);
* ``chat_start`` -- a start a person typed in the composer (LO5, ADR 0028 decision 3);
* ``data_contract`` -- a client's data contract accepted (``client-data-in-analysis`` 2);
* ``map_snapshot`` -- a map snapshot approved for a report (``report-delivery`` RD4);
* ``sociomap_unlock`` -- a person's unlock of the Sociomap inputs (WCE8, ADR 0029 decision 8).

Nothing writes them yet. The set is listed literally here, as it was when this ran; the model
builds it from ``domain/approval_ledger.py``. The constraint is named with ``op.f`` on drop and
on create (AGENTS.md § Alembic), and the downgrade refuses while the append-only ledger holds a
row of a subject it would no longer admit.
"""

from __future__ import annotations

from alembic import op

revision: str = "5054d4d610c2"
down_revision: str | None = "57eaa96a5538"
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
)
_ADDED = (
    "wallet",
    "lead_plan",
    "plan_step",
    "chat_start",
    "data_contract",
    "map_snapshot",
    "sociomap_unlock",
)


def _check(subjects: tuple[str, ...]) -> str:
    return "subject_type in (" + ",".join(f"'{s}'" for s in subjects) + ")"


def upgrade() -> None:
    op.drop_constraint(op.f(_LEDGER), "approval_decisions", type_="check")
    op.create_check_constraint(op.f(_LEDGER), "approval_decisions", _check(_BEFORE + _ADDED))


def downgrade() -> None:
    held = (
        op.get_bind()
        .exec_driver_sql(
            "SELECT count(*) FROM approval_decisions WHERE subject_type IN ("
            + ",".join(f"'{s}'" for s in _ADDED)
            + ")"
        )
        .scalar()
    )
    if held:
        raise RuntimeError(
            f"{held} decision(s) of the MVP lane's subjects are in the approval ledger, which is "
            "append-only; downgrading would erase them"
        )
    op.drop_constraint(op.f(_LEDGER), "approval_decisions", type_="check")
    op.create_check_constraint(op.f(_LEDGER), "approval_decisions", _check(_BEFORE))
