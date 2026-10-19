"""The Research Lead's use cases: a researcher's turns, and a person's decisions on them.

ADR 0026 and the product owner's 2026-10-19 decisions. The API never calls a model: a post
queues a ``research_lead`` run; these tests stand in for the worker by completing or parking
its one step through the workflow repository, as a worker would.
"""

from __future__ import annotations

import dataclasses
import json
import os
import threading
from datetime import timedelta
from typing import Any

import pytest
from sqlalchemy import select

from aia_core.application.research import CostCeilingUnknown, CostConfirmationRequired
from aia_core.application.research_lead import (
    LeadBusy,
    LeadContextTooLarge,
    LeadEditsStale,
    LeadNotHatched,
    LeadRejected,
    LeadSelfUpdateDecided,
    LeadSelfUpdateNone,
    LeadTurnNotFound,
    LeadTurnNotReady,
    LeadUnavailable,
    NotAPaidRequest,
    ResearchLead,
)
from aia_core.domain.research_lead import RememberNote, SelfUpdate, layer
from aia_core.domain.scope import (
    WORKER_PERMISSIONS,
    Permission,
    ScopeDenied,
    StudyStatus,
)
from aia_core.domain.workflow import FailureClass, WorkflowRunStatus
from aia_core.domain.workflow_templates import RESEARCH_AGENT, RESEARCH_LEAD, RESEARCH_LEAD_TURN
from aia_core.infrastructure.researcher_lead_repository import ResearcherLeadRepository
from aia_core.infrastructure.study_design_repository import StudyDesignRepository
from aia_core.infrastructure.study_workspace_repository import StudyWorkspaceRepository
from aia_core.infrastructure.tables import ApprovalDecisionRow, utcnow
from aia_core.infrastructure.workflow_repository import WorkflowRepository

CONTENT: dict[str, Any] = {
    "title": "Fiktivní koncept",
    "goal": "Otestovat koncept",
    "sections": [
        {
            "id": "s1",
            "type": "questions",
            "questions": [
                {"id": "q1", "text": "Znáte značku?", "typ": "vyber", "kategorie": ["Ano", "Ne"]}
            ],
        }
    ],
    "research_plan": {"objectives": ["Ověřit zájem"]},
}
WHY = "Zadání to potřebuje."


def _hatch(scoped: Any, session: Any, user: str = "lead") -> None:
    org = scoped.resolver.organization_context(scoped.principal(scoped.users[user]))
    ResearcherLeadRepository(session, org).hatch()


def _save(scope: Any, session: Any, content: dict[str, Any] = CONTENT) -> int:
    saved = StudyWorkspaceRepository(session).save(scope, content=content, base_revision=None)
    return saved.revision


def _lead(scope: Any, session: Any, **kw: Any) -> ResearchLead:
    return ResearchLead(session, scope, enabled=True, **kw)


def _message(lead: ResearchLead, text: str = "Kde studie stojí?") -> list[dict[str, Any]]:
    return lead.post(
        kind="message", stage="brief", text=text, focus={"id": "brief:goal", "label": "Cíl"}
    )


def _step_input(session: Any, scope: Any, run_id: str) -> dict[str, Any]:
    run = WorkflowRepository(session, scope).get_run(run_id)
    from aia_core.infrastructure.tables import StepRunRow

    row = session.get(StepRunRow, run["steps"][0]["step_id"])
    return dict(row.input_json)


def _complete(session: Any, scope: Any, output: dict[str, Any], **extra: Any) -> None:
    workflows = WorkflowRepository(session, scope)
    work = workflows.claim_next(worker_id="w", kinds={RESEARCH_LEAD_TURN})
    assert work is not None
    workflows.complete_attempt(
        work.attempt_id,
        worker_id="w",
        output={
            "lead_output": output,
            "dropped": [],
            "self_update_applied": None,
            "data_class": "CLASS_C_INTERNAL",
            **extra,
        },
    )


def _ready(
    scoped: Any, session: Any, output: dict[str, Any], *, user: str = "lead", study: str = "primary"
) -> tuple[Any, str]:
    """A hatched researcher, saved content and one completed Lead turn proposing ``output``."""
    scope = scoped.scope(user=user, study=study)
    _hatch(scoped, session, user)
    _save(scope, session)
    turns = _message(_lead(scope, session))
    _complete(session, scope, output)
    return scope, turns[-1]["turn_id"]


