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
    LeadMessageNotQueued,
    LeadNotHatched,
    LeadQueueFull,
    LeadRejected,
    LeadSelfUpdateDecided,
    LeadSelfUpdateNone,
    LeadTurnNotFound,
    LeadTurnNotReady,
    LeadUnavailable,
    NotAPaidRequest,
    ResearchLead,
    set_study_budget,
    worker_readiness,
)
from aia_core.domain.edit_log import ActorKind, OpSource, WriteBy
from aia_core.domain.research_lead import (
    QUEUE_MAX,
    RememberNote,
    SelfUpdate,
    context_bytes,
    layer,
    self_update_base,
)
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
    saved = StudyWorkspaceRepository(session).save(
        scope,
        content=content,
        base_revision=None,
        by=WriteBy(ActorKind.PERSON, scope.actor_id, OpSource.UI),
    )
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
    # While the Lead works, a message waits, stored (ADR 0041 decision 7).
    (waiting,) = _message(_lead(scope, session), "A ještě?")
    assert (waiting["actor"], waiting["queued"]) == ("person", True)


def test_a_focus_on_an_audience_filter_the_copy_does_not_store_is_refused(
    scoped: Any, session: Any
) -> None:
    """artifact-audience AUD1: refused by name before anything is stored or queued."""
    scope = scoped.scope()
    _hatch(scoped, session)
    _save(scope, session, {**CONTENT, "audience": {"filters": {"kraj": ["Praha"]}}})
    lead = _lead(scope, session)
    with pytest.raises(LeadRejected, match="audience_filter_not_stored"):
        lead.post(
            kind="message",
            stage="audience",
            text="Proč tenhle filtr?",
            focus={"id": "audience:filter:vzdelani", "label": "Filtr: vzdelani"},
        )
    assert lead.state()["turns"] == []
    person, _lead_turn = lead.post(
        kind="message",
        stage="audience",
        text="Proč tenhle filtr?",
        focus={"id": "audience:filter:kraj", "label": "Filtr: kraj"},
    )
    assert person["focus"]["id"] == "audience:filter:kraj"


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
    # A message waits, stored, for the Lead to finish (ADR 0041 decision 7).
    assert [t["queued"] for t in _message(_lead(scope, session))] == [True]
    later = _lead(scope, session, clock=lambda: utcnow() + timedelta(hours=9))
    with pytest.raises(LeadBusy):
        later.post(kind="greeting", stage="brief")
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


def _park_on_budget(session: Any, scope: Any, requested: Any = 0.5) -> Any:
    """The worker's side of a turn whose reservation passes the study's budget, with the error
    the worker records (``requested_usd``: the hold the turn asked for)."""
    workflows = WorkflowRepository(session, scope)
    work = workflows.claim_next(worker_id="w", kinds={RESEARCH_LEAD_TURN})
    assert work is not None
    error = {} if requested is None else {"requested_usd": requested, "remaining_usd": 0.0}
    workflows.fail_attempt(
        work.attempt_id, worker_id="w", failure=FailureClass.BUDGET_EXCEEDED, error=error
    )
    return work


def _no_budget(scoped: Any, scope: Any) -> None:
    scoped.scope_repo.set_study_budget(scope, 0.0)


def test_a_message_written_again_before_the_budget_is_set_is_answered_not_held(
    scoped: Any, session: Any
) -> None:
    """The product owner on develop (2026-10-21): a message sent with no study budget parked
    at the cap, and that parked turn held the conversation, so every later message was refused
    (``lead_busy``) or queued by the pane behind it, for ever (F4).

    A turn parked on the budget does not hold the conversation. A message written before the
    budget is set supersedes it: the parked run is cancelled, never paid, and the new turn
    carries the unanswered message in its history. Only one turn is ever waiting, so a lift
    never pays for a stack.
    """
    scope = scoped.scope()
    _hatch(scoped, session)
    _no_budget(scoped, scope)
    first = _message(_lead(scope, session), "Kde studie stojí?")
    _park_on_budget(session, scope)
    state = _lead(scope, session).state()
    parked = state["turns"][-1]
    assert (parked["status"], parked["reason"]) == ("WAITING", "budget_exceeded")
    assert state["busy"] is False

    turns = _message(_lead(scope, session), "Jsi tam?")
    assert [t["actor"] for t in turns] == ["person", "lead"]
    assert turns[-1]["status"] == "QUEUED"

    workflows = WorkflowRepository(session, scope)
    old = workflows.get_run(first[-1]["run_id"])
    assert old["status"] is WorkflowRunStatus.CANCELLED
    state = _lead(scope, session).state()
    assert state["busy"] is True  # the new turn is queued: the pane waits for it alone
    by_id = {t["turn_id"]: t for t in state["turns"]}
    assert by_id[first[-1]["turn_id"]]["status"] == "CANCELLED"
    # The parked turn's message is answered by the new turn, with the new one, in order.
    context = _step_input(session, scope, turns[-1]["run_id"])["context"]
    asked = [m["text"] for m in layer(context, "view")["messages"]]
    assert asked == ["Kde studie stojí?", "Jsi tam?"]
    assert turns[-1]["answers"] == [first[0]["turn_id"], turns[0]["turn_id"]]
    _complete(session, scope, {"reply": "Ano."})
    assert _lead(scope, session).state()["busy"] is False


