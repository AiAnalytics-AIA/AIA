"""The Research Lead over HTTP: the caller's conversation, their own Lead, and their decisions.

ADR 0026 and the product owner's 2026-10-19 decisions. The API enqueues and reads; nothing
here calls a model. A completed turn is made by completing its step through the workflow
repository, as a worker would.
"""

from __future__ import annotations

import json
from typing import Any

import pytest
from aia_core.application.research import research_artifacts
from aia_core.application.scope import AuthenticatedPrincipal, ScopeResolver
from aia_core.domain.approval_ledger import ApprovalSubject
from aia_core.domain.research_lead import ARTIFACT_TYPE
from aia_core.domain.workflow import FailureClass
from aia_core.domain.workflow_templates import RESEARCH_AGENT, RESEARCH_LEAD_TURN
from aia_core.infrastructure.db import create_session_factory
from aia_core.infrastructure.scope_repository import ScopeRepository
from aia_core.infrastructure.study_workspace_repository import StudyWorkspaceRepository
from aia_core.infrastructure.tables import (
    AccessAuditRow,
    ApprovalDecisionRow,
    BudgetReservationRow,
    WorkflowRunRow,
)
from aia_core.infrastructure.workflow_repository import WorkflowRepository
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select

from aia_api.config import Settings

CONTENT: dict[str, Any] = {
    "title": "Fiktivní koncept",
    "sections": [{"id": "s1", "type": "questions", "questions": [{"id": "q1", "text": "Znáte?"}]}],
}
WHY = "Zadání to potřebuje."


@pytest.fixture
def settings(settings: Settings) -> Settings:
    return settings.model_copy(
        update={"ai_research_lead_enabled": True, "ai_research_reservation_usd": 2.0}
    )


def lead_url(world: Any, study: str = "primary") -> str:
    return f"/api/v1/studies/{world.study_id(study)}/lead"


def _scope(app: FastAPI, world: Any, session: Any, user: str = "researcher") -> Any:
    return ScopeResolver(session).study_context(
        AuthenticatedPrincipal(user_id=world.users[user], organization_id=world.organization_id),
        study_id=world.study_id(),
    )


def _save_content(app: FastAPI, world: Any) -> int:
    with create_session_factory(app.state.engine)() as session:
        saved = StudyWorkspaceRepository(session).save(
            _scope(app, world, session), content=CONTENT, base_revision=None
        )
        session.commit()
        return saved.revision


def _complete(app: FastAPI, world: Any, output: dict[str, Any], **extra: Any) -> None:
    with create_session_factory(app.state.engine)() as session:
        workflows = WorkflowRepository(session, _scope(app, world, session))
        work = workflows.claim_next(worker_id="w", kinds={RESEARCH_LEAD_TURN})
        assert work is not None
        workflows.complete_attempt(
            work.attempt_id,
            worker_id="w",
            output={
                "lead_output": output,
                "dropped": [],
                "self_update_applied": None,
                **extra,
            },
        )
        session.commit()


def _hatched(client: TestClient) -> None:
    assert client.post("/api/v1/lead").status_code == 201


def _turn(client: TestClient, world: Any, app: FastAPI, output: dict[str, Any]) -> str:
    _hatched(client)
    _save_content(app, world)
    posted = client.post(
        f"{lead_url(world)}/turns", json={"kind": "message", "stage": "brief", "text": "Co dál?"}
    )
    assert posted.status_code == 201, posted.text
    _complete(app, world, output)
    return str(posted.json()["turns"][-1]["turn_id"])


# --------------------------------------------------------------------------- the caller's Lead


def test_a_lead_is_hatched_once_and_read_only(researcher: TestClient) -> None:
    assert researcher.get("/api/v1/lead").json() == {"hatched": False, "lead": None}
    hatched = researcher.post("/api/v1/lead")
    assert hatched.status_code == 201
    lead = hatched.json()["lead"]
    assert set(lead) == {
        "lead_id",
        "name",
        "hatched_at",
        "updated_at",
        "files",
        "memories",
        "preferences",
    }
    # Off until the researcher turns it on (plan inline-decisions chunk 2).
    assert lead["preferences"] == {"auto_accept_text_edits": False}
    assert lead["name"] == "Vedoucí výzkumu" and lead["memories"] == []
    assert set(lead["files"]) == {"soul", "user"} and lead["files"]["user"] == ""
    again = researcher.post("/api/v1/lead")
    assert again.status_code == 409 and again.json()["code"] == "lead_already_hatched"
    assert researcher.get("/api/v1/lead").json() == {"hatched": True, "lead": lead}
    # Read-only: nothing over HTTP writes the files or the notes.
    assert researcher.put("/api/v1/lead", json={"name": "x"}).status_code == 405
    assert researcher.post("/api/v1/lead/memories", json={"text": "x"}).status_code == 404


def test_each_researcher_has_their_own_lead(researcher: TestClient, viewer: TestClient) -> None:
    _hatched(researcher)
    assert viewer.get("/api/v1/lead").json() == {"hatched": False, "lead": None}


# --------------------------------------------------------------------------- the conversation


def test_a_turn_is_refused_until_the_lead_is_hatched(researcher: TestClient, world: Any) -> None:
    for body in (
        {"kind": "greeting", "stage": "brief"},
        {"kind": "message", "stage": "brief", "text": "Ahoj"},
    ):
        refused = researcher.post(f"{lead_url(world)}/turns", json=body)
        assert refused.status_code == 409 and refused.json()["code"] == "lead_not_hatched"