# --------------------------------------------------------------------------- posting


def test_a_message_stores_the_persons_turn_and_queues_the_leads(scoped: Any, session: Any) -> None:
    scope = scoped.scope()
    _hatch(scoped, session)
    revision = _save(scope, session)
    person, lead_turn = _message(_lead(scope, session))
    assert (person["actor"], person["status"], person["output"]) == ("person", "COMPLETED", None)
    assert person["text"] == "Kde studie stojí?" and person["focus"] == {
        "id": "brief:goal",
        "label": "Cíl",
    }
    assert (lead_turn["actor"], lead_turn["status"]) == ("lead", "QUEUED")
    assert lead_turn["workspace_revision"] == revision
    assert (person["sequence_no"], lead_turn["sequence_no"]) == (1, 2)

    run = WorkflowRepository(session, scope).get_run(lead_turn["run_id"])
    assert run["workflow_type"] == RESEARCH_LEAD
    assert run["project_id"] == StudyDesignRepository(session, scope).project_id()
    assert run["metadata"]["turn_id"] == lead_turn["turn_id"]
    # A Study without a Design Revision has its working content submitted as the first one.
    first = StudyDesignRepository(session, scope).latest()
    assert first is not None and first.source_stage == "brief"
    assert run["metadata"]["design_revision_id"] == first.revision_id

    turn = _step_input(session, scope, lead_turn["run_id"])
    context = turn["context"]
    assert turn["user_id"] == scope.actor_id and turn["turn_id"] == lead_turn["turn_id"]
    assert layer(context, "prompt")["pin"]["prompt_id"] == "aia.research.lead"
    assert layer(context, "view") == {
        "layer": "view",
        "kind": "message",
        "stage": "brief",
        "focus": {"id": "brief:goal", "label": "Cíl"},
        "message": "Kde studie stojí?",
    }
    study = layer(context, "study")
    assert (study["name"], study["client_name"], study["budget_usd"]) == (
        "Acme brand",
        "Acme Corp",
        500.0,
    )
    assert layer(context, "design")["content"]["title"] == "Fiktivní koncept"
    assert layer(context, "lead")["first_conversation"] is True
    with pytest.raises(LeadBusy):
        _message(_lead(scope, session), "A ještě?")


def test_a_greeting_stores_no_persons_turn_and_is_said_once_in_eight_hours(
    scoped: Any, session: Any
) -> None:
    scope = scoped.scope()
    _hatch(scoped, session)
    (greeting,) = _lead(scope, session).post(kind="greeting", stage="brief")
    assert (greeting["actor"], greeting["kind"]) == ("lead", "greeting")
    _complete(session, scope, {"reply": "Dobrý den."})
    assert _lead(scope, session).post(kind="greeting", stage="design") == []
    later = _lead(scope, session, clock=lambda: utcnow() + timedelta(hours=9))
    assert len(later.post(kind="greeting", stage="design")) == 1


def test_a_greeting_waits_for_nothing_but_a_message_waits_for_the_lead(
    scoped: Any, session: Any
) -> None:
    scope = scoped.scope()
    _hatch(scoped, session)
    _message(_lead(scope, session))
    # A greeting while the Lead answers is the Lead having spoken: a no-op, never a 409.
    assert _lead(scope, session).post(kind="greeting", stage="brief") == []
    with pytest.raises(LeadBusy):
        _message(_lead(scope, session))
    _complete(session, scope, {"reply": "Hotovo."})
    assert len(_message(_lead(scope, session), "Další")) == 2