def test_setting_the_budget_sends_the_parked_message_and_records_the_person(
    scoped: Any, session: Any
) -> None:
    """The product owner, 2026-10-21 (Q39): "once the budget is set or raised, it should
    automatically resend the message the researcher attempted to send in the first place".
    The person setting the budget is the consent, recorded in the ledger as every lift is."""
    scope = scoped.scope()
    _hatch(scoped, session)
    _no_budget(scoped, scope)
    first = _message(_lead(scope, session), "Kde studie stojí?")
    work = _park_on_budget(session, scope, requested=0.5)

    study, released = set_study_budget(session, scope, 5.0)
    assert study.budget_usd == 5.0 and released == [first[-1]["run_id"]]
    state = _lead(scope, session).state()
    assert state["turns"][-1]["status"] == "QUEUED" and state["busy"] is True
    rows = session.scalars(
        select(ApprovalDecisionRow).where(ApprovalDecisionRow.run_id == first[-1]["run_id"])
    ).all()
    assert [(r.gate_type, r.decision, r.step_id) for r in rows] == [
        ("budget", "lift", work.step_id)
    ]
    assert rows[0].approver_user_id == scope.actor_id

    # The message is answered without being written again; the next one goes as usual.
    _complete(session, scope, {"reply": "Ve fázi zadání."})
    state = _lead(scope, session).state()
    assert state["busy"] is False and state["turns"][-1]["output"] == {"reply": "Ve fázi zadání."}
    assert len(_message(_lead(scope, session), "Díky")) == 2


def test_a_budget_still_too_small_leaves_the_turn_parked(scoped: Any, session: Any) -> None:
    """A hold that would still pass the new budget is not sent; nor is one whose hold the
    attempt did not record (unknown never fits), nor anything on a budget lowered or kept."""
    scope = scoped.scope()
    _hatch(scoped, session)
    _no_budget(scoped, scope)
    _message(_lead(scope, session))
    _park_on_budget(session, scope, requested=10.0)

    assert set_study_budget(session, scope, 5.0)[1] == []
    assert set_study_budget(session, scope, 5.0)[1] == []  # kept, not raised
    assert set_study_budget(session, scope, 1.0)[1] == []  # lowered
    turn = _lead(scope, session).state()["turns"][-1]
    assert (turn["status"], turn["reason"]) == ("WAITING", "budget_exceeded")
    assert session.scalars(select(ApprovalDecisionRow)).all() == []
    assert set_study_budget(session, scope, 10.0)[1] != []  # now it fits


def test_a_turn_parked_behind_more_than_a_page_of_later_runs_is_still_sent(
    scoped: Any, session: Any
) -> None:
    """Codex on #547: the release read the newest 200 Lead runs, so a turn parked behind more
    than 200 later ones was never found and stayed parked for ever. It reads the waiting steps
    themselves."""
    from aia_core.application.workflows import start_workflow
    from aia_core.domain.design import DESIGN_PROJECT_OWNER

    scope = scoped.scope()
    _hatch(scoped, session)
    _no_budget(scoped, scope)
    first = _message(_lead(scope, session))
    _park_on_budget(session, scope, requested=0.5)
    parked = WorkflowRepository(session, scope).get_run(first[-1]["run_id"])
    for i in range(201):  # later Lead runs, as other turns of the study would leave them
        start_workflow(
            session,
            scope,
            project_id=parked["project_id"],
            revision=parked["project_revision"],
            workflow_type=RESEARCH_LEAD,
            idempotency_key=f"{RESEARCH_LEAD}:later-{i}",
            step_inputs={"turn": {}},
            owner=DESIGN_PROJECT_OWNER,
        )
    assert first[-1]["run_id"] not in {
        r["run_id"]
        for r in WorkflowRepository(session, scope).list_runs(
            project_id=parked["project_id"], workflow_type=RESEARCH_LEAD, limit=200
        )
    }
    assert set_study_budget(session, scope, 5.0)[1] == [first[-1]["run_id"]]


