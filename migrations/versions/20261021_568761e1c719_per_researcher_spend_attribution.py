"""per-researcher spend attribution

Revision ID: 568761e1c719
Revises: c663617cf79b
Created: 2026-10-21 14:30:00.000000+00:00

``develop-spend-attribution`` chunk 7 (Q40, the product owner, 2026-10-21): a charge is booked
to whoever approved or started the paid work. ``charged_to_user_id`` (nullable) on
``budget_reservations`` -- every hold, a model call's and a priced tool call's alike, which are
the tool-spend rows until ``deep-research`` 4 gives tools a ledger -- and on
``ai_usage_events``; with ``ix_reservations_charged_to``, ``ix_usage_charged_to`` and
``ix_usage_reservation`` for the per-person read.

Chained after ``c663617cf79b`` (the Lead turn's typed command), which it does not depend on: that
revision adds ``study_lead_turns.command`` only, and the backfill below reads the approval ledger,
whose ``chat_start`` rows name their run in ``run_id`` either way.

**The backfill takes the person only from the approval ledger, exactly.** A past hold is booked
to the person who lifted its run's budget (the latest ``budget`` row with decision ``lift`` and
the hold's ``run_id``, written no later than the hold; the lifter pays for what runs after the
lift, Q67, the product owner, 2026-10-21 20:12 UTC, choice (a)), else to the one person whose approval
started the run (``spend``, ``answerability``, ``chat_start``, ``plan_step`` rows naming the run
in ``run_id``, and the ``lead_job_request`` row whose comment names it as ``agent_run_id``),
the same rule ``domain/spend_attribution.py`` ``charged_to`` applies to a new hold, without its
last step: the run's ``triggered_by`` is not the ledger, so a past hold whose run no approval
names stays NULL, as does one whose approvals name two people. A past usage row takes its hold's
person. Nothing else is inferred. The subjects are written out as they were when this ran.

``ai_usage_events`` is append-only; the backfill writes only the column this migration adds,
from the ledger, and no other value of any row. The downgrade drops the columns and indexes:
what a new hold recorded beyond the ledger (its run's starter) is not recoverable after it.
"""

from __future__ import annotations

import json
from collections import defaultdict
from typing import Any

import sqlalchemy as sa
from alembic import op

revision: str = "568761e1c719"
down_revision: str | None = "c663617cf79b"
branch_labels = None
depends_on = None

_START_APPROVALS = ("spend", "answerability", "chat_start", "plan_step")
_CARD = "lead_job_request"
_BUDGET = "budget"
_LIFT = "lift"


def upgrade() -> None:
    op.add_column("budget_reservations", sa.Column("charged_to_user_id", sa.String(64)))
    op.create_index(
        "ix_reservations_charged_to",
        "budget_reservations",
        ["charged_to_user_id", "status"],
    )
    op.add_column("ai_usage_events", sa.Column("charged_to_user_id", sa.String(64)))
    op.create_index(
        "ix_usage_charged_to",
        "ai_usage_events",
        ["organization_id", "charged_to_user_id", "occurred_at"],
    )
    op.create_index("ix_usage_reservation", "ai_usage_events", ["reservation_id"])
    backfill(op.get_bind())


def backfill(connection: Any) -> int:
    """Book each past hold, and its usage rows, to the person the ledger names exactly.
    Returns the number of holds booked."""
    decisions = sa.table(
        "approval_decisions",
        sa.column("decision_id", sa.Integer),
        sa.column("subject_type", sa.String),
        sa.column("run_id", sa.String),
        sa.column("decision", sa.String),
        sa.column("approver_user_id", sa.String),
        sa.column("comment", sa.Text),
        sa.column("created_at", sa.DateTime(timezone=True)),
    )
    holds = sa.table(
        "budget_reservations",
        sa.column("reservation_id", sa.String),
        sa.column("run_id", sa.String),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("charged_to_user_id", sa.String),
    )
    usage = sa.table(
        "ai_usage_events",
        sa.column("reservation_id", sa.String),
        sa.column("charged_to_user_id", sa.String),
    )

    approvers: dict[str, set[str]] = defaultdict(set)
    lifts: dict[str, list[tuple[Any, int, str]]] = defaultdict(list)
    rows = connection.execute(
        sa.select(
            decisions.c.decision_id,
            decisions.c.subject_type,
            decisions.c.run_id,
            decisions.c.decision,
            decisions.c.approver_user_id,
            decisions.c.comment,
            decisions.c.created_at,
        ).where(decisions.c.subject_type.in_((*_START_APPROVALS, _CARD, _BUDGET)))
    ).all()
    for decision_id, subject, run_id, decision, approver, comment, created_at in rows:
        if subject == _BUDGET:
            if decision == _LIFT and run_id:
                lifts[run_id].append((created_at, int(decision_id), approver))
        elif subject == _CARD:
            try:
                named = json.loads(comment or "{}").get("agent_run_id")
            except (ValueError, AttributeError):
                continue
            if isinstance(named, str) and named:
                approvers[named].add(approver)
        elif run_id:
            approvers[run_id].add(approver)

    booked = 0
    for reservation_id, run_id, created_at in connection.execute(
        sa.select(holds.c.reservation_id, holds.c.run_id, holds.c.created_at).where(
            holds.c.run_id.is_not(None)
        )
    ).all():
        before = [lift for lift in lifts.get(run_id, ()) if lift[0] <= created_at]
        person: str | None
        if before:
            person = max(before, key=lambda lift: lift[1])[2]
        else:
            named = approvers.get(run_id, set())
            person = next(iter(named)) if len(named) == 1 else None
        if person:
            connection.execute(
                holds.update()
                .where(holds.c.reservation_id == reservation_id)
                .values(charged_to_user_id=person)
            )
            connection.execute(
                usage.update()
                .where(usage.c.reservation_id == reservation_id)
                .values(charged_to_user_id=person)
            )
            booked += 1
    return booked


def downgrade() -> None:
    op.drop_index("ix_usage_reservation", table_name="ai_usage_events")
    op.drop_index("ix_usage_charged_to", table_name="ai_usage_events")
    with op.batch_alter_table("ai_usage_events") as batch:
        batch.drop_column("charged_to_user_id")
    op.drop_index("ix_reservations_charged_to", table_name="budget_reservations")
    with op.batch_alter_table("budget_reservations") as batch:
        batch.drop_column("charged_to_user_id")
