"""the approval ledger admits lead cards

Revision ID: 124dedc8f7b1
Revises: 46d0bf6b5121
Created: 2026-10-26 09:30:00.000000+00:00

Migration M3b of the MVP's lane (``lead-orchestration`` LO5a.2): ``approval_decisions.subject_type``
admits ``lead_card`` -- a person's approval of a Lead card that started paid work, naming that
work's run with decision ``start``: the wallet's authority to charge it (ADR 0028 decision 3),
as ``chat_start`` is for a typed start. A second migration on the constraint M3 widened, which
LO16 wanted to avoid; the plan chose it over a single-step Lead plan (LO3/LO4).

The set is listed literally here, as it was when this ran; the model builds it from
``domain/approval_ledger.py``. The downgrade refuses while the append-only ledger holds a
``lead_card`` row.
"""

from __future__ import annotations

from alembic import op

revision: str = "124dedc8f7b1"
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
_ADDED = ("lead_card",)


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
            f"{held} lead_card decision(s) are in the approval ledger, which is append-only; "
            "downgrading would erase them"
        )
    op.drop_constraint(op.f(_LEDGER), "approval_decisions", type_="check")
    op.create_check_constraint(op.f(_LEDGER), "approval_decisions", _check(_BEFORE))