@pytest.mark.parametrize("requested", [None, True, -1.0, "0.5"])
def test_a_parked_turn_whose_hold_is_unknown_stays_parked(
    scoped: Any, session: Any, requested: Any
) -> None:
    """A hold the attempt did not record as a number of USD is unknown, and unknown never fits:
    a bool or a negative hold passed as one. (NaN and inf cannot be stored in PostgreSQL's JSONB;
    _recorded_hold refuses them below.)"""
    scope = scoped.scope()
    _hatch(scoped, session)
    _no_budget(scoped, scope)
    _message(_lead(scope, session))
    _park_on_budget(session, scope, requested=requested)
    assert set_study_budget(session, scope, 500.0)[1] == []
    assert _lead(scope, session).state()["turns"][-1]["status"] == "WAITING"


@pytest.mark.parametrize(
    ("value", "hold"),
    [
        (0.5, 0.5),
        (2, 2.0),
        (0, 0.0),
        (None, None),
        (True, None),
        (-1.0, None),
        ("0.5", None),
        (float("nan"), None),
        (float("inf"), None),
    ],
)
def test_a_recorded_hold_is_a_finite_non_negative_number_of_usd(value: Any, hold: Any) -> None:
    """NaN compared as fitting anything, so it is refused here, beside inf."""
    from aia_core.application.research_lead import _recorded_hold

    assert _recorded_hold(value) == hold


def test_a_greeting_does_not_supersede_a_message_waiting_for_budget(
    scoped: Any, session: Any
) -> None:
    """Opening the study greets; it never cancels the person's own message."""
    scope = scoped.scope()
    _hatch(scoped, session)
    first = _message(_lead(scope, session))
    _park_on_budget(session, scope)
    later = _lead(scope, session, clock=lambda: utcnow() + timedelta(days=1))
    assert later.post(kind="greeting", stage="brief") == []
    run = WorkflowRepository(session, scope).get_run(first[-1]["run_id"])
    assert run["status"] is not WorkflowRunStatus.CANCELLED


def test_a_turn_resumed_from_a_budget_wait_holds_the_conversation(
    scoped: Any, session: Any
) -> None:
    """The review of baac33d5: messages must not stack paid turns behind one another. A turn
    whose budget wait a person lifted is queued again, and holds the conversation as any
    queued turn does, until it is answered."""
    scope = scoped.scope()
    _hatch(scoped, session)
    _message(_lead(scope, session))
    work = _park_on_budget(session, scope)
    budget = float(scoped.scope_repo.get_study(scope).budget_usd)
    WorkflowRepository(session, scope).resume_budget_wait(
        work.step_id, budget_before=budget, budget_after=budget
    )
    assert _lead(scope, session).state()["busy"] is True
    # A message waits behind it, stored; nothing paid is stacked behind the resumed turn.
    (waiting,) = _message(_lead(scope, session), "Jsi tam?")
    assert waiting["queued"] is True
    _complete(session, scope, {"reply": "Hotovo."})
    assert _lead(scope, session).state()["busy"] is False
    assert len(_message(_lead(scope, session), "Další")) == 2


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