def test_a_message_queues_a_turn_and_the_lead_answers_one_at_a_time(
    researcher: TestClient, world: Any
) -> None:
    _hatched(researcher)
    posted = researcher.post(
        f"{lead_url(world)}/turns",
        json={
            "kind": "message",
            "stage": "brief",
            "text": "Kde stojíme?",
            "focus": {"id": "brief:goal", "label": "Cíl"},
        },
    )
    assert posted.status_code == 201, posted.text
    person, lead = posted.json()["turns"]
    assert (person["actor"], person["status"], person["output"]) == ("person", "COMPLETED", None)
    assert person["focus"] == {"id": "brief:goal", "label": "Cíl"}
    assert (lead["actor"], lead["status"], lead["reason"]) == ("lead", "QUEUED", None)
    assert lead["run_id"].startswith("RUN-") and lead["edit_decisions"] == {}
    assert set(lead) == {
        "turn_id",
        "sequence_no",
        "actor",
        "kind",
        "stage",
        "text",
        "focus",
        "status",
        "reason",
        "output",
        "changes",
        "dropped",
        "edit_decisions",
        "request_decision",
        "self_update_decision",
        "self_update_pending",
        "self_update_waiting",
        "run_id",
        "workspace_revision",
        "created_at",
        "created_by",
    }

    busy = researcher.post(
        f"{lead_url(world)}/turns", json={"kind": "message", "stage": "brief", "text": "Haló?"}
    )
    assert busy.status_code == 409 and busy.json()["code"] == "lead_busy"
    greeting = researcher.post(
        f"{lead_url(world)}/turns", json={"kind": "greeting", "stage": "brief"}
    )
    assert greeting.status_code == 200 and greeting.json() == {"turns": []}

    state = researcher.get(lead_url(world)).json()
    assert (state["available"], state["unavailable_reason"], state["busy"]) == (True, None, True)
    assert [t["turn_id"] for t in state["turns"]] == [person["turn_id"], lead["turn_id"]]


def test_the_state_reads_the_reply_from_the_turns_step(
    researcher: TestClient, world: Any, app: FastAPI
) -> None:
    output = {"reply": "Studie je ve fázi zadání.", "follow": ["Co dál?"]}
    turn_id = _turn(researcher, world, app, output)
    state = researcher.get(lead_url(world)).json()
    assert state["busy"] is False
    lead = state["turns"][-1]
    assert lead["turn_id"] == turn_id and lead["status"] == "COMPLETED"
    assert lead["output"] == output and "data_class" not in lead


def test_another_researcher_reads_none_of_my_conversation(
    researcher: TestClient, viewer: TestClient, world: Any
) -> None:
    _hatched(researcher)
    researcher.post(f"{lead_url(world)}/turns", json={"kind": "greeting", "stage": "brief"})
    assert len(researcher.get(lead_url(world)).json()["turns"]) == 1
    assert viewer.get(lead_url(world)).json()["turns"] == []


def test_off_the_conversation_reads_and_takes_no_message(
    app: FastAPI, researcher: TestClient, world: Any
) -> None:
    app.state.settings = app.state.settings.model_copy(update={"ai_research_lead_enabled": False})
    _hatched(researcher)
    state = researcher.get(lead_url(world)).json()
    assert (state["available"], state["unavailable_reason"]) == (False, "research_lead_disabled")
    refused = researcher.post(
        f"{lead_url(world)}/turns", json={"kind": "greeting", "stage": "brief"}
    )
    assert refused.status_code == 409 and refused.json()["code"] == "research_lead_unavailable"


@pytest.mark.parametrize(
    "body,code",
    [
        ({"kind": "message", "stage": "brief", "text": "x", "client_id": "CLI-x"}, None),
        ({"kind": "message", "stage": "brief", "text": "x" * 4001}, None),
        ({"kind": "shout", "stage": "brief"}, None),
        ({"kind": "message", "stage": "nowhere", "text": "x"}, "invalid_lead_turn"),
        ({"kind": "greeting", "stage": "brief", "text": "x"}, "invalid_lead_turn"),
        (
            {"kind": "greeting", "stage": "brief", "focus": {"id": "question:q1", "label": "x"}},
            "invalid_lead_turn",
        ),
        # The focus id reaches the model unclassified: an element's identifier, nothing else.
        *(
            (
                {
                    "kind": "message",
                    "stage": "brief",
                    "text": "x",
                    "focus": {"id": i, "label": "x"},
                },
                "invalid_lead_turn",
            )
            for i in (
                "question:Acme chystá zdražení o deset procent",
                "question:q1 a tajný plán",
                "note:q1",
                "question:",
                "question:" + "q" * 81,
            )
        ),
    ],
)
def test_an_invalid_turn_is_422(
    researcher: TestClient, world: Any, body: dict[str, Any], code: str | None
) -> None:
    _hatched(researcher)
    refused = researcher.post(f"{lead_url(world)}/turns", json=body)
    assert refused.status_code == 422
    if code:
        assert refused.json()["code"] == code


@pytest.mark.parametrize(
    "focus_id",
    ["question:Q_1", "question:q-3.2", "section:B1", "brief:decision_use", "plan:narrative"],
)
def test_every_focus_the_web_names_is_accepted(
    researcher: TestClient, world: Any, app: FastAPI, focus_id: str
) -> None:
    """The forms lib/lead.ts targetOfElement produces."""
    _hatched(researcher)
    _save_content(app, world)
    posted = researcher.post(
        f"{lead_url(world)}/turns",
        json={"kind": "message", "stage": "brief", "text": "x", "focus": {"id": focus_id}},
    )
    assert posted.status_code == 201, posted.text


def test_another_organizations_study_is_404(app: FastAPI, researcher: TestClient) -> None:
    with create_session_factory(app.state.engine)() as session:
        scopes = ScopeRepository(session)
        org, owner = scopes.create_organization(
            slug="other-org", name="Other", owner_email="boss@other.example"
        )
        admin = ScopeResolver(session).organization_context(
            AuthenticatedPrincipal(user_id=owner.user_id, organization_id=org.organization_id)
        )
        client = scopes.create_client(admin, slug="theirs", name="Theirs")
        study = scopes.create_study(admin, client_id=client.client_id, slug="s", name="S")
        session.commit()
    url = f"/api/v1/studies/{study.study_id}/lead"
    assert researcher.get(url).status_code == 404
    assert (
        researcher.post(f"{url}/turns", json={"kind": "greeting", "stage": "brief"}).status_code
        == 404
    )