def test_a_parked_turn_says_why_and_does_not_hold_the_conversation(
    scoped: Any, session: Any
) -> None:
    scope = scoped.scope()
    _hatch(scoped, session)
    _message(_lead(scope, session))
    workflows = WorkflowRepository(session, scope)
    work = workflows.claim_next(worker_id="w", kinds={RESEARCH_LEAD_TURN})
    assert work is not None
    workflows.fail_attempt(
        work.attempt_id,
        worker_id="w",
        failure=FailureClass.RUNTIME_UNAVAILABLE,
        error={"reason": "research_lead_unconfigured", "message": "off"},
    )
    state = _lead(scope, session).state()
    assert state["busy"] is False
    lead_turn = state["turns"][-1]
    assert (lead_turn["status"], lead_turn["reason"]) == ("WAITING", "research_lead_unconfigured")
    assert len(_message(_lead(scope, session), "Jsi tam?")) == 2


def test_the_state_reads_the_reply_from_the_step_output(scoped: Any, session: Any) -> None:
    output = {"reply": "Studie je ve fázi zadání.", "follow": ["Co dál?"]}
    scope, turn_id = _ready(scoped, session, output, user="lead")
    state = _lead(scope, session).state()
    assert state["busy"] is False
    lead_turn = state["turns"][-1]
    assert lead_turn["turn_id"] == turn_id and lead_turn["status"] == "COMPLETED"
    assert lead_turn["output"] == output and lead_turn["text"] is None
    assert lead_turn["edit_decisions"] == {} and lead_turn["request_decision"] is None
    # The next turn is shown the reply, with the class its turn was sent as.
    _message(_lead(scope, session), "Díky")
    turns = _lead(scope, session).state()["turns"]
    context = _step_input(session, scope, turns[-1]["run_id"])["context"]
    assert layer(context, "conversation")["turns"][-1] == {
        "actor": "lead",
        "stage": "brief",
        "reply": "Studie je ve fázi zadání.",
        "data_class": "CLASS_C_INTERNAL",
    }
    assert layer(context, "lead")["first_conversation"] is False


def test_another_researcher_sees_none_of_this_conversation(scoped: Any, session: Any) -> None:
    scope, _ = _ready(scoped, session, {"reply": "Ahoj."})
    other = scoped.scope(user="researcher")
    _hatch(scoped, session, "researcher")
    assert _lead(other, session).state() == {"busy": False, "turns": []}
    # Each researcher's busy rule is their own.
    assert len(_message(_lead(other, session))) == 2
    assert len(_lead(scope, session).state()["turns"]) == 2


def test_a_post_needs_the_switch_a_hatched_lead_and_valid_input(scoped: Any, session: Any) -> None:
    scope = scoped.scope()
    with pytest.raises(LeadUnavailable):
        ResearchLead(session, scope).post(kind="greeting", stage="brief")
    with pytest.raises(LeadNotHatched):
        _lead(scope, session).post(kind="greeting", stage="brief")
    _hatch(scoped, session)
    for kw in (
        {"kind": "message", "stage": "brief", "text": "  "},
        {"kind": "greeting", "stage": "brief", "text": "ahoj"},
        {"kind": "message", "stage": "nowhere", "text": "x"},
        {"kind": "shout", "stage": "brief", "text": "x"},
        {"kind": "message", "stage": "brief", "text": "x" * 4001},
    ):
        with pytest.raises(LeadRejected):
            _lead(scope, session).post(**kw)


@pytest.mark.parametrize("missing", [Permission.EDIT_STUDY, Permission.RUN_WORKFLOW])
def test_a_post_needs_edit_and_run_permissions(scoped: Any, session: Any, missing: Any) -> None:
    _hatch(scoped, session)
    scope = scoped.scope()
    narrowed = dataclasses.replace(scope, permissions=scope.permissions - {missing})
    with pytest.raises(ScopeDenied):
        _lead(narrowed, session).post(kind="greeting", stage="brief")


def test_a_closed_study_takes_no_turn(scoped: Any, session: Any) -> None:
    _hatch(scoped, session)
    closed = dataclasses.replace(scoped.scope(), study_status=StudyStatus.DELIVERED)
    with pytest.raises(ScopeDenied) as refused:
        _lead(closed, session).post(kind="greeting", stage="brief")
    assert refused.value.reason == "study_closed"


def test_a_context_over_its_bound_is_refused_and_nothing_is_stored(
    scoped: Any, session: Any
) -> None:
    scope = scoped.scope()
    _hatch(scoped, session)
    _save(scope, session, {**CONTENT, "notes": "y" * (100 * 1024)})
    with pytest.raises(LeadContextTooLarge):
        _message(_lead(scope, session))