def test_the_next_turn_carries_what_the_conversation_decided(scoped: Any, session: Any) -> None:
    """ADR 0041 decision 4: the decision digest, from the ledger, in the next turn's context."""
    scope, turn_id = _ready(scoped, session, EDITS)
    base = StudyWorkspaceRepository(session).content(scope).revision
    lead = _lead(scope, session)
    lead.decide_edits(turn_id, decision="accept", indices=[0], base_revision=base)
    lead.decide_edits(turn_id, decision="dismiss", indices=[3], base_revision=None)
    (_, nxt) = _lead(scope, session).post(
        kind="message",
        stage="brief",
        text="A název?",
        focus={"id": "brief:title", "label": "Název"},
    )
    digest = layer(_step_input(session, scope, nxt["run_id"])["context"], "memory")["digest"]
    rows = {r.subject_id: r.decision_id for r in _ledger(session, "lead_edit")}
    assert digest["named"] == [
        {"kind": "edit", "item": "brief:title", "turn": turn_id, "decision": "accept",
         "ledger": rows[f"{turn_id}:0"]}
    ]  # fmt: skip
    assert digest["latest"] == [
        {"kind": "edit", "item": "sample:n", "turn": turn_id, "decision": "dismiss",
         "ledger": rows[f"{turn_id}:3"]}
    ]  # fmt: skip
    assert [(p["item"], p["index"]) for p in digest["undecided"]] == [
        ("question:q9", 2),
        ("plan:plan.objectives:Ověřit cenu", 1),
    ]


def test_another_researchers_decisions_are_not_in_my_digest(scoped: Any, session: Any) -> None:
    scope, turn_id = _ready(scoped, session, EDITS)
    base = StudyWorkspaceRepository(session).content(scope).revision
    _lead(scope, session).decide_edits(turn_id, decision="accept", indices=[0], base_revision=base)
    other = scoped.scope(user="researcher")
    _hatch(scoped, session, "researcher")
    (_, theirs) = _message(_lead(other, session))
    digest = layer(_step_input(session, other, theirs["run_id"])["context"], "memory")["digest"]
    assert digest["named"] == digest["latest"] == digest["undecided"] == []


@pytest.mark.parametrize(
    ("output", "waiting"),
    [
        ({"reply": "Můžeme spustit.", "request": {"kind": "research_run", "why": WHY}}, []),
        (
            {
                "reply": "Připravil.",
                "request": {"kind": "agent_job", "action": "analyze_brief", "why": WHY},
            },
            ["job"],
        ),
    ],
)
def test_only_a_prepared_job_waits_in_the_digest(
    scoped: Any, session: Any, output: dict[str, Any], waiting: list[str]
) -> None:
    # A run card is started from its own screen and is never decided through the ledger, so
    # it is no waiting proposal; a prepared agent job is one until a person decides it.
    scope, _ = _ready(scoped, session, output)
    (_, nxt) = _message(_lead(scope, session))
    digest = layer(_step_input(session, scope, nxt["run_id"])["context"], "memory")["digest"]
    assert [p["kind"] for p in digest["undecided"]] == waiting


def test_a_turns_manifest_is_what_it_froze_and_only_its_researchers(
    scoped: Any, session: Any
) -> None:
    """Co Vedoucí vidí (LC2): read from the turn's frozen context, never today's study."""
    scope = scoped.scope()
    _hatch(scoped, session)
    _save(scope, session)
    person, turn = _message(_lead(scope, session))
    frozen = _step_input(session, scope, turn["run_id"])["context"]
    read = _lead(scope, session).manifest(turn["turn_id"])
    assert read["recorded"] is True
    assert read["manifest"]["total_bytes"] == context_bytes(frozen)
    view = next(r for r in read["manifest"]["layers"] if r["layer"] == "view")
    assert view["included"] == ["brief:goal"]
    with pytest.raises(LeadTurnNotFound):
        _lead(scope, session).manifest(person["turn_id"])  # a person's turn saw nothing
    other = scoped.scope(user="researcher")
    with pytest.raises(LeadTurnNotFound):
        _lead(other, session).manifest(turn["turn_id"])
    with pytest.raises(LeadTurnNotFound):
        _lead(other, session).omitted(turn["turn_id"], "knowledge")
    assert _lead(scope, session).omitted(turn["turn_id"], "knowledge") == ([], 0)


# --------------------------------------------------------------------------- the queue (LC5a)


def _busy(scoped: Any, session: Any) -> Any:
    """A hatched researcher whose Lead is answering a first message."""
    scope = scoped.scope()
    _hatch(scoped, session)
    _save(scope, session)
    _message(_lead(scope, session), "První")
    return scope