def test_every_lead_route_is_study_scoped_or_the_callers_own(app: FastAPI) -> None:
    paths = {path for path in app.openapi()["paths"] if "/lead" in path}
    assert paths == {
        "/api/v1/studies/{study_id}/lead",
        "/api/v1/studies/{study_id}/lead/turns",
        "/api/v1/studies/{study_id}/lead/turns/{turn_id}/edits",
        "/api/v1/studies/{study_id}/lead/turns/{turn_id}/request",
        "/api/v1/studies/{study_id}/lead/turns/{turn_id}/self-update",
        "/api/v1/lead",
        "/api/v1/lead/preferences",
    }


# --------------------------------------------------------------------------- decisions

EDITS = {
    "reply": "Navrhuji změny.",
    "edits": [
        {"op": "set_text", "field": "title", "value": "Nový název", "why": WHY},
        {"op": "question_remove", "question_id": "q404", "why": WHY},
    ],
}


def test_edits_are_decided_on_the_server_and_once(
    researcher: TestClient, world: Any, app: FastAPI
) -> None:
    turn_id = _turn(researcher, world, app, EDITS)
    url = f"{lead_url(world)}/turns/{turn_id}/edits"
    stale = researcher.post(url, json={"decision": "accept", "indices": [0], "base_revision": 9})
    assert stale.status_code == 409 and stale.json()["code"] == "stale_revision"
    assert stale.json()["details"]["current_revision"] == 1

    decided = researcher.post(
        url, json={"decision": "accept", "indices": [0, 1], "base_revision": 1}
    )
    assert decided.status_code == 200, decided.text
    assert decided.json() == {
        "workspace_revision": 2,
        "results": [
            {"index": 0, "status": "accepted", "reason": None},
            {"index": 1, "status": "refused", "reason": "unknown_question"},
        ],
    }
    again = researcher.post(url, json={"decision": "dismiss", "indices": [0]})
    assert again.json()["results"] == [{"index": 0, "status": "accepted", "reason": None}]
    lead = researcher.get(lead_url(world)).json()["turns"][-1]
    assert lead["edit_decisions"] == {"0": {"status": "accepted", "reason": None, "auto": False}}
    assert researcher.post(url, json={"decision": "accept", "indices": []}).status_code == 422


def test_a_sample_size_is_accepted_only_within_the_readiness_limits_in_force(
    researcher: TestClient, world: Any, app: FastAPI
) -> None:
    """RQC9: the Lead's set_n is held to the readiness limits at its accept, the same limits
    a run start checks (20-10,000 under the preset), and refused outside them -- never
    clamped to the nearest bound."""
    turn_id = _turn(
        researcher,
        world,
        app,
        {
            "reply": "Navrhuji jiný vzorek.",
            "edits": [
                {"op": "set_n", "value": 10_001, "why": WHY},
                {"op": "set_n", "value": 19, "why": WHY},
                {"op": "set_n", "value": 10_000, "why": WHY},
            ],
        },
    )
    url = f"{lead_url(world)}/turns/{turn_id}/edits"
    decided = researcher.post(
        url, json={"decision": "accept", "indices": [0, 1, 2], "base_revision": 1}
    )
    assert decided.status_code == 200, decided.text
    assert decided.json()["results"] == [
        {"index": 0, "status": "refused", "reason": "sample_size_out_of_range"},
        {"index": 1, "status": "refused", "reason": "sample_size_out_of_range"},
        {"index": 2, "status": "accepted", "reason": None},
    ]
    content = researcher.get(f"/api/v1/studies/{world.study_id()}/workspace/content").json()
    assert content["content"]["n"] == 10_000


TEXT_AND_STRUCTURE = {
    "reply": "Navrhuji změny.",
    "edits": [
        {"op": "set_text", "field": "title", "value": "Nový název", "why": WHY},
        {"op": "question_edit", "question_id": "q1", "text": "Znáte značku?", "why": WHY},
        {"op": "question_add", "text": "Kolik?", "qtype": "otevrena", "why": WHY},
        {"op": "set_n", "value": 400, "why": WHY},
    ],
}


def test_the_preference_is_the_researchers_own_off_by_default_and_audited(
    researcher: TestClient, viewer: TestClient, app: FastAPI, world: Any
) -> None:
    url = "/api/v1/lead/preferences"
    assert researcher.put(url, json={"auto_accept_text_edits": True}).status_code == 409
    _hatched(researcher)
    _hatched(viewer)
    on = researcher.put(url, json={"auto_accept_text_edits": True})
    assert on.status_code == 200, on.text
    assert on.json()["lead"]["preferences"] == {"auto_accept_text_edits": True}
    assert researcher.get("/api/v1/lead").json()["lead"]["preferences"]["auto_accept_text_edits"]
    # Another researcher's Lead is untouched: the route takes no user, the scope says whose.
    assert not viewer.get("/api/v1/lead").json()["lead"]["preferences"]["auto_accept_text_edits"]
    assert researcher.put(url, json={"auto_accept_text_edits": True}).status_code == 200
    assert researcher.put(url, json={"auto_accept_text_edits": "yes"}).status_code == 422
    with create_session_factory(app.state.engine)() as session:
        audits = session.scalars(
            select(AccessAuditRow).where(AccessAuditRow.action == "RESEARCH_LEAD_PREFERENCES_SET")
        ).all()
    # Set once; the unchanged second set wrote nothing.
    assert [(a.actor_id, a.payload["auto_accept_text_edits"]) for a in audits] == [
        (world.users["researcher"], True)
    ]


