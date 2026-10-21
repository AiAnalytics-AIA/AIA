"""Who a charge is booked to, and a person's spend read back (``develop-spend-attribution`` 7).

**The rule (Q40, the product owner, 2026-10-21):** a charge is booked to whoever approved or
started the paid work. :func:`charged_to` is that rule, over facts the infrastructure reads from
the approval ledger and the run (``WorkflowRepository``), in this order:

1. the person who **lifted the budget** of the run, the latest lift before the hold (a lift
   approves the run's further paid work; ``ApprovalSubject.BUDGET``);
2. the person whose **approval let the run start**: a spend confirmation, an answerability
   acknowledgement, a chat start or a plan step naming the run, or the Lead card whose approval
   started it (:data:`START_APPROVALS`, :data:`CARD_APPROVAL`). Two different people there is no
   single approver, and the hold is booked to nobody rather than to one of them by guess;
3. else the person who **started** it (the run's recorded starter, when it is a member).

Never a model and never the worker: a hold with none of these is ``None``, listed as
unattributed ("nepřiřazeno"), never booked to someone (CLAUDE.md § 8).

:func:`researcher_spend` folds the content-free usage and hold rows into each person's spend:
model spend from the usage ledger (authoritative for model cost, ADR 0006), spend held outside
the ledger (tool calls: Brave, Athena, until ``deep-research`` 4 gives them a ledger) from the
settled holds no ledger row names, the open holds apart, and every uncertain call counted, never
as zero.

No I/O: stdlib only.
"""

from __future__ import annotations

from collections.abc import Collection, Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Final

from .approval_ledger import ApprovalSubject

__all__ = [
    "CARD_APPROVAL",
    "LIFT_DECISION",
    "START_APPROVALS",
    "ActivitySpend",
    "HoldFact",
    "PersonSpend",
    "SpendActivity",
    "SpendPeriod",
    "StudySpend",
    "UsageFact",
    "activity_of",
    "charged_to",
    "period_bounds",
    "researcher_spend",
]

#: Ledger subjects whose row names the run it let start in ``run_id`` (subject: the run, or
#: for a plan step its step, LO1's charge authority).
START_APPROVALS: Final[frozenset[ApprovalSubject]] = frozenset(
    {
        ApprovalSubject.SPEND,
        ApprovalSubject.ANSWERABILITY,
        ApprovalSubject.CHAT_START,
        ApprovalSubject.PLAN_STEP,
    }
)

#: The Lead card a person approved: its row names the Lead's run, and the agent job it started
#: as ``comment.agent_run_id`` (``WorkflowRepository.record_lead_job_approval``).
CARD_APPROVAL: Final = ApprovalSubject.LEAD_JOB_REQUEST

#: A budget lift's decision (``WorkflowRepository._resume_budget_waits``).
LIFT_DECISION: Final = "lift"


def charged_to(
    *, lift_approver: str | None, start_approvers: Collection[str], starter: str | None
) -> str | None:
    """The person a hold is booked to, by the rule above; ``None`` when there is none."""
    if lift_approver:
        return lift_approver
    approvers = {a for a in start_approvers if a}
    if len(approvers) == 1:
        return next(iter(approvers))
    if approvers:
        return None
    return starter or None


# --------------------------------------------------------------------------- activities


class SpendActivity(StrEnum):
    """What paid work a charge was for, as Settings shows it."""

    LEAD = "lead"
    FIELDWORK = "fieldwork"
    ANALYSIS_REPORT = "analysis_report"
    DEEP_RESEARCH = "deep_research"
    #: Agent jobs (design proposals), AI proposals from a client's document, validation runs:
    #: paid work that is none of the four.
    OTHER = "other"


# Written out, not imported: the domain's workflow constants live beside heavier modules, and a
# test holds these to them (test_spend_attribution.py).
_LEAD_WORKFLOWS: Final = frozenset({"research_lead"})
_DEEP_RESEARCH_WORKFLOWS: Final = frozenset({"deep_research"})
_RESEARCH_WORKFLOWS: Final = frozenset({"research"})
_ANALYSIS_REPORT_STAGES: Final = frozenset({"ANALYSIS", "REPORT"})