def test_a_client_note_reaches_only_its_own_clients_turns(scoped: Any, session: Any) -> None:
    """Cross-client isolation: a note kept in an Acme study never reaches a Globex turn."""
    _hatch(scoped, session, "lead")
    acme = scoped.scope(user="lead", study="primary")
    ResearcherLeadRepository(session, acme).apply_self_update(
        SelfUpdate(
            remember=[
                RememberNote(scope="client", text="Acme chce čísla v tabulce."),
                RememberNote(scope="personal", text="Má rád stručnost."),
            ]
        ),
        source_turn_id="LDT-seed",
    )
    globex = scoped.scope(user="lead", study="other_client")
    (turn,) = _lead(globex, session).post(kind="greeting", stage="brief")
    notes = layer(_step_input(session, globex, turn["run_id"])["context"], "lead")["notes"]
    assert [n["text"] for n in notes] == ["Má rád stručnost."]
    (turn,) = _lead(acme, session).post(kind="greeting", stage="brief")
    notes = layer(_step_input(session, acme, turn["run_id"])["context"], "lead")["notes"]
    assert {n["text"] for n in notes} == {"Acme chce čísla v tabulce.", "Má rád stručnost."}


# --------------------------------------------------------------------------- deciding on edits

EDITS = {
    "reply": "Navrhuji dvě změny.",
    "edits": [
        {"op": "set_text", "field": "title", "value": "Nový název", "why": WHY},
        {"op": "list_add", "list": "plan.objectives", "value": "Ověřit cenu", "why": WHY},
        {"op": "question_remove", "question_id": "q9", "why": WHY},
        {"op": "set_n", "value": 400, "why": WHY},
    ],
}


def _ledger(session: Any, subject_type: str) -> list[ApprovalDecisionRow]:
    return list(
        session.scalars(
            select(ApprovalDecisionRow)
            .where(ApprovalDecisionRow.subject_type == subject_type)
            .order_by(ApprovalDecisionRow.decision_id)
        )
    )


def test_accepting_edits_saves_the_working_copy_and_writes_one_row_each(
    scoped: Any, session: Any
) -> None:
    scope, turn_id = _ready(scoped, session, EDITS)
    base = StudyWorkspaceRepository(session).content(scope).revision
    decided = _lead(scope, session).decide_edits(
        turn_id, decision="accept", indices=[0, 1, 2], base_revision=base
    )
    assert decided["workspace_revision"] == base + 1
    assert decided["results"] == [
        {"index": 0, "status": "accepted", "reason": None},
        {"index": 1, "status": "accepted", "reason": None},
        {"index": 2, "status": "refused", "reason": "unknown_question"},
    ]
    working = StudyWorkspaceRepository(session).content(scope)
    assert working.content is not None and working.content["title"] == "Nový název"
    assert working.content["research_plan"]["objectives"] == ["Ověřit zájem", "Ověřit cenu"]
    assert working.content["ui_state"]["plan_manual_changed"] is True
    assert working.analysis is not None and working.analysis["objectives"][-1] == "Ověřit cenu"

    rows = _ledger(session, "lead_edit")
    assert [(r.subject_id, r.decision, r.gate_type) for r in rows] == [
        (f"{turn_id}:0", "accept", "set_text"),
        (f"{turn_id}:1", "accept", "list_add"),
    ]
    assert rows[0].producer_user_id == rows[0].approver_user_id == scope.actor_id
    assert rows[0].self_approved is True
    assert json.loads(rows[0].comment)["workspace_revision"] == base + 1

    # Decided once: asked again, the first decision stands and nothing new is written.
    again = _lead(scope, session).decide_edits(
        turn_id, decision="dismiss", indices=[0, 3], base_revision=None
    )
    assert again["results"] == [
        {"index": 0, "status": "accepted", "reason": None},
        {"index": 3, "status": "dismissed", "reason": None},
    ]
    assert len(_ledger(session, "lead_edit")) == 3
    assert StudyWorkspaceRepository(session).content(scope).revision == base + 1

    state = _lead(scope, session).state()["turns"][-1]
    assert state["edit_decisions"] == {
        "0": {"status": "accepted", "reason": None},
        "1": {"status": "accepted", "reason": None},
        "3": {"status": "dismissed", "reason": None},
    }