def test_an_automatic_accept_takes_text_edits_only_and_says_so_in_the_ledger(
    researcher: TestClient, world: Any, app: FastAPI
) -> None:
    turn_id = _turn(researcher, world, app, TEXT_AND_STRUCTURE)
    url = f"{lead_url(world)}/turns/{turn_id}/edits"
    body = {"decision": "accept", "indices": [0, 1, 2, 3], "base_revision": 1, "auto": True}
    # Off by default: the server does not take the screen's word for the choice.
    off = researcher.post(url, json=body)
    assert off.status_code == 422 and off.json()["code"] == "auto_accept_off"
    on = researcher.put("/api/v1/lead/preferences", json={"auto_accept_text_edits": True})
    assert on.status_code == 200
    dismiss = researcher.post(url, json={**body, "decision": "dismiss"})
    assert dismiss.status_code == 422 and dismiss.json()["code"] == "invalid_decision"

    decided = researcher.post(url, json=body)
    assert decided.status_code == 200, decided.text
    assert decided.json() == {
        "workspace_revision": 2,
        "results": [
            {"index": 0, "status": "accepted", "reason": None},
            {"index": 1, "status": "accepted", "reason": None},
            {"index": 2, "status": "refused", "reason": "not_a_text_edit"},
            {"index": 3, "status": "refused", "reason": "not_a_text_edit"},
        ],
    }
    turn = researcher.get(lead_url(world)).json()["turns"][-1]
    assert turn["edit_decisions"] == {
        "0": {"status": "accepted", "reason": None, "auto": True},
        "1": {"status": "accepted", "reason": None, "auto": True},
    }
    # The structural edits wait for a click, which is no automatic accept.
    clicked = researcher.post(
        url, json={"decision": "accept", "indices": [2, 3], "base_revision": 2}
    )
    assert [r["status"] for r in clicked.json()["results"]] == ["accepted", "accepted"]
    with create_session_factory(app.state.engine)() as session:
        rows = session.scalars(
            select(ApprovalDecisionRow)
            .where(ApprovalDecisionRow.subject_type == "lead_edit")
            .order_by(ApprovalDecisionRow.decision_id)
        ).all()
        comments = {r.subject_id: json.loads(r.comment or "{}") for r in rows}
    assert comments[f"{turn_id}:0"]["auto"] is True
    assert comments[f"{turn_id}:1"]["auto"] is True
    assert "auto" not in comments[f"{turn_id}:2"] and "auto" not in comments[f"{turn_id}:3"]
    saved = researcher.get(f"/api/v1/studies/{world.study_id()}/workspace/content").json()
    assert saved["content"]["title"] == "Nový název"


def test_an_automatic_accept_leaves_a_save_made_while_the_lead_worked_and_says_why(
    researcher: TestClient, world: Any, app: FastAPI
) -> None:
    """The turn was written from revision 1; the person saved revision 2 while it ran. An
    automatic accept would put the Lead's title over theirs without a click: it is refused by
    name and nothing is written, so the edits wait for one."""
    _hatched(researcher)
    assert (
        researcher.put(
            "/api/v1/lead/preferences", json={"auto_accept_text_edits": True}
        ).status_code
        == 200
    )
    _save_content(app, world)
    posted = researcher.post(
        f"{lead_url(world)}/turns", json={"kind": "message", "stage": "brief", "text": "Co dál?"}
    )
    assert posted.status_code == 201, posted.text
    turn_id = str(posted.json()["turns"][-1]["turn_id"])
    content_url = f"/api/v1/studies/{world.study_id()}/workspace/content"
    mine = researcher.put(
        content_url, json={"content": {**CONTENT, "title": "Můj název"}, "base_revision": 1}
    )
    assert mine.status_code == 200, mine.text
    _complete(app, world, TEXT_AND_STRUCTURE)

    url = f"{lead_url(world)}/turns/{turn_id}/edits"
    auto = researcher.post(
        url, json={"decision": "accept", "indices": [0, 1], "base_revision": 2, "auto": True}
    )
    assert auto.status_code == 409 and auto.json()["code"] == "stale_turn", auto.text
    assert auto.json()["details"]["current_revision"] == 2
    saved = researcher.get(content_url).json()
    assert saved["revision"] == 2 and saved["content"]["title"] == "Můj název"
    assert researcher.get(lead_url(world)).json()["turns"][-1]["edit_decisions"] == {}
    # A click is the person's own decision, made over what they now see.
    clicked = researcher.post(url, json={"decision": "accept", "indices": [0], "base_revision": 2})
    assert clicked.status_code == 200
    assert clicked.json()["results"] == [{"index": 0, "status": "accepted", "reason": None}]


def test_a_greeting_on_a_new_study_does_not_make_the_persons_first_save_stale(
    researcher: TestClient, world: Any, app: FastAPI
) -> None:
    """The product owner's report of 2026-10-21: a brand-new study, the Lead's greeting on
    opening it, two sentences typed into Zadání -- "Uloženo jinde". The greeting needs a Design
    Revision, and a study with no working copy has its template saved as revision 1 for it
    (``submit_as_working_copy``), behind the browser, which loaded the study EMPTY and saves
    its first change from no revision. That copy is the template the browser started from
    too: nobody's work is in it, so the first save is not stale. The turn names the revision
    its context was frozen from, so its text edits can be accepted automatically."""
    _hatched(researcher)
    assert (
        researcher.put(
            "/api/v1/lead/preferences", json={"auto_accept_text_edits": True}
        ).status_code
        == 200
    )
    content_url = f"/api/v1/studies/{world.study_id()}/workspace/content"
    assert researcher.get(content_url).json()["state"] == "EMPTY"
    greeted = researcher.post(
        f"{lead_url(world)}/turns", json={"kind": "greeting", "stage": "brief"}
    )
    assert greeted.status_code == 201, greeted.text
    (turn,) = greeted.json()["turns"]
    behind = researcher.get(content_url).json()
    assert behind["revision"] == 1
    assert turn["workspace_revision"] == 1

    typed = {**CONTENT, "title": "Dvě věty v zadání."}
    mine = researcher.put(content_url, json={"content": typed, "base_revision": None})
    assert mine.status_code == 200, mine.text
    assert mine.json()["revision"] == 2
    assert researcher.get(content_url).json()["content"]["title"] == "Dvě věty v zadání."

    # Once a person's work is in the copy, a save from no revision is stale again.
    again = researcher.put(content_url, json={"content": CONTENT, "base_revision": None})
    assert again.status_code == 409 and again.json()["code"] == "stale_revision"
    assert again.json()["details"]["current_revision"] == 2