def activity_of(workflow_type: str | None, stage_type: str | None) -> SpendActivity:
    """The activity of a charge made by a step of ``stage_type`` in a ``workflow_type`` run.

    A research run's analysis and report steps are analysis and report; its other steps
    (fieldwork and what prepares it) are fieldwork.
    """
    if workflow_type in _LEAD_WORKFLOWS:
        return SpendActivity.LEAD
    if workflow_type in _DEEP_RESEARCH_WORKFLOWS:
        return SpendActivity.DEEP_RESEARCH
    if workflow_type in _RESEARCH_WORKFLOWS:
        if stage_type in _ANALYSIS_REPORT_STAGES:
            return SpendActivity.ANALYSIS_REPORT
        return SpendActivity.FIELDWORK
    return SpendActivity.OTHER


# --------------------------------------------------------------------------- periods


class SpendPeriod(StrEnum):
    """The periods Settings offers, in UTC."""

    THIS_MONTH = "this_month"
    LAST_MONTH = "last_month"
    YEAR_TO_DATE = "year_to_date"


def period_bounds(period: SpendPeriod, now: datetime) -> tuple[datetime, datetime]:
    """``[start, end)`` of ``period`` in UTC, as of ``now``; ``end`` is ``now`` for a period
    still running."""
    now = now.astimezone(UTC) if now.tzinfo else now.replace(tzinfo=UTC)
    month = datetime(now.year, now.month, 1, tzinfo=UTC)
    if period is SpendPeriod.THIS_MONTH:
        return month, now
    if period is SpendPeriod.LAST_MONTH:
        if now.month == 1:
            return datetime(now.year - 1, 12, 1, tzinfo=UTC), month
        return datetime(now.year, now.month - 1, 1, tzinfo=UTC), month
    return datetime(now.year, 1, 1, tzinfo=UTC), now


# --------------------------------------------------------------------------- facts


@dataclass(frozen=True, slots=True)
class UsageFact:
    """One usage-ledger row, content-free: what :func:`researcher_spend` needs of it."""

    call_id: str
    outcome: str
    cost_usd: float
    charged_to: str | None
    client_id: str
    study_id: str | None
    activity: SpendActivity
    occurred_at: datetime


@dataclass(frozen=True, slots=True)
class HoldFact:
    """One budget hold, content-free. ``in_ledger``: a usage-ledger row names it (a model
    call's hold, whose cost the ledger carries)."""

    reservation_id: str
    status: str
    amount_usd: float
    settled_amount_usd: float
    charged_to: str | None
    client_id: str
    study_id: str | None
    activity: SpendActivity
    in_ledger: bool
    settled_at: datetime | None


_RESOLUTIONS: Final = frozenset({"RESOLVED_BILLED", "RESOLVED_NOT_BILLED"})
_TERMINALS: Final = frozenset({"SUCCEEDED", "FAILED", "UNCERTAIN"})


# --------------------------------------------------------------------------- results


@dataclass(slots=True)
class ActivitySpend:
    """Spend of one activity: settled in the period, and held open now."""

    model_usd: float = 0.0
    outside_ledger_usd: float = 0.0
    reserved_usd: float = 0.0
    uncertain_calls: int = 0

    @property
    def total_usd(self) -> float:
        return self.model_usd + self.outside_ledger_usd


@dataclass(slots=True)
class StudySpend(ActivitySpend):
    """One study's part of a person's spend; ``study_id`` ``None`` is the client's own work."""

    client_id: str = ""
    study_id: str | None = None
    by_activity: dict[SpendActivity, ActivitySpend] = field(default_factory=dict)


@dataclass(slots=True)
class PersonSpend(ActivitySpend):
    """One person's spend; ``user_id`` ``None`` is what no person is booked for."""

    user_id: str | None = None
    by_activity: dict[SpendActivity, ActivitySpend] = field(default_factory=dict)
    studies: dict[tuple[str, str | None], StudySpend] = field(default_factory=dict)

    @property
    def study_count(self) -> int:
        """The studies this person's spend or open holds touched (the client's own work not
        counted: it is no study)."""
        return sum(1 for (_, study) in self.studies if study is not None)