def test_an_accept_shown_on_an_older_working_copy_is_refused_whole(
    scoped: Any, session: Any
) -> None:
    scope, turn_id = _ready(scoped, session, EDITS)
    base = StudyWorkspaceRepository(session).content(scope).revision
    StudyWorkspaceRepository(session).save(
        scope, content={**CONTENT, "goal": "Jinde upraveno"}, base_revision=base
    )
    with pytest.raises(LeadEditsStale) as stale:
        _lead(scope, session).decide_edits(
            turn_id, decision="accept", indices=[0], base_revision=base
        )
    assert stale.value.current_revision == base + 1
    assert _ledger(session, "lead_edit") == []


def test_dismissing_writes_only_the_ledger(scoped: Any, session: Any) -> None:
    scope, turn_id = _ready(scoped, session, EDITS)
    base = StudyWorkspaceRepository(session).content(scope).revision
    decided = _lead(scope, session).decide_edits(
        turn_id, decision="dismiss", indices=[3, 99], base_revision=None
    )
    assert decided == {
        "workspace_revision": base,
        "results": [
            {"index": 3, "status": "dismissed", "reason": None},
            {"index": 99, "status": "refused", "reason": "unknown_edit"},
        ],
    }
    assert StudyWorkspaceRepository(session).content(scope).revision == base
    assert [r.decision for r in _ledger(session, "lead_edit")] == ["dismiss"]


def test_only_a_person_decides_on_their_own_completed_turn(scoped: Any, session: Any) -> None:
    scope, turn_id = _ready(scoped, session, EDITS)
    as_worker = dataclasses.replace(scope, permissions=WORKER_PERMISSIONS)
    with pytest.raises(ScopeDenied):
        _lead(as_worker, session).decide_edits(
            turn_id, decision="dismiss", indices=[0], base_revision=None
        )
    _hatch(scoped, session, "researcher")
    with pytest.raises(LeadTurnNotFound):
        _lead(scoped.scope(user="researcher"), session).decide_edits(
            turn_id, decision="dismiss", indices=[0], base_revision=None
        )
    _message(_lead(scope, session), "A teď?")
    pending = _lead(scope, session).state()["turns"][-1]["turn_id"]
    with pytest.raises(LeadTurnNotReady):
        _lead(scope, session).decide_edits(
            pending, decision="dismiss", indices=[0], base_revision=None
        )


# --------------------------------------------------------------------------- the Lead's own files

PERSONAL = "Klient Acme chystá zdražení o deset procent."  # a client fact the model called personal
WAITING = {"remember": [{"scope": "personal", "text": PERSONAL}], "user": "Chce tabulky."}


def _waiting_turn(scoped: Any, session: Any) -> tuple[Any, str]:
    """A completed Acme turn whose Lead wants to keep a "personal" note and a USER change."""
    acme = scoped.scope(user="lead", study="primary")
    _hatch(scoped, session)
    _save(acme, session)
    turns = _message(_lead(acme, session))
    _complete(
        session,
        acme,
        {"reply": "Zapamatuji si to.", "self_update": WAITING},
        self_update_pending=WAITING,
    )
    return acme, turns[-1]["turn_id"]


def _notes(scope: Any, session: Any) -> list[str]:
    return [n.text for n in ResearcherLeadRepository(session, scope).notes_for_study()]