def test_a_greeting_on_a_new_study_has_its_text_edits_accepted_automatically(
    researcher: TestClient, world: Any, app: FastAPI
) -> None:
    """The browser still holds the EMPTY copy (no revision) when the greeting answers; the
    turn was frozen from the template revision saved for it, so its wording is taken."""
    _hatched(researcher)
    researcher.put("/api/v1/lead/preferences", json={"auto_accept_text_edits": True})
    greeted = researcher.post(
        f"{lead_url(world)}/turns", json={"kind": "greeting", "stage": "brief"}
    )
    turn_id = str(greeted.json()["turns"][-1]["turn_id"])
    _complete(app, world, TEXT_AND_STRUCTURE)
    auto = researcher.post(
        f"{lead_url(world)}/turns/{turn_id}/edits",
        json={"decision": "accept", "indices": [0], "base_revision": None, "auto": True},
    )
    assert auto.status_code == 200, auto.text
    assert auto.json() == {
        "workspace_revision": 2,
        "results": [{"index": 0, "status": "accepted", "reason": None}],
    }


def test_someone_elses_turn_is_not_found(
    researcher: TestClient, viewer: TestClient, world: Any, app: FastAPI
) -> None:
    turn_id = _turn(researcher, world, app, EDITS)
    _hatched(viewer)
    refused = viewer.post(
        f"{lead_url(world)}/turns/{turn_id}/edits", json={"decision": "dismiss", "indices": [0]}
    )
    assert refused.status_code == 404 and refused.json()["code"] == "lead_turn_not_found"


def test_the_generic_run_routes_never_serve_a_lead_turn(
    researcher: TestClient, reviewer: TestClient, world: Any, app: FastAPI
) -> None:
    """A Lead turn's run sits in the Study's design project, where any member's generic run
    routes would read it: its reply, notes and pending changes. Only ``/lead`` serves it."""
    _hatched(researcher)
    _save_content(app, world)
    posted = researcher.post(
        f"{lead_url(world)}/turns", json={"kind": "message", "stage": "brief", "text": "Co dál?"}
    )
    assert posted.status_code == 201, posted.text
    run_id = posted.json()["turns"][-1]["run_id"]
    secret = {"reply": "Tajná odpověď", "self_update": {"soul": "Klient X: tajné"}}
    with create_session_factory(app.state.engine)() as session:
        scope = _scope(app, world, session)
        workflows = WorkflowRepository(session, scope)
        work = workflows.claim_next(worker_id="w", kinds={RESEARCH_LEAD_TURN})
        assert work is not None
        project_id = workflows.get_run(run_id)["project_id"]
        artifacts = research_artifacts(session, scope, app.state.artifact_store)
        common: dict[str, Any] = {
            "project_id": project_id,
            "revision": work.project_revision,
            "stage_type": work.stage_type,
            "runtime_version": "",
        }
        # Found by its type, and by the run that produced it whatever its type says.
        by_type, _ = artifacts.put_json(
            payload={"result": secret},
            artifact_type=ARTIFACT_TYPE,
            input_fingerprint="lead-a",
            produced_by_job_id=work.attempt_id,
            **common,
        )
        by_run, _ = artifacts.put_json(
            payload={"result": secret},
            artifact_type="something_else",
            input_fingerprint="lead-b",
            produced_by_job_id=work.attempt_id,
            **common,
        )
        workflows.complete_attempt(
            work.attempt_id,
            worker_id="w",
            output={
                "lead_output": secret,
                "dropped": [],
                "self_update_applied": None,
                "self_update_pending": {"soul": "Klient X: tajné"},
                "artifact_id": by_type.artifact_id,
            },
        )
        session.commit()

    base = f"/api/v1/studies/{world.study_id()}/projects/{project_id}"
    for client in (reviewer, researcher):
        listed = client.get(f"{base}/runs")
        assert listed.status_code == 200
        assert run_id not in {r["run_id"] for r in listed.json()["items"]}
        for path in (f"runs/{run_id}", f"runs/{run_id}/events"):
            got = client.get(f"{base}/{path}")
            assert got.status_code == 404 and got.json()["code"] == "run_not_found", path
        for artifact in (by_type, by_run):
            got = client.get(f"{base}/artifacts/{artifact.artifact_id}")
            assert got.status_code == 404 and got.json()["code"] == "artifact_not_found"
    # The owner reads the turn where it is served; the other member's conversation is empty.
    assert researcher.get(lead_url(world)).json()["turns"][-1]["output"] == secret
    _hatched(reviewer)
    assert reviewer.get(lead_url(world)).json()["turns"] == []


