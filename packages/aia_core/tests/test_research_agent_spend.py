"""An agent job meets the study's confirmation threshold like a run (lead-orchestration LO15).

``ResearchAgentJobs.start`` and ``rebuild`` read ``spend_confirm_usd`` and apply the one rule in
``domain/money.py``: a job whose ceiling (the design job's reservation) reaches the threshold
needs a person's confirmation covering it, written to the approval ledger with the job. The
worker's scope can create a job (it holds ``EDIT_STUDY`` and ``RUN_WORKFLOW``) and can never
confirm one (``WORKER_PERMISSIONS`` withholds ``APPROVE_BUDGET``). F-LO0-1: every start path
calls the domain rule; none keeps an inline copy.
"""

from __future__ import annotations

import dataclasses
import json
import re
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import select

from aia_core.application import deep_research, research, research_lead, validation
from aia_core.application.research import (
    CostCeilingUnknown,
    CostConfirmationRequired,
    ResearchAgentJobs,
)
from aia_core.domain.research_agents import ResearchAction
from aia_core.domain.run_cost import CeilingUnknown
from aia_core.domain.scope import WORKER_PERMISSIONS, ScopeDenied
from aia_core.domain.workflow_templates import RESEARCH_AGENT
from aia_core.infrastructure.study_design_repository import StudyDesignRepository
from aia_core.infrastructure.tables import ApprovalDecisionRow, WorkflowRunRow

DESIGN = {"title": "Fictional", "goal": "Test concept", "sections": []}
#: The design job's reservation: a primary and one repair.
RESERVATION = 2.0


def _world(scoped: Any, session: Any, *, limit: float | None) -> tuple[Any, str]:
    scope = scoped.scope(user="lead")
    revision, _ = StudyDesignRepository(session, scope).submit_as_working_copy(
        content=DESIGN, source_stage="brief"
    )
    scoped.scope_repo.set_study_spend_confirm(scope, limit)
    return scope, revision.revision_id


def _jobs(session: Any, scope: Any, reservation: float | None = RESERVATION) -> ResearchAgentJobs:
    return ResearchAgentJobs(session, scope, reservation_usd=reservation)


def _spend_rows(session: Any) -> list[ApprovalDecisionRow]:
    return list(
        session.scalars(
            select(ApprovalDecisionRow).where(ApprovalDecisionRow.subject_type == "spend")
        )
    )


def _job_count(session: Any) -> int:
    return len(
        list(
            session.scalars(
                select(WorkflowRunRow.run_id).where(WorkflowRunRow.workflow_type == RESEARCH_AGENT)
            )
        )
    )


def test_without_a_threshold_nothing_asks_and_nothing_is_recorded(
    scoped: Any, session: Any
) -> None:
    scope, revision = _world(scoped, session, limit=None)
    # Not even an unknown ceiling asks: with no threshold, nothing does (ADR 0028).
    started = _jobs(session, scope, reservation=None).start(
        design_revision_id=revision, action=ResearchAction.ANALYZE
    )
    assert started.created and _spend_rows(session) == []


def test_a_job_below_the_threshold_starts_without_asking(scoped: Any, session: Any) -> None:
    scope, revision = _world(scoped, session, limit=RESERVATION + 0.01)
    started = _jobs(session, scope).start(
        design_revision_id=revision, action=ResearchAction.ANALYZE
    )
    assert started.created and _spend_rows(session) == []


def test_a_job_reaching_the_threshold_asks_and_creates_nothing(scoped: Any, session: Any) -> None:
    scope, revision = _world(scoped, session, limit=RESERVATION)  # at the threshold asks
    jobs = _jobs(session, scope)
    with pytest.raises(CostConfirmationRequired) as asked:
        jobs.start(design_revision_id=revision, action=ResearchAction.ANALYZE)
    assert (asked.value.ceiling_usd, asked.value.limit_usd) == (RESERVATION, RESERVATION)
    with pytest.raises(CostConfirmationRequired):
        jobs.start(
            design_revision_id=revision,
            action=ResearchAction.ANALYZE,
            confirm_cost_usd=RESERVATION - 0.01,
        )
    assert _job_count(session) == 0 and _spend_rows(session) == []