def _add(
    targets: Iterable[ActivitySpend],
    *,
    model: float = 0.0,
    outside: float = 0.0,
    reserved: float = 0.0,
    uncertain: int = 0,
) -> None:
    for t in targets:
        t.model_usd += model
        t.outside_ledger_usd += outside
        t.reserved_usd += reserved
        t.uncertain_calls += uncertain


def _in(at: datetime | None, start: datetime, end: datetime) -> bool:
    if at is None:
        return False
    at = at if at.tzinfo else at.replace(tzinfo=UTC)
    return start <= at < end


def researcher_spend(
    usage: Iterable[UsageFact],
    holds: Iterable[HoldFact],
    *,
    start: datetime,
    end: datetime,
    people: Iterable[str] = (),
) -> dict[str | None, PersonSpend]:
    """Each person's spend over ``[start, end)``, keyed by user id (``None``: unattributed).

    * ``model_usd``: the usage ledger's rows that occurred in the period, compensations
      included (a resolution counts when it is written, as the ledger is read everywhere).
    * ``outside_ledger_usd``: holds settled in the period that no ledger row names.
    * ``reserved_usd``: holds open **now**, whatever the period: they are not spent yet.
    * ``uncertain_calls``: a model call dispatched in the period with no resolution and no
      known outcome (``usage`` must hold every row of such a call, the later ones too), and a
      hold outside the ledger settled uncertain in the period. Counted, never as zero: a total
      with one is not known to the cent.

    ``people`` are listed even with nothing booked to them: a member with no rows has spent
    nothing (a sum over no rows is zero, OI-4), which is known, not unknown.
    """
    out: dict[str | None, PersonSpend] = {p: PersonSpend(user_id=p) for p in people}

    def person(user: str | None) -> PersonSpend:
        if user not in out:
            out[user] = PersonSpend(user_id=user)
        return out[user]

    def targets(
        user: str | None, client_id: str, study_id: str | None, activity: SpendActivity
    ) -> list[ActivitySpend]:
        p = person(user)
        study = p.studies.get((client_id, study_id))
        if study is None:
            study = p.studies[(client_id, study_id)] = StudySpend(
                client_id=client_id, study_id=study_id
            )
        return [
            p,
            p.by_activity.setdefault(activity, ActivitySpend()),
            study,
            study.by_activity.setdefault(activity, ActivitySpend()),
        ]

    calls: dict[str, list[UsageFact]] = {}
    for fact in usage:
        calls.setdefault(fact.call_id, []).append(fact)
        if _in(fact.occurred_at, start, end):
            _add(
                targets(fact.charged_to, fact.client_id, fact.study_id, fact.activity),
                model=fact.cost_usd,
            )
    for facts in calls.values():
        dispatched = next((f for f in facts if f.outcome == "DISPATCHED"), None)
        if dispatched is None or not _in(dispatched.occurred_at, start, end):
            continue
        outcomes = {f.outcome for f in facts}
        if outcomes & _RESOLUTIONS:
            continue
        terminal = outcomes & _TERMINALS
        if not terminal or terminal == {"UNCERTAIN"}:
            _add(
                targets(
                    dispatched.charged_to,
                    dispatched.client_id,
                    dispatched.study_id,
                    dispatched.activity,
                ),
                uncertain=1,
            )

    for hold in holds:
        if hold.status == "RESERVED":
            _add(
                targets(hold.charged_to, hold.client_id, hold.study_id, hold.activity),
                reserved=hold.amount_usd,
            )
        elif (
            not hold.in_ledger
            and hold.status in ("SETTLED", "SETTLED_UNCERTAIN")
            and _in(hold.settled_at, start, end)
        ):
            _add(
                targets(hold.charged_to, hold.client_id, hold.study_id, hold.activity),
                outside=hold.settled_amount_usd,
                uncertain=1 if hold.status == "SETTLED_UNCERTAIN" else 0,
            )
    return out