def test_a_prepared_job_is_approved_under_the_spend_limit_once(
    researcher: TestClient, world: Any, app: FastAPI
) -> None:
    job = {
        "reply": "Připraveno.",
        "request": {"kind": "agent_job", "action": "analyze_brief", "why": WHY},
    }
    turn_id = _turn(researcher, world, app, job)
    with create_session_factory(app.state.engine)() as session:
        ScopeRepository(session).set_study_spend_confirm(_scope(app, world, session), 1.0)
        session.commit()
    url = f"{lead_url(world)}/turns/{turn_id}/request"
    asked = researcher.post(url, json={})
    assert asked.status_code == 409 and asked.json()["code"] == "cost_confirmation_required"
    assert asked.json()["details"] == {"ceiling_usd": 2.0, "limit_usd": 1.0}
    approved = researcher.post(url, json={"confirm_cost_usd": 2.0})
    assert approved.status_code == 200, approved.text
    body = approved.json()
    assert body["run_id"].startswith("RUN-") and body["design_revision_id"].startswith("REV-")
    assert researcher.post(url, json={"confirm_cost_usd": 2.0}).json()["run_id"] == body["run_id"]
    lead = researcher.get(lead_url(world)).json()["turns"][-1]
    assert lead["request_decision"] == {"status": "approved", "run_id": body["run_id"]}


@pytest.mark.parametrize("bad", [-1.0, 1_000_001.0, "Infinity", "NaN", "-Infinity"])
def test_a_confirmation_outside_its_bound_or_not_finite_is_refused(
    researcher: TestClient, world: Any, app: FastAPI, bad: Any
) -> None:
    """The same bound the run and job confirmations take (0 to 1,000,000 USD), and no
    non-finite number: ``Infinity`` would otherwise cover any ceiling."""
    job = {
        "reply": "Připraveno.",
        "request": {"kind": "agent_job", "action": "analyze_brief", "why": WHY},
    }
    turn_id = _turn(researcher, world, app, job)
    raw = f'{{"confirm_cost_usd": {bad}}}'
    refused = researcher.post(
        f"{lead_url(world)}/turns/{turn_id}/request",
        content=raw,
        headers={"content-type": "application/json"},
    )
    assert refused.status_code == 422, refused.text


def test_a_request_that_only_opens_a_stage_is_not_a_paid_request(
    researcher: TestClient, world: Any, app: FastAPI
) -> None:
    run = {"reply": "Spusťte běh.", "request": {"kind": "research_run", "why": WHY}}
    turn_id = _turn(researcher, world, app, run)
    refused = researcher.post(f"{lead_url(world)}/turns/{turn_id}/request", json={})
    assert refused.status_code == 422 and refused.json()["code"] == "not_a_paid_request"


def test_without_a_reservation_a_limited_study_does_not_start_the_job(
    app: FastAPI, researcher: TestClient, world: Any
) -> None:
    app.state.settings = app.state.settings.model_copy(update={"ai_research_reservation_usd": None})
    job = {
        "reply": "Připraveno.",
        "request": {"kind": "agent_job", "action": "build_questionnaire", "why": WHY},
    }
    turn_id = _turn(researcher, world, app, job)
    with create_session_factory(app.state.engine)() as session:
        ScopeRepository(session).set_study_spend_confirm(_scope(app, world, session), 1.0)
        session.commit()
    refused = researcher.post(f"{lead_url(world)}/turns/{turn_id}/request", json={})
    assert refused.status_code == 409 and refused.json()["code"] == "cost_ceiling_unknown"


def test_what_the_lead_wants_to_keep_everywhere_waits_for_the_researcher(
    researcher: TestClient, viewer: TestClient, world: Any, app: FastAPI
) -> None:
    """Codex P1 on #484: a personal note is decided by the researcher, once, never by the
    model's choice of scope."""
    waiting = {"remember": [{"scope": "personal", "text": "Chce tabulky."}]}
    _hatched(researcher)
    _save_content(app, world)
    posted = researcher.post(
        f"{lead_url(world)}/turns", json={"kind": "message", "stage": "brief", "text": "Pamatuj"}
    )
    turn_id = posted.json()["turns"][-1]["turn_id"]
    _complete(
        app,
        world,
        {"reply": "Zapamatuji si to.", "self_update": waiting},
        self_update_pending=waiting,
        self_update_waiting={
            "name": None,
            "soul": None,
            "user": None,
            "remember": ["Chce tabulky."],
            "forget": [],
        },
    )
    lead = researcher.get(lead_url(world)).json()["turns"][-1]
    assert (lead["self_update_pending"], lead["self_update_decision"]) == (True, None)
    assert lead["self_update_waiting"]["remember"] == ["Chce tabulky."]
    assert "pending_self_update" not in lead
    assert researcher.get("/api/v1/lead").json()["lead"]["memories"] == []

    url = f"{lead_url(world)}/turns/{turn_id}/self-update"
    _hatched(viewer)
    assert viewer.post(url, json={"decision": "accept"}).status_code == 404
    assert researcher.post(url, json={"decision": "maybe"}).status_code == 422
    accepted = researcher.post(url, json={"decision": "accept"})
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["status"] == "accepted"
    assert len(accepted.json()["changes"]["remembered"]) == 1
    memories = researcher.get("/api/v1/lead").json()["lead"]["memories"]
    assert [(m["scope"], m["text"]) for m in memories] == [("personal", "Chce tabulky.")]
    again = researcher.post(url, json={"decision": "dismiss"})
    assert again.status_code == 409 and again.json()["code"] == "lead_self_update_decided"
    lead = researcher.get(lead_url(world)).json()["turns"][-1]
    assert (lead["self_update_pending"], lead["self_update_decision"]) == (
        False,
        {"status": "accepted", "stale": []},
    )


def _soul_turn(client: TestClient, world: Any, app: FastAPI, soul: str) -> str:
    """A completed turn whose Lead wants ``soul``, with the files it saw when it was posted."""
    files = client.get("/api/v1/lead").json()["lead"]
    seen = {"name": files["name"], "soul": files["files"]["soul"], "user": files["files"]["user"]}
    posted = client.post(
        f"{lead_url(world)}/turns", json={"kind": "message", "stage": "brief", "text": "Změň se"}
    )
    assert posted.status_code == 201, posted.text
    waiting = {"soul": soul, "remember": [{"scope": "personal", "text": f"Pozn. {soul}"}]}
    _complete(
        app,
        world,
        {"reply": "Upravím se.", "self_update": waiting},
        self_update_pending=waiting,
        self_update_base=seen,
    )
    return str(posted.json()["turns"][-1]["turn_id"])