def test_messages_from_two_tabs_while_the_lead_works_are_answered_by_one_turn(
    scoped: Any, session: Any
) -> None:
    scope = _busy(scoped, session)
    (a,) = _lead(scope, session).post(kind="message", stage="brief", text="Z první karty")
    (b,) = _lead(scope, session).post(kind="message", stage="design", text="Z druhé karty")
    assert a["queued"] and b["queued"]
    assert _lead(scope, session).answer_queued() == []  # the Lead is still at work
    _complete(session, scope, {"reply": "Hotovo."})
    (turn,) = _lead(scope, session).answer_queued()
    assert turn["answers"] == [a["turn_id"], b["turn_id"]]
    view = layer(_step_input(session, scope, turn["run_id"])["context"], "view")
    assert view["message"] is None and "queued_deferred" not in view
    assert [(m["text"], m["stage"]) for m in view["messages"]] == [
        ("Z první karty", "brief"),
        ("Z druhé karty", "design"),
    ]
    # A second tab asking finds the turn already started: nothing more.
    assert _lead(scope, session).answer_queued() == []
    state = {t["turn_id"]: t for t in _lead(scope, session).state()["turns"]}
    assert not state[a["turn_id"]]["queued"] and not state[b["turn_id"]]["queued"]
    # The turn is frozen with the messages in its view, not twice in the conversation.
    history = layer(_step_input(session, scope, turn["run_id"])["context"], "conversation")
    assert [t.get("text") for t in history["turns"] if t["actor"] == "person"] == ["První"]


def test_a_withdrawn_message_is_never_answered(scoped: Any, session: Any) -> None:
    scope = _busy(scoped, session)
    (kept,) = _lead(scope, session).post(kind="message", stage="brief", text="Platí")
    (gone,) = _lead(scope, session).post(kind="message", stage="brief", text="Neplatí")
    _lead(scope, session).withdraw(gone["turn_id"])
    with pytest.raises(LeadMessageNotQueued):
        _lead(scope, session).withdraw(gone["turn_id"])
    _complete(session, scope, {"reply": "Hotovo."})
    (turn,) = _lead(scope, session).answer_queued()
    assert turn["answers"] == [kept["turn_id"]]
    state = _lead(scope, session).state()["turns"]
    by_id = {t["turn_id"]: t for t in state}
    assert by_id[gone["turn_id"]]["withdrawn"] is True
    assert by_id[gone["turn_id"]]["queued"] is False
    assert all(t["kind"] != "withdrawal" for t in state)  # the withdrawal row is not a turn shown
    with pytest.raises(LeadMessageNotQueued):
        _lead(scope, session).withdraw(kept["turn_id"])  # answered: no longer waiting
    with pytest.raises(LeadTurnNotFound):
        _lead(scoped.scope(user="researcher"), session).withdraw(kept["turn_id"])


def test_erasing_a_members_turns_deletes_their_answer_rows_and_no_one_elses(
    scoped: Any, session: Any
) -> None:
    from aia_core.infrastructure.study_lead_repository import erase_member_turns
    from aia_core.infrastructure.tables import StudyLeadTurnAnswerRow, StudyLeadTurnRow

    scope = _busy(scoped, session)
    _lead(scope, session).post(kind="message", stage="brief", text="Ve frontě")
    _complete(session, scope, {"reply": "Hotovo."})
    assert _lead(scope, session).answer_queued()
    other = scoped.scope(user="researcher")
    _hatch(scoped, session, "researcher")
    _message(_lead(other, session), "Jiný výzkumník")

    def answers(user: str) -> int:
        return len(
            session.scalars(
                select(StudyLeadTurnAnswerRow).where(StudyLeadTurnAnswerRow.user_id == user)
            ).all()
        )

    assert answers(scope.actor_id) and answers(other.actor_id)
    erase_member_turns(session, organization_id=scope.organization_id, user_id=scope.actor_id)
    session.flush()
    assert answers(scope.actor_id) == 0
    assert not session.scalars(
        select(StudyLeadTurnRow).where(StudyLeadTurnRow.user_id == scope.actor_id)
    ).all()
    assert answers(other.actor_id)  # another member's conversation is untouched


