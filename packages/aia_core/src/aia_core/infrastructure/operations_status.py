"""The deployment's state as an operator reads it (plan ops-status-report): the ONLY reader for
``aia_executors.status_report``.

Read across every organization, acting as no one, as ``deploy_smoke_repository.tenant_count``
and the work queue's reconciler do: the deployment's health is no organization's. What it returns
is codes, counts and AIA's opaque ids only -- never text a person or a model wrote, a name, a URL
or a secret. A reason is kept only when it is a code (:data:`CODE`); anything else is
``uncoded``, so a free-text error can never reach a log through here.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import ColumnElement, func, select
from sqlalchemy.orm import Session

from ..domain.ai_contracts import UsageOutcome
from ..domain.workflow import ReservationStatus, StepRunStatus, WorkflowRunStatus
from .deep_research_settings_repository import approved_versions_by_organization
from .tables import (
    AIUsageEventRow,
    BudgetReservationRow,
    StepAttemptRow,
    StepRunRow,
    WorkflowRunRow,
    as_utc,
)

__all__ = ["CODE", "OperationsStatus", "ProblemStep", "code_or_uncoded", "read_status"]

#: A reason, kind or status is printed only in this shape.
CODE = re.compile(r"^[A-Za-z0-9_.:-]{1,64}$")

#: How many steps each problem list holds (parked or awaiting recovery; failed), newest first.
PROBLEM_LIMIT = 50

_LIVE_PROBLEMS = frozenset(
    {
        StepRunStatus.AWAITING_BUDGET,
        StepRunStatus.AWAITING_GATE,
        StepRunStatus.WAITING_PROVIDER,
        StepRunStatus.WAITING_CAPACITY,
        StepRunStatus.RECOVERY_REQUIRED,
    }
)


def code_or_uncoded(value: object) -> str | None:
    """``value`` when it is a code, ``"uncoded"`` when it is anything else, None when absent."""
    if value is None or value == "":
        return None
    return value if isinstance(value, str) and CODE.match(value) else "uncoded"


@dataclass(frozen=True, slots=True)
class ProblemStep:
    run_id: str
    workflow_type: str | None
    kind: str | None
    status: str | None
    waiting_reason: str | None
    error_reason: str | None
    failure_class: str | None
    updated_at: str

    def as_json(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "workflow_type": self.workflow_type,
            "kind": self.kind,
            "status": self.status,
            "waiting_reason": self.waiting_reason,
            "error_reason": self.error_reason,
            "failure_class": self.failure_class,
            "updated_at": self.updated_at,
        }


@dataclass(frozen=True, slots=True)
class OperationsStatus:
    runs: dict[str, dict[str, int]]
    steps: dict[str, int]
    live_problem_steps: list[ProblemStep]
    failed_steps: list[ProblemStep]
    model_calls: list[dict[str, Any]]
    open_calls: int
    open_holds: dict[str, Any]
    deep_research_approvals: dict[str, dict[str, int | None]]

    def as_json(self) -> dict[str, Any]:
        return {
            "runs": self.runs,
            "steps": self.steps,
            "live_problem_steps": [p.as_json() for p in self.live_problem_steps],
            "failed_steps": [p.as_json() for p in self.failed_steps],
            "model_calls": self.model_calls,
            "open_calls": self.open_calls,
            "open_holds": self.open_holds,
            "deep_research_approvals": self.deep_research_approvals,
        }


def read_status(session: Session, *, since: datetime) -> OperationsStatus:
    """The deployment's runs and steps touched since ``since`` or still live, whatever their
    age; parked and recovery steps listed apart from the window's failures, so neither crowds
    the other out; model calls since ``since``; open calls and holds whatever their age."""
    live_runs = [s.value for s in WorkflowRunStatus if not s.is_terminal]
    runs: dict[str, dict[str, int]] = {}
    for workflow_type, status, count in session.execute(
        select(WorkflowRunRow.workflow_type, WorkflowRunRow.status, func.count())
        .where((WorkflowRunRow.updated_at >= since) | WorkflowRunRow.status.in_(live_runs))
        .group_by(WorkflowRunRow.workflow_type, WorkflowRunRow.status)
    ):
        key = code_or_uncoded(workflow_type) or "none"
        runs.setdefault(key, {})[code_or_uncoded(status) or "none"] = int(count)

    live_steps = [s.value for s in StepRunStatus if not s.is_terminal]
    steps = {
        code_or_uncoded(status) or "none": int(count)
        for status, count in session.execute(
            select(StepRunRow.status, func.count())
            .where((StepRunRow.updated_at >= since) | StepRunRow.status.in_(live_steps))
            .group_by(StepRunRow.status)
        )
    }

    return OperationsStatus(
        runs=runs,
        steps=steps,
        live_problem_steps=_problem_steps(
            session, StepRunRow.status.in_([s.value for s in _LIVE_PROBLEMS])
        ),
        failed_steps=_problem_steps(
            session,
            (StepRunRow.status == StepRunStatus.FAILED.value) & (StepRunRow.updated_at >= since),
        ),
        model_calls=_model_calls(session, since=since),
        open_calls=_open_calls(session),
        open_holds=_open_holds(session),
        deep_research_approvals=_approvals(session),
    )


def _problem_steps(session: Session, condition: ColumnElement[bool]) -> list[ProblemStep]:
    rows = session.execute(
        select(StepRunRow, WorkflowRunRow.workflow_type)
        .join(WorkflowRunRow, WorkflowRunRow.run_id == StepRunRow.run_id)
        .where(condition)
        .order_by(StepRunRow.updated_at.desc(), StepRunRow.step_id)
        .limit(PROBLEM_LIMIT)
    ).all()
    last_attempts = _last_attempts(session, [step.step_id for step, _ in rows])
    problems = []
    for step, workflow_type in rows:
        attempt = last_attempts.get(step.step_id)
        error = (attempt.error_json or {}) if attempt is not None else {}
        problems.append(
            ProblemStep(
                run_id=step.run_id,
                workflow_type=code_or_uncoded(workflow_type),
                kind=code_or_uncoded(step.kind),
                status=code_or_uncoded(step.status),
                waiting_reason=code_or_uncoded(step.waiting_reason),
                error_reason=code_or_uncoded(error.get("reason")),
                failure_class=code_or_uncoded(attempt.failure_class if attempt else None),
                updated_at=as_utc(step.updated_at).isoformat(timespec="seconds"),
            )
        )
    return problems


def _last_attempts(session: Session, step_ids: list[str]) -> dict[str, StepAttemptRow]:
    if not step_ids:
        return {}
    newest = (
        select(StepAttemptRow.step_id, func.max(StepAttemptRow.attempt_number).label("n"))
        .where(StepAttemptRow.step_id.in_(step_ids))
        .group_by(StepAttemptRow.step_id)
        .subquery()
    )
    attempts = session.scalars(
        select(StepAttemptRow).join(
            newest,
            (StepAttemptRow.step_id == newest.c.step_id)
            & (StepAttemptRow.attempt_number == newest.c.n),
        )
    )
    return {a.step_id: a for a in attempts}


def _model_calls(session: Session, *, since: datetime) -> list[dict[str, Any]]:
    calls = []
    for model, outcome, count, tokens_in, tokens_out, cost in session.execute(
        select(
            AIUsageEventRow.model,
            AIUsageEventRow.outcome,
            func.count(),
            func.sum(AIUsageEventRow.input_tokens),
            func.sum(AIUsageEventRow.output_tokens),
            func.sum(AIUsageEventRow.cost_usd),
        )
        .where(AIUsageEventRow.occurred_at >= since)
        .group_by(AIUsageEventRow.model, AIUsageEventRow.outcome)
        .order_by(AIUsageEventRow.model, AIUsageEventRow.outcome)
    ):
        calls.append(
            {
                "model": code_or_uncoded(model),
                "outcome": code_or_uncoded(outcome),
                "rows": int(count),
                # A provider that did not report tokens leaves them null: unknown, never zero.
                "input_tokens": None if tokens_in is None else int(tokens_in),
                "output_tokens": None if tokens_out is None else int(tokens_out),
                "cost_usd": round(float(cost or 0.0), 6),
            }
        )
    return calls


def _open_calls(session: Session) -> int:
    """Calls dispatched with no known outcome and no resolution, whatever their age: no entry
    but DISPATCHED, or only UNCERTAIN beside it (as ``AIUsageRepository.uncertain_calls``)."""
    closed = (
        select(AIUsageEventRow.call_id)
        .where(
            AIUsageEventRow.outcome.in_(
                [
                    UsageOutcome.SUCCEEDED.value,
                    UsageOutcome.FAILED.value,
                    UsageOutcome.RESOLVED_BILLED.value,
                    UsageOutcome.RESOLVED_NOT_BILLED.value,
                ]
            )
        )
        .scalar_subquery()
    )
    return int(
        session.scalar(
            select(func.count(func.distinct(AIUsageEventRow.call_id))).where(
                AIUsageEventRow.outcome == UsageOutcome.DISPATCHED.value,
                AIUsageEventRow.call_id.not_in(closed),
            )
        )
        or 0
    )


def _open_holds(session: Session) -> dict[str, Any]:
    count, amount = session.execute(
        select(func.count(), func.sum(BudgetReservationRow.amount_usd)).where(
            BudgetReservationRow.status == ReservationStatus.RESERVED.value
        )
    ).one()
    uncertain = session.scalar(
        select(func.count()).where(
            BudgetReservationRow.status == ReservationStatus.SETTLED_UNCERTAIN.value
        )
    )
    return {
        "reserved": int(count),
        "reserved_usd": round(float(amount or 0.0), 6),
        "settled_uncertain": int(uncertain or 0),
    }


def _approvals(session: Session) -> dict[str, dict[str, int | None]]:
    """Per organization, each Deep Research setting's version in force (None: the code's
    default), through the settings tables' own repository."""
    return {
        code_or_uncoded(org) or "none": {code_or_uncoded(k) or "none": v for k, v in keys.items()}
        for org, keys in approved_versions_by_organization(session).items()
    }