def test_an_unknown_ceiling_is_refused_under_a_threshold(scoped: Any, session: Any) -> None:
    scope, revision = _world(scoped, session, limit=1.0)
    with pytest.raises(CostCeilingUnknown) as refused:
        _jobs(session, scope, reservation=None).start(
            design_revision_id=revision, action=ResearchAction.ANALYZE, confirm_cost_usd=100.0
        )
    assert refused.value.reason is CeilingUnknown.RESEARCH_RESERVATION_MISSING
    assert _job_count(session) == 0


def test_a_covering_confirmation_starts_the_job_and_is_recorded_once(
    scoped: Any, session: Any
) -> None:
    scope, revision = _world(scoped, session, limit=1.0)
    jobs = _jobs(session, scope)
    started = jobs.start(
        design_revision_id=revision, action=ResearchAction.ANALYZE, confirm_cost_usd=RESERVATION
    )
    assert started.created
    (row,) = _spend_rows(session)
    assert (row.run_id, row.decision, row.gate_type) == (started.run_id, "confirm", "spend")
    assert row.approver_user_id == scope.actor_id
    assert json.loads(row.comment) == {
        "ceiling_usd": RESERVATION,
        "limit_usd": 1.0,
        "confirmed_usd": RESERVATION,
    }
    # Asked again, the same job is followed: it spends nothing more and asks nothing.
    again = jobs.start(design_revision_id=revision, action=ResearchAction.ANALYZE)
    assert again.run_id == started.run_id and not again.created
    assert len(_spend_rows(session)) == 1


def test_a_rebuild_meets_the_threshold_as_a_start_does(scoped: Any, session: Any) -> None:
    scope, revision = _world(scoped, session, limit=None)
    jobs = _jobs(session, scope)
    first = jobs.start(design_revision_id=revision, action=ResearchAction.ANALYZE)
    scoped.scope_repo.set_study_spend_confirm(scope, 1.0)
    with pytest.raises(CostConfirmationRequired):
        jobs.rebuild(first.run_id, design_revision_id=revision)
    assert _job_count(session) == 1 and _spend_rows(session) == []
    rebuilt = jobs.rebuild(first.run_id, design_revision_id=revision, confirm_cost_usd=RESERVATION)
    assert rebuilt.created and rebuilt.run_id != first.run_id
    (row,) = _spend_rows(session)
    assert row.run_id == rebuilt.run_id


def test_the_workers_scope_can_neither_evade_the_threshold_nor_confirm_it(
    scoped: Any, session: Any
) -> None:
    """The worker's scope holds EDIT_STUDY and RUN_WORKFLOW, so it could create a job; under a
    threshold it is asked like anyone, and a confirmation it supplies is refused: a step never
    confirms the spend it starts (ADR 0019 decision 6, ADR 0028 decision 3)."""
    person, revision = _world(scoped, session, limit=1.0)
    worker = dataclasses.replace(person, permissions=WORKER_PERMISSIONS)
    jobs = _jobs(session, worker)
    with pytest.raises(CostConfirmationRequired):
        jobs.start(design_revision_id=revision, action=ResearchAction.ANALYZE)
    with pytest.raises(ScopeDenied):
        jobs.start(
            design_revision_id=revision,
            action=ResearchAction.ANALYZE,
            confirm_cost_usd=RESERVATION,
        )
    assert _job_count(session) == 0 and _spend_rows(session) == []


_INLINE = re.compile(r"confirm_cost_usd\s*<|>=\s*limit\b")


@pytest.mark.parametrize("module", [research, deep_research, validation, research_lead])
def test_every_start_path_applies_the_one_domain_rule(module: Any) -> None:
    """F-LO0-1: each start path calls ``money.threshold_verdict`` (or the agent job's gate,
    which does), and none keeps an inline copy of the comparison."""
    source = Path(module.__file__).read_text(encoding="utf-8")
    assert not _INLINE.search(source), module.__name__
    assert "threshold_verdict(" in source or "spend_gate(" in source, module.__name__