def test_erasing_a_clients_lead_turns_deletes_their_answer_rows(scoped: Any, session: Any) -> None:
    from aia_core.infrastructure.study_lead_repository import erase_client_lead_turns
    from aia_core.infrastructure.tables import StudyLeadTurnAnswerRow

    scope = _busy(scoped, session)
    _lead(scope, session).post(kind="message", stage="brief", text="Ve frontě")
    _complete(session, scope, {"reply": "Hotovo."})
    assert _lead(scope, session).answer_queued()
    rows = select(StudyLeadTurnAnswerRow).where(StudyLeadTurnAnswerRow.study_id == scope.study_id)
    assert session.scalars(rows).all()
    erase_client_lead_turns(session, client_id=scope.client_id)
    assert session.scalars(rows).all() == []


def test_a_message_is_bounded_in_bytes_and_the_queue_in_count(scoped: Any, session: Any) -> None:
    scope = _busy(scoped, session)
    with pytest.raises(LeadRejected) as refused:
        _lead(scope, session).post(kind="message", stage="brief", text="😀" * 4000)
    assert refused.value.reason == "message_too_long"
    for i in range(QUEUE_MAX):
        _lead(scope, session).post(kind="message", stage="brief", text=f"Zpráva {i}")
    with pytest.raises(LeadQueueFull):
        _lead(scope, session).post(kind="message", stage="brief", text="Šestá")


def test_a_waiting_messages_focus_is_checked_again_when_its_turn_is_frozen(
    scoped: Any, session: Any
) -> None:
    """Another tab removes the filter a waiting message pointed at: the message is sent, its
    focus is not (the review of LC5a, the race of Codex on #624)."""
    scope = scoped.scope()
    _hatch(scoped, session)
    base = _save(scope, session, {**CONTENT, "audience": {"filters": {"kraj": ["Praha"]}}})
    _message(_lead(scope, session), "První")
    (waiting,) = _lead(scope, session).post(
        kind="message",
        stage="audience",
        text="Proč tenhle filtr?",
        focus={"id": "audience:filter:kraj", "label": "Filtr: kraj"},
    )
    StudyWorkspaceRepository(session).save(
        scope,
        content=CONTENT,
        base_revision=base,
        by=WriteBy(ActorKind.PERSON, scope.actor_id, OpSource.UI),
    )
    _complete(session, scope, {"reply": "Hotovo."})
    (turn,) = _lead(scope, session).answer_queued()
    view = layer(_step_input(session, scope, turn["run_id"])["context"], "view")
    assert view["message"] == "Proč tenhle filtr?" and view["focus"] is None
    assert turn["answers"] == [waiting["turn_id"]]


def test_a_free_lead_takes_a_message_with_a_full_queue(scoped: Any, session: Any) -> None:
    """Only a busy Lead's queue fills up: a free one answers what waits with the new message."""
    scope = _busy(scoped, session)
    for i in range(QUEUE_MAX):
        _lead(scope, session).post(kind="message", stage="brief", text=f"Zpráva {i}")
    _complete(session, scope, {"reply": "Hotovo."})
    person, turn = _lead(scope, session).post(kind="message", stage="brief", text="Šestá")
    assert turn["actor"] == "lead" and person["turn_id"] in turn["answers"]
    assert len(turn["answers"]) == QUEUE_MAX + 1


def test_large_queued_messages_are_answered_one_turn_each_never_cut(
    scoped: Any, session: Any
) -> None:
    """Five 8 KB messages: one fits layer 9's 12 KB, two do not. A chain of five turns, each
    naming the rest as deferred; each message sent whole."""
    scope = _busy(scoped, session)
    big = ["ž" * 4000 for _ in range(QUEUE_MAX)]  # 8,000 bytes each
    ids = [
        _lead(scope, session).post(kind="message", stage="brief", text=t)[0]["turn_id"] for t in big
    ]
    _complete(session, scope, {"reply": "Hotovo."})
    for i in range(QUEUE_MAX):
        (turn,) = _lead(scope, session).answer_queued()
        assert turn["answers"] == [ids[i]]
        view = layer(_step_input(session, scope, turn["run_id"])["context"], "view")
        assert view["message"] == big[i]
        assert view.get("queued_deferred", []) == ids[i + 1 :]
        _complete(session, scope, {"reply": "Hotovo."})
    assert _lead(scope, session).answer_queued() == []