def test_an_older_soul_change_never_overwrites_a_newer_one(
    researcher: TestClient, world: Any, app: FastAPI
) -> None:
    """The review of baac33d5: accepting T2 and then T1 silently put T1's SOUL back."""
    _hatched(researcher)
    _save_content(app, world)
    first = _soul_turn(researcher, world, app, "# SOUL první")
    second = _soul_turn(researcher, world, app, "# SOUL druhý")

    def decide(turn_id: str) -> Any:
        url = f"{lead_url(world)}/turns/{turn_id}/self-update"
        return researcher.post(url, json={"decision": "accept"})

    newer = decide(second)
    assert newer.status_code == 200 and newer.json()["stale"] == []
    stale = decide(first)
    # Still an accept: its note applied. The SOUL it would have put back is named, not written.
    assert stale.status_code == 200, stale.text
    assert stale.json()["status"] == "accepted" and stale.json()["stale"] == ["soul"]
    assert stale.json()["changes"]["soul"] is False
    assert len(stale.json()["changes"]["remembered"]) == 1
    lead = researcher.get("/api/v1/lead").json()["lead"]
    assert lead["files"]["soul"] == "# SOUL druhý"
    # Notes have no base: the older turn's note still applied, and its decision is recorded.
    assert {m["text"] for m in lead["memories"]} == {"Pozn. # SOUL první", "Pozn. # SOUL druhý"}
    turns = {t["turn_id"]: t for t in researcher.get(lead_url(world)).json()["turns"]}
    assert turns[first]["self_update_decision"] == {"status": "accepted", "stale": ["soul"]}
    assert turns[first]["self_update_pending"] is False
    assert "self_update_base" not in turns[first]
    again = decide(first)
    assert again.status_code == 409 and again.json()["code"] == "lead_self_update_decided"


# --------------------------------------------------------------------------- the study's budget


def test_setting_the_study_budget_sends_the_message_that_waited_for_it(
    researcher: TestClient, world: Any, app: FastAPI
) -> None:
    """F4 and the product owner's Q39 (2026-10-21): the message that parked for lack of budget
    is sent once a person sets the budget in Nastavení -> Studie, and the ledger names them."""
    budget_url = f"/api/v1/studies/{world.study_id()}/budget"
    assert researcher.put(budget_url, json={"budget_usd": 0.0}).status_code == 200
    _hatched(researcher)
    posted = researcher.post(
        f"{lead_url(world)}/turns", json={"kind": "message", "stage": "brief", "text": "Jsi tam?"}
    )
    assert posted.status_code == 201, posted.text
    run_id = posted.json()["turns"][-1]["run_id"]
    with create_session_factory(app.state.engine)() as session:
        workflows = WorkflowRepository(session, _scope(app, world, session))
        work = workflows.claim_next(worker_id="w", kinds={RESEARCH_LEAD_TURN})
        assert work is not None
        workflows.fail_attempt(
            work.attempt_id,
            worker_id="w",
            failure=FailureClass.BUDGET_EXCEEDED,
            error={"requested_usd": 0.5, "remaining_usd": 0.0, "budget_usd": 0.0},
        )
        session.commit()
    lead = researcher.get(lead_url(world)).json()
    assert (lead["turns"][-1]["status"], lead["turns"][-1]["reason"]) == (
        "WAITING",
        "budget_exceeded",
    )
    assert lead["busy"] is False

    assert researcher.put(budget_url, json={"budget_usd": 5.0}).status_code == 200
    lead = researcher.get(lead_url(world)).json()
    assert lead["turns"][-1]["status"] == "QUEUED" and lead["busy"] is True
    with create_session_factory(app.state.engine)() as session:
        rows = session.scalars(
            select(ApprovalDecisionRow).where(ApprovalDecisionRow.run_id == run_id)
        ).all()
        assert [(r.gate_type, r.decision, r.approver_user_id) for r in rows] == [
            ("budget", "lift", world.users["researcher"])
        ]


# --------------------------------------------------------------------------- the switch off (27b)


def _written_by_an_approval(app: FastAPI) -> int:
    """What approving a Lead job writes: the job's run, its ledger rows and any budget hold."""
    with create_session_factory(app.state.engine)() as session:
        runs = session.scalars(
            select(WorkflowRunRow).where(WorkflowRunRow.workflow_type == RESEARCH_AGENT)
        ).all()
        approvals = session.scalars(
            select(ApprovalDecisionRow).where(
                ApprovalDecisionRow.subject_type == ApprovalSubject.LEAD_JOB_REQUEST
            )
        ).all()
        holds = session.scalars(select(BudgetReservationRow)).all()
        return len(runs) + len(approvals) + len(holds)


JOB = {
    "reply": "Připraveno.",
    "request": {"kind": "agent_job", "action": "analyze_brief", "why": WHY},
}


def test_a_card_the_lead_prepared_waits_while_the_lead_is_switched_off(
    researcher: TestClient, world: Any, app: FastAPI
) -> None:
    """Q42 (D22): approved after a switch-off, a card the Lead's model prepared is 409
    research_lead_disabled and nothing is written -- no run, no ledger row, no hold -- and it
    is approvable once the Lead is on again."""
    turn_id = _turn(researcher, world, app, JOB)
    before = _written_by_an_approval(app)
    app.state.settings = app.state.settings.model_copy(update={"ai_research_lead_enabled": False})
    url = f"{lead_url(world)}/turns/{turn_id}/request"
    refused = researcher.post(url, json={})
    assert refused.status_code == 409, refused.text
    assert refused.json()["code"] == "research_lead_disabled"
    assert _written_by_an_approval(app) == before
    assert researcher.get(lead_url(world)).json()["turns"][-1]["request_decision"] is None

    app.state.settings = app.state.settings.model_copy(update={"ai_research_lead_enabled": True})
    approved = researcher.post(url, json={})
    assert approved.status_code == 200, approved.text
    assert _written_by_an_approval(app) > before