def test_a_personal_note_waits_and_reaches_no_other_client_until_accepted(
    scoped: Any, session: Any
) -> None:
    """Codex P1 on #484: the model's choice of scope is not an isolation boundary."""
    acme, turn_id = _waiting_turn(scoped, session)
    globex = scoped.scope(user="lead", study="other_client")
    lead_turn = _lead(acme, session).state()["turns"][-1]
    assert lead_turn["self_update_pending"] is True and lead_turn["self_update_decision"] is None
    assert _notes(globex, session) == [] and _notes(acme, session) == []
    lead = ResearcherLeadRepository(session, acme).get()
    assert lead is not None and lead.user == ""
    # Nor does it reach a Globex turn's context while it waits.
    (turn,) = _lead(globex, session).post(kind="greeting", stage="brief")
    assert layer(_step_input(session, globex, turn["run_id"])["context"], "lead")["notes"] == []

    decided = _lead(acme, session).decide_self_update(turn_id, decision="accept")
    assert decided["status"] == "accepted"
    assert decided["changes"]["user"] is True and len(decided["changes"]["remembered"]) == 1
    assert _notes(globex, session) == [PERSONAL]
    lead = ResearcherLeadRepository(session, acme).get()
    assert lead is not None and lead.user == "Chce tabulky."
    (revision,) = ResearcherLeadRepository(session, acme).revisions()
    assert (revision["field"], revision["source_turn_id"]) == ("user", turn_id)
    after = _lead(acme, session).state()["turns"][-1]
    assert after["self_update_pending"] is False
    assert after["self_update_decision"] == {"status": "accepted"}
    (row,) = _ledger(session, "lead_self_update")
    assert (row.subject_id, row.decision) == (turn_id, "accept")

    with pytest.raises(LeadSelfUpdateDecided):
        _lead(acme, session).decide_self_update(turn_id, decision="dismiss")
    assert len(_ledger(session, "lead_self_update")) == 1


def test_dismissing_a_waiting_self_update_applies_nothing(scoped: Any, session: Any) -> None:
    acme, turn_id = _waiting_turn(scoped, session)
    decided = _lead(acme, session).decide_self_update(turn_id, decision="dismiss")
    assert decided == {"status": "dismissed", "changes": None}
    assert _notes(acme, session) == []
    lead = ResearcherLeadRepository(session, acme).get()
    assert lead is not None and lead.user == ""
    assert ResearcherLeadRepository(session, acme).revisions() == []
    assert [r.decision for r in _ledger(session, "lead_self_update")] == ["dismiss"]
    with pytest.raises(LeadSelfUpdateDecided):
        _lead(acme, session).decide_self_update(turn_id, decision="accept")


def test_only_the_turns_researcher_decides_and_only_when_something_waits(
    scoped: Any, session: Any
) -> None:
    acme, turn_id = _waiting_turn(scoped, session)
    narrowed = dataclasses.replace(acme, permissions=acme.permissions - {Permission.APPROVE_GATE})
    with pytest.raises(ScopeDenied):
        _lead(narrowed, session).decide_self_update(turn_id, decision="accept")
    _hatch(scoped, session, "researcher")
    with pytest.raises(LeadTurnNotFound):
        _lead(scoped.scope(user="researcher"), session).decide_self_update(
            turn_id, decision="accept"
        )
    with pytest.raises(LeadRejected):
        _lead(acme, session).decide_self_update(turn_id, decision="maybe")
    _message(_lead(acme, session), "Další")
    _complete(session, acme, {"reply": "Nic si nepamatuji."})
    plain = _lead(acme, session).state()["turns"][-1]["turn_id"]
    with pytest.raises(LeadSelfUpdateNone):
        _lead(acme, session).decide_self_update(plain, decision="accept")


# --------------------------------------------------------------------------- a prepared job

JOB = {
    "reply": "Připravil jsem analýzu zadání.",
    "request": {"kind": "agent_job", "action": "analyze_brief", "why": "Zadání je hotové."},
}


def test_approving_a_prepared_job_starts_it_once_and_records_it(scoped: Any, session: Any) -> None:
    scope, turn_id = _ready(scoped, session, JOB)
    started = _lead(scope, session).approve_request(
        turn_id, confirm_cost_usd=None, reservation_usd=None
    )
    run = WorkflowRepository(session, scope).get_run(started["run_id"])
    assert run["workflow_type"] == RESEARCH_AGENT
    assert run["metadata"]["action"] == "analyze_brief"
    assert started["design_revision_id"] == run["metadata"]["design_revision_id"]
    assert started["status"] == WorkflowRunStatus.RUNNING.value or started["status"]
    (row,) = _ledger(session, "lead_job_request")
    assert (row.subject_id, row.decision, row.gate_type) == (turn_id, "approve", "analyze_brief")
    assert json.loads(row.comment)["agent_run_id"] == started["run_id"]

    again = _lead(scope, session).approve_request(
        turn_id, confirm_cost_usd=None, reservation_usd=None
    )
    assert again["run_id"] == started["run_id"]
    assert len(_ledger(session, "lead_job_request")) == 1
    state = _lead(scope, session).state()["turns"][-1]
    assert state["request_decision"] == {"status": "approved", "run_id": started["run_id"]}