def test_small_queued_messages_pack_into_one_turn_while_they_fit(scoped: Any, session: Any) -> None:
    scope = _busy(scoped, session)
    texts = ["ž" * 2000, "ž" * 2000, "ž" * 2000]  # 4,000 bytes each: all three fit 12 KB
    for t in texts:
        _lead(scope, session).post(kind="message", stage="brief", text=t)
    _complete(session, scope, {"reply": "Hotovo."})
    (turn,) = _lead(scope, session).answer_queued()
    assert len(turn["answers"]) == 3


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
    # A click is no automatic accept: "auto" is false (plan inline-decisions chunk 2).
    assert state["edit_decisions"] == {
        "0": {"status": "accepted", "reason": None, "auto": False},
        "1": {"status": "accepted", "reason": None, "auto": False},
        "3": {"status": "dismissed", "reason": None, "auto": False},
    }
    assert "auto" not in json.loads(rows[0].comment)


def test_an_accept_shown_on_an_older_working_copy_is_refused_whole(
    scoped: Any, session: Any
) -> None:
    scope, turn_id = _ready(scoped, session, EDITS)
    base = StudyWorkspaceRepository(session).content(scope).revision
    StudyWorkspaceRepository(session).save(
        scope,
        content={**CONTENT, "goal": "Jinde upraveno"},
        base_revision=base,
        by=WriteBy(ActorKind.PERSON, scope.actor_id, OpSource.UI),
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
    frozen = _step_input(session, acme, turns[-1]["run_id"])["context"]
    _complete(
        session,
        acme,
        {"reply": "Zapamatuji si to.", "self_update": WAITING},
        self_update_pending=WAITING,
        self_update_base=self_update_base(layer(frozen, "lead")),
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
    assert after["self_update_decision"] == {"status": "accepted", "stale": []}
    (row,) = _ledger(session, "lead_self_update")
    assert (row.subject_id, row.decision) == (turn_id, "accept")

    with pytest.raises(LeadSelfUpdateDecided):
        _lead(acme, session).decide_self_update(turn_id, decision="dismiss")
    assert len(_ledger(session, "lead_self_update")) == 1


def test_dismissing_a_waiting_self_update_applies_nothing(scoped: Any, session: Any) -> None:
    acme, turn_id = _waiting_turn(scoped, session)
    decided = _lead(acme, session).decide_self_update(turn_id, decision="dismiss")
    assert decided == {"status": "dismissed", "changes": None, "stale": []}
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
    # The job's own start applied the same rule (LO15) and wrote the job's spend row.
    (spend,) = _ledger(session, "spend")
    assert (spend.run_id, spend.decision) == (started["run_id"], "confirm")
    assert json.loads(spend.comment) == {"ceiling_usd": 2.0, "limit_usd": 1.0, "confirmed_usd": 2.0}
    # Below the limit, nothing is asked.
    scope2, turn2 = _ready(scoped, session, JOB, user="researcher", study="sibling")
    scoped.scope_repo.set_study_spend_confirm(scope2, 5.0)
    assert _lead(scope2, session).approve_request(turn2, confirm_cost_usd=None, reservation_usd=2.0)


def test_an_approval_that_finds_its_job_already_there_records_no_new_spend(
    scoped: Any, session: Any
) -> None:
    """Two turns preparing the same job on the same design: the second approval starts nothing
    (the job exists), so its ledger row confirms no spend and no second spend row is written."""
    scope, first = _ready(scoped, session, JOB)
    scoped.scope_repo.set_study_spend_confirm(scope, 1.0)
    one = _lead(scope, session).approve_request(first, confirm_cost_usd=2.0, reservation_usd=2.0)
    second = _message(_lead(scope, session))[-1]["turn_id"]
    _complete(session, scope, JOB)
    two = _lead(scope, session).approve_request(second, confirm_cost_usd=2.0, reservation_usd=2.0)
    assert two["run_id"] == one["run_id"]
    rows = {r.subject_id: json.loads(r.comment) for r in _ledger(session, "lead_job_request")}
    assert rows[first]["spend"] == {"ceiling_usd": 2.0, "limit_usd": 1.0, "confirmed_usd": 2.0}
    assert rows[second]["spend"] is None
    assert len(_ledger(session, "spend")) == 1


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


def _t(actor: str, status: str, reason: str | None = None) -> dict[str, Any]:
    return {"actor": actor, "status": status, "reason": reason}


NOT_READY_UNCONFIGURED = (False, "newest_turn", "research_lead_unconfigured")
NOT_READY_RUNTIME = (False, "newest_turn", "ai_runtime_unavailable")


@pytest.mark.parametrize(
    "turns,expected",
    [
        ([], (None, None, None)),
        ([_t("person", "COMPLETED")], (None, None, None)),
        ([_t("lead", "COMPLETED")], (None, None, None)),
        ([_t("lead", "WAITING", "research_lead_unconfigured")], NOT_READY_UNCONFIGURED),
        ([_t("lead", "FAILED", "ai_runtime_unavailable")], NOT_READY_RUNTIME),
        # A park that does not name the worker's composition says nothing about it.
        ([_t("lead", "WAITING", "budget_exceeded")], (None, None, None)),
        ([_t("lead", "WAITING", "egress_no_approved_route")], (None, None, None)),
        # The newest decided turn speaks; one still queued or cancelled is skipped.
        (
            [_t("lead", "WAITING", "research_lead_unconfigured"), _t("lead", "QUEUED")],
            NOT_READY_UNCONFIGURED,
        ),
        (
            [_t("lead", "WAITING", "research_lead_unconfigured"), _t("lead", "COMPLETED")],
            (None, None, None),
        ),
        (
            [_t("lead", "WAITING", "ai_runtime_unavailable"), _t("lead", "CANCELLED")],
            NOT_READY_RUNTIME,
        ),
    ],
)
def test_the_worker_is_never_read_as_ready(
    turns: list[dict[str, Any]], expected: tuple[bool | None, str | None, str | None]
) -> None:
    """27b without LO12b's record: only a park naming the worker's composition says anything
    (not ready); nothing says ready."""
    assert worker_readiness(turns) == expected
    assert worker_readiness(turns)[0] is not True


PIN = {"deep_research_run_id": "RUN-dr1", "artifact_id": "ART-b1", "sha256": "ab" * 32}


def test_external_context_is_frozen_only_when_switched_on_and_pinned(
    scoped: Any, session: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """evidence-integrity 7: the Study's newest Design Research findings reach the Lead's turn as
    external context, read through the same pinned, seal-verified reader as the analysis."""
    from aia_core.application import research_lead as module
    from aia_core.application.research import ResearchRuns
    from aia_core.domain.research_lead import EXTERNAL_LAYER
    from aia_core.infrastructure.storage import InMemoryArtifactStore

    scope = scoped.scope()
    _hatch(scoped, session)
    _save(scope, session)
    store = InMemoryArtifactStore()
    read: list[object] = []

    def reader(_session: Any, _scope: Any, given: Any, pin: Any) -> tuple[str, ...]:
        read.append((given, pin))
        return ("[EV-1] Trh roste. (cs.wikipedia.org)",)

    monkeypatch.setattr(module, "_external_context", reader)
    monkeypatch.setattr(ResearchRuns, "design_research_pin", lambda self: PIN)

    def frozen(lead: ResearchLead, text: str) -> dict[str, Any]:
        turns = _message(lead, text)
        context = _step_input(session, scope, turns[-1]["run_id"])["context"]
        _complete(session, scope, {"reply": "Ano."})
        return context

    off = frozen(_lead(scope, session), "Bez rešerše?")
    assert EXTERNAL_LAYER not in [e["layer"] for e in off["layers"]] and read == []
    on = frozen(_lead(scope, session, external_store=store), "S rešerší?")
    assert layer(on, EXTERNAL_LAYER)["lines"] == ["[EV-1] Trh roste. (cs.wikipedia.org)"]
    assert layer(on, EXTERNAL_LAYER)["pin"] == PIN and read == [(store, PIN)]

    # No finished Design Research: no layer. A bundle that does not read: said, never a stop.
    monkeypatch.setattr(ResearchRuns, "design_research_pin", lambda self: None)
    none = frozen(_lead(scope, session, external_store=store), "Bez běhu?")
    assert EXTERNAL_LAYER not in [e["layer"] for e in none["layers"]]

    def refused(*_: Any) -> tuple[str, ...]:
        raise module.SourcesRefused("context_unverified", "the pinned bundle does not read")

    monkeypatch.setattr(ResearchRuns, "design_research_pin", lambda self: PIN)
    monkeypatch.setattr(module, "_external_context", refused)
    broken = frozen(_lead(scope, session, external_store=store), "Rozbitá?")
    assert layer(broken, EXTERNAL_LAYER)["lines"] == []
    assert layer(broken, EXTERNAL_LAYER)["unavailable"] == "context_unverified"