def test_a_card_approved_before_the_switch_off_still_answers_with_its_job(
    researcher: TestClient, world: Any, app: FastAPI
) -> None:
    """Review of #561: an approval asked again after the switch-off (a lost response, a second
    tab) returns the job that already runs, and writes nothing; only an approval that would
    create a job is refused."""
    turn_id = _turn(researcher, world, app, JOB)
    url = f"{lead_url(world)}/turns/{turn_id}/request"
    approved = researcher.post(url, json={})
    assert approved.status_code == 200, approved.text
    written = _written_by_an_approval(app)
    app.state.settings = app.state.settings.model_copy(update={"ai_research_lead_enabled": False})
    again = researcher.post(url, json={})
    assert again.status_code == 200, again.text
    assert again.json()["run_id"] == approved.json()["run_id"]
    assert _written_by_an_approval(app) == written


def test_the_refusal_is_read_from_the_stored_turn_never_the_body(
    researcher: TestClient, world: Any, app: FastAPI
) -> None:
    """The card's kind comes from the stored turn: a body naming an origin is refused at
    validation, and the switch's refusal holds whatever the body confirms."""
    turn_id = _turn(researcher, world, app, JOB)
    app.state.settings = app.state.settings.model_copy(update={"ai_research_lead_enabled": False})
    url = f"{lead_url(world)}/turns/{turn_id}/request"
    assert researcher.post(url, json={"origin": "chat_start"}).status_code == 422
    refused = researcher.post(url, json={"confirm_cost_usd": 5.0})
    assert refused.status_code == 409 and refused.json()["code"] == "research_lead_disabled"


def test_stored_edits_are_still_decided_while_the_lead_is_switched_off(
    researcher: TestClient, world: Any, app: FastAPI
) -> None:
    """Q42: accepting or dismissing stored edits calls no model and spends nothing."""
    turn_id = _turn(researcher, world, app, EDITS)
    app.state.settings = app.state.settings.model_copy(update={"ai_research_lead_enabled": False})
    url = f"{lead_url(world)}/turns/{turn_id}/edits"
    accepted = researcher.post(url, json={"decision": "accept", "indices": [0], "base_revision": 1})
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["results"][0]["status"] == "accepted"
    dismissed = researcher.post(url, json={"decision": "dismiss", "indices": [1]})
    assert dismissed.status_code == 200, dismissed.text
    assert dismissed.json()["results"][0]["status"] == "dismissed"


def _park(app: FastAPI, world: Any, *, reason: str) -> None:
    with create_session_factory(app.state.engine)() as session:
        workflows = WorkflowRepository(session, _scope(app, world, session))
        work = workflows.claim_next(worker_id="w", kinds={RESEARCH_LEAD_TURN})
        assert work is not None
        workflows.fail_attempt(
            work.attempt_id,
            worker_id="w",
            failure=FailureClass.RUNTIME_UNAVAILABLE,
            error={"reason": reason, "message": "x"},
        )
        session.commit()


def test_the_worker_is_never_reported_ready_without_a_source(
    researcher: TestClient, world: Any, app: FastAPI
) -> None:
    """27b: with the API's switch on, ``available`` is true, but nothing the API holds shows a
    worker that can answer: ``worker_ready`` is null, never true -- before any turn and after
    one completed."""
    _hatched(researcher)
    state = researcher.get(lead_url(world)).json()
    assert state["available"] is True
    assert (state["worker_ready"], state["worker_ready_source"], state["worker_reason"]) == (
        None,
        None,
        None,
    )
    posted = researcher.post(
        f"{lead_url(world)}/turns", json={"kind": "message", "stage": "brief", "text": "Ahoj"}
    )
    assert posted.status_code == 201, posted.text
    _complete(app, world, {"reply": "Dobrý den."})
    state = researcher.get(lead_url(world)).json()
    assert state["turns"][-1]["status"] == "COMPLETED"
    assert (state["worker_ready"], state["worker_ready_source"], state["worker_reason"]) == (
        None,
        None,
        None,
    )


@pytest.mark.parametrize("reason", ["research_lead_unconfigured", "ai_runtime_unavailable"])
def test_a_worker_that_cannot_answer_is_reported_not_ready(
    researcher: TestClient, world: Any, app: FastAPI, reason: str
) -> None:
    """27b: the API's switch on and the worker's off (or its keys unset, or no runtime): the
    turn parks for the worker's composition, and GET /lead says the worker is not ready and
    where it read that. A later turn the worker answers makes it unknown again."""
    _hatched(researcher)
    _save_content(app, world)
    posted = researcher.post(
        f"{lead_url(world)}/turns", json={"kind": "message", "stage": "brief", "text": "Jsi tam?"}
    )
    assert posted.status_code == 201, posted.text
    _park(app, world, reason=reason)
    state = researcher.get(lead_url(world)).json()
    assert state["available"] is True
    assert (state["turns"][-1]["status"], state["turns"][-1]["reason"]) == ("WAITING", reason)
    assert (state["worker_ready"], state["worker_ready_source"], state["worker_reason"]) == (
        False,
        "newest_turn",
        reason,
    )

    again = researcher.post(
        f"{lead_url(world)}/turns", json={"kind": "message", "stage": "brief", "text": "A teď?"}
    )
    assert again.status_code == 201, again.text
    _complete(app, world, {"reply": "Ano."})
    state = researcher.get(lead_url(world)).json()
    assert (state["worker_ready"], state["worker_ready_source"], state["worker_reason"]) == (
        None,
        None,
        None,
    )
