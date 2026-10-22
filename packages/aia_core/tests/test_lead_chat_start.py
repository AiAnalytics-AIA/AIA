"""The chat start's ledger row (lead-orchestration LO5): a person's approval of their own typed
start, naming the run it created, is the authority a wallet charge of that run names, and the
worker's scope can write none."""

from __future__ import annotations

import json
from dataclasses import replace
from typing import Any

import pytest
from sqlalchemy.orm import Session

from aia_core.application.lead_chat_start import chat_start_decisions
from aia_core.application.workflows import start_workflow
from aia_core.domain.approval_ledger import ApprovalSubject
from aia_core.domain.pipeline import ProjectType
from aia_core.domain.scope import WORKER_PERMISSIONS, ScopeDenied
from aia_core.domain.wallet import ChargeKind
from aia_core.domain.workflow_templates import DEVELOP_SNAPSHOT
from aia_core.infrastructure.repositories import ProjectRepository
from aia_core.infrastructure.study_wallet_repository import StudyWalletRepository
from aia_core.infrastructure.workflow_repository import WorkflowRepository


def _run(session: Session, scope: Any, key: str) -> str:
    project, _ = ProjectRepository(session, scope).create(
        title=f"Chat start {key}", project_type=ProjectType.RESEARCH, content={"title": key}
    )
    return start_workflow(
        session,
        scope,
        project_id=project.project_id,
        workflow_type=DEVELOP_SNAPSHOT,
        idempotency_key=key,
    ).run_id


def test_a_chat_start_row_names_its_run_and_authorises_its_charge(
    session: Session, scoped: Any
) -> None:
    scope = scoped.scope()
    run_id = _run(session, scope, "a")
    workflows = WorkflowRepository(session, scope)
    decision_id = workflows.record_chat_start(
        run_id,
        turn_id="LDT-1",
        start="agent_job:analyze_brief",
        ceiling_usd=2.0,
        design_revision_id="REV-1",
    )
    entry = workflows.ledger_entry(decision_id)
    assert entry is not None
    assert (entry.subject, entry.subject_id, entry.run_id, entry.decision) == (
        ApprovalSubject.CHAT_START,
        run_id,
        run_id,
        "start",
    )
    assert json.loads(entry.comment) == {
        "turn_id": "LDT-1",
        "start": "agent_job:analyze_brief",
        "ceiling_usd": 2.0,
        "design_revision_id": "REV-1",
    }
    wallet = StudyWalletRepository(session, scope)
    wallet.set_cap(5.0)
    charge = wallet.charge(
        run_id=run_id, kind=ChargeKind.AGENT_JOB, ceiling_usd=2.0, approval_decision_id=decision_id
    )
    assert charge.approval_decision_id == decision_id
    assert chat_start_decisions(workflows, ["LDT-1", "LDT-2"]) == {
        "LDT-1": {"run_id": run_id, "comment": json.loads(entry.comment), "reused": False}
    }
    assert chat_start_decisions(workflows, []) == {}


def test_a_typed_command_is_stored_only_on_a_persons_turn(session: Session, scoped: Any) -> None:
    """The table holds it: a person's turn keeps its command; a Lead turn naming one is refused
    by the CHECK (the model never names a start, D22)."""
    from sqlalchemy.exc import IntegrityError

    from aia_core.infrastructure.study_lead_repository import StudyLeadRepository

    scope = scoped.scope()
    turns = StudyLeadRepository(session, scope)
    stored = turns.append(
        actor="person", kind="message", stage="brief", text="Spusť výzkum", command="research_run"
    )
    assert turns.get(stored.turn_id) == stored and stored.command == "research_run"
    assert turns.append(actor="person", kind="message", stage="brief", text="x").command is None
    run_id = _run(session, scope, "lead")
    with pytest.raises(IntegrityError):
        turns.append(
            actor="lead", kind="message", stage="brief", run_id=run_id, command="research_run"
        )


def test_the_worker_cannot_write_a_chat_start(session: Session, scoped: Any) -> None:
    """A chat_start row authorises a wallet charge, so a step must not be able to make one:
    it needs APPROVE_GATE, which WORKER_PERMISSIONS withholds."""
    scope = scoped.scope()
    run_id = _run(session, scope, "w")
    worker = replace(scope, permissions=frozenset(WORKER_PERMISSIONS))
    with pytest.raises(ScopeDenied):
        WorkflowRepository(session, worker).record_chat_start(
            run_id, turn_id="LDT-w", start="research_run", ceiling_usd=1.0, design_revision_id="R"
        )