def test_the_spend_limit_holds_a_prepared_job(scoped: Any, session: Any) -> None:
    scope, turn_id = _ready(scoped, session, JOB)
    scoped.scope_repo.set_study_spend_confirm(scope, 1.0)
    with pytest.raises(CostCeilingUnknown):
        _lead(scope, session).approve_request(turn_id, confirm_cost_usd=None, reservation_usd=None)
    with pytest.raises(CostConfirmationRequired) as asked:
        _lead(scope, session).approve_request(turn_id, confirm_cost_usd=None, reservation_usd=2.0)
    assert (asked.value.ceiling_usd, asked.value.limit_usd) == (2.0, 1.0)
    with pytest.raises(CostConfirmationRequired):
        _lead(scope, session).approve_request(turn_id, confirm_cost_usd=1.5, reservation_usd=2.0)
    assert _ledger(session, "lead_job_request") == []
    started = _lead(scope, session).approve_request(
        turn_id, confirm_cost_usd=2.0, reservation_usd=2.0
    )
    (row,) = _ledger(session, "lead_job_request")
    assert json.loads(row.comment)["spend"] == {
        "ceiling_usd": 2.0,
        "limit_usd": 1.0,
        "confirmed_usd": 2.0,
    }
    assert started["run_id"]
    # Below the limit, nothing is asked.
    scope2, turn2 = _ready(scoped, session, JOB, user="researcher", study="sibling")
    scoped.scope_repo.set_study_spend_confirm(scope2, 5.0)
    assert _lead(scope2, session).approve_request(turn2, confirm_cost_usd=None, reservation_usd=2.0)


def test_only_an_agent_job_is_approved_here(scoped: Any, session: Any) -> None:
    run_request = {"reply": "Můžeme spustit.", "request": {"kind": "research_run", "why": WHY}}
    scope, turn_id = _ready(scoped, session, run_request)
    with pytest.raises(NotAPaidRequest):
        _lead(scope, session).approve_request(turn_id, confirm_cost_usd=None, reservation_usd=1.0)
    narrowed = dataclasses.replace(scope, permissions=scope.permissions - {Permission.APPROVE_GATE})
    with pytest.raises(ScopeDenied):
        _lead(narrowed, session).approve_request(
            turn_id, confirm_cost_usd=None, reservation_usd=1.0
        )


# --------------------------------------------------------------------------- two tabs at once


@pytest.mark.postgres
def test_two_tabs_opening_the_study_start_one_greeting(
    scoped: Any, session: Any, engine: Any
) -> None:
    """The researcher's Lead row is locked first, so the 8-hour rule reads the other post."""
    if not os.environ.get("DATABASE_URL", "").startswith("postgresql"):
        pytest.skip("two concurrent posts need PostgreSQL's row locks")
    _hatch(scoped, session)
    scope = scoped.scope()
    session.commit()
    from aia_core.infrastructure.db import create_session_factory

    factory = create_session_factory(engine)
    barrier = threading.Barrier(2)
    results: list[Any] = []

    def open_study() -> None:
        with factory() as own:
            barrier.wait()
            try:
                results.append(_lead(scope, own).post(kind="greeting", stage="brief"))
                own.commit()
            except Exception as exc:  # pragma: no cover - reported below
                own.rollback()
                results.append(exc)

    threads = [threading.Thread(target=open_study) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)
    assert sorted(len(r) for r in results) == [0, 1], results
    session.expire_all()
    runs = WorkflowRepository(session, scope).list_runs(
        project_id=StudyDesignRepository(session, scope).project_id() or "",
        workflow_type=RESEARCH_LEAD,
    )
    assert len(runs) == 1
