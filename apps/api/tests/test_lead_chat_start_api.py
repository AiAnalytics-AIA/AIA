"""A person's typed start in the Lead's composer, over HTTP (lead-orchestration LO5).

The server matches the command by code (``domain/lead_commands.py``) and stores it on the
person's own turn; no model is in the path, so the card is theirs, approvable while the Lead is
switched off (Q43), while a card the Lead's model prepared is refused then (Q42, D22). Approval
follows LO1's order: quote (the wallet, when on), create the run, write ``chat_start`` naming it,
charge it.
"""

from __future__ import annotations

import json
from typing import Any

import pytest
from aia_core.application.scope import AuthenticatedPrincipal, ScopeResolver
from aia_core.application.wallet import StudyWallets
from aia_core.domain.approval_ledger import ApprovalSubject
from aia_core.domain.money import WalletVerdict
from aia_core.domain.workflow_templates import (
    RESEARCH,
    RESEARCH_AGENT,
    RESEARCH_LEAD,
    RESEARCH_LEAD_TURN,
)
from aia_core.infrastructure.db import create_session_factory
from aia_core.infrastructure.scope_repository import ScopeRepository
from aia_core.infrastructure.study_workspace_repository import StudyWorkspaceRepository
from aia_core.infrastructure.tables import (
    ApprovalDecisionRow,
    StudyWalletChargeRow,
    WorkflowRunRow,
)
from aia_core.infrastructure.workflow_repository import WorkflowRepository
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select

from aia_api.config import Settings

#: Runnable: 450 respondents, seven closed items in one block (test_research_spend_api).
DESIGN: dict[str, Any] = {
    "title": "Ranní nápoj",
    "goal": "Zjistit, zda nový nápoj dává smysl dojíždějícím.",
    "n": 450,
    "sections": [
        {
            "id": "s1",
            "type": "questions",
            "questions": [
                {"id": "q1", "text": "Jak často pijete kávu?", "typ": "skala", "skala": [1, 5]},
                {
                    "id": "q2",
                    "text": "Co si ráno koupíte?",
                    "typ": "vyber",
                    "kategorie": ["Kávu", "Čaj", "Nic"],
                },
            ],
        },
    ],
}
JOB_RESERVATION = 2.0
WHY = "Zadání to potřebuje."


@pytest.fixture
def settings(settings: Settings) -> Settings:
    return settings.model_copy(
        update={
            "ai_research_lead_enabled": False,
            "ai_research_reservation_usd": JOB_RESERVATION,
            "ai_fieldwork_reservation_usd": 0.5,
        }
    )


def _lead(world: Any) -> str:
    return f"/api/v1/studies/{world.study_id()}/lead"


def _scope(world: Any, session: Any) -> Any:
    return ScopeResolver(session).study_context(
        AuthenticatedPrincipal(
            user_id=world.users["researcher"], organization_id=world.organization_id
        ),
        study_id=world.study_id(),
    )


def _save(app: FastAPI, world: Any, content: dict[str, Any] = DESIGN) -> None:
    with create_session_factory(app.state.engine)() as session:
        repo = StudyWorkspaceRepository(session)
        scope = _scope(world, session)
        repo.save(scope, content=content, base_revision=repo.content(scope).revision)
        session.commit()


def _type(client: TestClient, world: Any, text: str) -> Any:
    return client.post(
        f"{_lead(world)}/turns", json={"kind": "message", "stage": "brief", "text": text}
    )


def _approve(client: TestClient, world: Any, turn_id: str, **body: Any) -> Any:
    return client.post(f"{_lead(world)}/turns/{turn_id}/request", json=body)


def _written(app: FastAPI) -> dict[str, int]:
    """Every row an approval may write: the jobs' and runs' rows, the chat_start rows, the
    wallet's charges."""
    with create_session_factory(app.state.engine)() as session:
        runs = session.scalars(
            select(WorkflowRunRow.workflow_type).where(
                WorkflowRunRow.workflow_type.in_((RESEARCH_AGENT, RESEARCH))
            )
        ).all()
        starts = session.scalars(
            select(ApprovalDecisionRow).where(
                ApprovalDecisionRow.subject_type == ApprovalSubject.CHAT_START
            )
        ).all()
        charges = session.scalars(select(StudyWalletChargeRow)).all()
        return {"runs": len(runs), "chat_start": len(starts), "charges": len(charges)}


def _chat_starts(app: FastAPI) -> list[ApprovalDecisionRow]:
    with create_session_factory(app.state.engine)() as session:
        rows = session.scalars(
            select(ApprovalDecisionRow).where(
                ApprovalDecisionRow.subject_type == ApprovalSubject.CHAT_START
            )
        ).all()
        session.expunge_all()
        return list(rows)


def _lead_runs(app: FastAPI) -> int:
    with create_session_factory(app.state.engine)() as session:
        return len(
            session.scalars(
                select(WorkflowRunRow).where(WorkflowRunRow.workflow_type == RESEARCH_LEAD)
            ).all()
        )


# --------------------------------------------------------------------------- the command


def test_with_the_lead_off_a_typed_command_is_taken_and_free_text_is_not(
    researcher: TestClient, world: Any, app: FastAPI
) -> None:
    """Q43: the composer takes the typed start with the Lead off -- stored as the person's
    command, no Lead turn, no run -- while free text is refused with the disabled notice."""
    _save(app, world)
    refused = _type(researcher, world, "Co mám udělat dál?")
    assert refused.status_code == 409 and refused.json()["code"] == "research_lead_unavailable"

    typed = _type(researcher, world, "Analyzuj zadání")
    assert typed.status_code == 201, typed.text
    (turn,) = typed.json()["turns"]
    assert (turn["actor"], turn["command"], turn["text"]) == (
        "person",
        "agent_job:analyze_brief",
        "Analyzuj zadání",
    )
    assert turn["request_decision"] is None
    assert _lead_runs(app) == 0 and _written(app)["runs"] == 0
    # No hatched Lead is needed for a command: the person's own card, not a conversation.
    state = researcher.get(_lead(world)).json()
    assert [t["command"] for t in state["turns"]] == ["agent_job:analyze_brief"]


def test_with_the_lead_on_a_typed_command_is_not_sent_to_the_model(
    app: FastAPI, researcher: TestClient, world: Any
) -> None:
    """The model is never in the path of a typed start: nothing is queued for the Lead."""
    app.state.settings = app.state.settings.model_copy(update={"ai_research_lead_enabled": True})
    assert researcher.post("/api/v1/lead").status_code == 201
    _save(app, world)
    typed = _type(researcher, world, "/Navrhni dotazník: krátce, do deseti otázek.")
    assert typed.status_code == 201, typed.text
    assert [t["actor"] for t in typed.json()["turns"]] == ["person"]
    assert typed.json()["turns"][0]["command"] == "agent_job:build_questionnaire"
    assert _lead_runs(app) == 0


def test_a_near_match_is_a_message_never_a_start(
    app: FastAPI, researcher: TestClient, world: Any
) -> None:
    app.state.settings = app.state.settings.model_copy(update={"ai_research_lead_enabled": True})
    assert researcher.post("/api/v1/lead").status_code == 201
    _save(app, world)
    posted = _type(researcher, world, "Prosím spusť výzkum")
    assert posted.status_code == 201, posted.text
    person, lead = posted.json()["turns"]
    assert person["command"] is None and lead["actor"] == "lead"


def test_the_conversation_lists_the_commands_it_takes(researcher: TestClient, world: Any) -> None:
    """The composer's vocabulary comes from the server, the fixture's exactly, Lead on or off."""
    from pathlib import Path

    fixture = json.loads(
        (
            Path(__file__).resolve().parents[3]
            / "packages/aia_core/tests/fixtures/lead_commands/commands.json"
        ).read_text("utf-8")
    )
    state = researcher.get(_lead(world)).json()
    assert state["available"] is False
    assert state["commands"] == fixture["commands"]


# --------------------------------------------------------------------------- the approval


def test_a_typed_design_job_starts_with_the_lead_off_and_writes_chat_start_once(
    researcher: TestClient, world: Any, app: FastAPI
) -> None:
    _save(app, world)
    turn_id = _type(researcher, world, "Navrhni dotazník: krátce").json()["turns"][0]["turn_id"]
    approved = _approve(researcher, world, turn_id)
    assert approved.status_code == 200, approved.text
    run_id = approved.json()["run_id"]
    assert approved.json()["design_revision_id"].startswith("REV-")

    (row,) = _chat_starts(app)
    assert (row.subject_id, row.run_id, row.decision, row.gate_type) == (
        run_id,
        run_id,
        "start",
        "chat_start",
    )
    assert row.approver_user_id == world.users["researcher"]
    assert json.loads(row.comment) == {
        "turn_id": turn_id,
        "start": "agent_job:build_questionnaire",
        "ceiling_usd": JOB_RESERVATION,
        "design_revision_id": approved.json()["design_revision_id"],
    }
    with create_session_factory(app.state.engine)() as session:
        job = WorkflowRepository(session, _scope(world, session)).get_run(run_id)
        assert job["workflow_type"] == RESEARCH_AGENT
    jobs = researcher.get(f"/api/v1/studies/{world.study_id()}/research/agent-jobs").json()
    assert [j["run_id"] for j in jobs] == [run_id], jobs

    again = _approve(researcher, world, turn_id)
    assert again.status_code == 200 and again.json()["run_id"] == run_id
    assert _written(app)["chat_start"] == 1
    turn = researcher.get(_lead(world)).json()["turns"][-1]
    assert turn["request_decision"] == {"status": "approved", "run_id": run_id, "reused": False}


@pytest.mark.parametrize("wallet", [False, True])
def test_a_typed_start_approved_on_a_job_already_started_decides_its_card_and_starts_nothing(
    researcher: TestClient, world: Any, app: FastAPI, wallet: bool
) -> None:
    """The same command typed again on the same design finds the job the first approval started.
    Its card is decided (it never asks again after a reload) and says the job was found; nothing
    starts or is charged, and its row names the run in its comment only, so the second approval
    is neither a start approval of that run (spend attribution) nor a charge authority. With the
    wallet on, its cap is exactly one job: the found job is not held to the wallet again, which
    the first charge has used up (review of #682)."""
    if wallet:
        _wallet_on(app, researcher, world, cap=JOB_RESERVATION)
    _save(app, world)
    first = _type(researcher, world, "Zkontroluj návrh").json()["turns"][0]["turn_id"]
    run_id = _approve(researcher, world, first).json()["run_id"]
    second = _type(researcher, world, "Zkontroluj návrh").json()["turns"][0]["turn_id"]
    again = _approve(researcher, world, second)
    assert again.status_code == 200, again.text
    assert again.json()["run_id"] == run_id

    turns = {t["turn_id"]: t for t in researcher.get(_lead(world)).json()["turns"]}
    assert turns[first]["request_decision"] == {
        "status": "approved",
        "run_id": run_id,
        "reused": False,
    }
    assert turns[second]["request_decision"] == {
        "status": "approved",
        "run_id": run_id,
        "reused": True,
    }
    started, reused = _chat_starts(app)
    assert (started.run_id, started.decision) == (run_id, "start")
    assert (reused.subject_id, reused.run_id, reused.decision) == (run_id, None, "reuse")
    assert json.loads(reused.comment)["turn_id"] == second
    assert json.loads(reused.comment)["run_id"] == run_id
    assert _written(app) == {"runs": 1, "chat_start": 2, "charges": 1 if wallet else 0}
    # Asked once more, the card answers as decided and writes nothing further.
    assert _approve(researcher, world, second).json()["run_id"] == run_id
    assert _written(app)["chat_start"] == 2


def test_a_typed_start_found_already_started_asks_no_confirmation(
    researcher: TestClient, world: Any, app: FastAPI
) -> None:
    """With the wallet on, at or above the study's confirmation threshold the first approval
    asks and is confirmed; the second finds the job and asks nothing, since nothing will be
    charged (review of #682)."""
    _wallet_on(app, researcher, world, cap=5.0)
    _save(app, world)
    with create_session_factory(app.state.engine)() as session:
        ScopeRepository(session).set_study_spend_confirm(_scope(world, session), 1.0)
        session.commit()
    first = _type(researcher, world, "Zkontroluj návrh").json()["turns"][0]["turn_id"]
    asked = _approve(researcher, world, first)
    assert asked.status_code == 409 and asked.json()["code"] == "cost_confirmation_required"
    run_id = _approve(researcher, world, first, confirm_cost_usd=JOB_RESERVATION).json()["run_id"]
    second = _type(researcher, world, "Zkontroluj návrh").json()["turns"][0]["turn_id"]
    again = _approve(researcher, world, second)
    assert again.status_code == 200, again.text
    assert again.json()["run_id"] == run_id
    assert [r.decision for r in _chat_starts(app)] == ["start", "reuse"]


RUN_CEILING = 450 * 0.5  # the typed research run's ceiling at the test reservations


def _run_wallet(app: FastAPI, client: TestClient, world: Any, cap: float) -> None:
    """The wallet on, with the study's budget large enough for the cap."""
    app.state.settings = app.state.settings.model_copy(update={"study_wallet_enabled": True})
    study = f"/api/v1/studies/{world.study_id()}"
    assert client.put(f"{study}/budget", json={"budget_usd": cap}).status_code == 200
    set_cap = client.put(f"{study}/wallet", json={"cap_usd": cap})
    assert set_cap.status_code == 200, set_cap.text


def test_a_typed_research_run_found_already_started_is_not_held_to_a_used_up_wallet(
    researcher: TestClient, world: Any, app: FastAPI
) -> None:
    """The run branch (review of #682): a wallet of exactly one run's ceiling, used up by the
    first approval's charge, does not refuse the second approval of the same run; it answers
    with the run, decides the card by a reuse row, and charges nothing more."""
    _run_wallet(app, researcher, world, cap=RUN_CEILING)
    _save(app, world)
    first = _type(researcher, world, "Spusť výzkum").json()["turns"][0]["turn_id"]
    started = _approve(researcher, world, first)
    assert started.status_code == 200, started.text
    second = _type(researcher, world, "Spusť výzkum").json()["turns"][0]["turn_id"]
    again = _approve(researcher, world, second)
    assert again.status_code == 200, again.text
    assert again.json()["run_id"] == started.json()["run_id"]
    assert [r.decision for r in _chat_starts(app)] == ["start", "reuse"]
    assert _written(app) == {"runs": 1, "chat_start": 2, "charges": 1}


def test_a_typed_research_run_found_already_started_asks_no_confirmation(
    researcher: TestClient, world: Any, app: FastAPI
) -> None:
    """The run branch at the threshold: the first approval asks and is confirmed; the second
    finds the run and asks nothing (review of #682)."""
    _run_wallet(app, researcher, world, cap=2 * RUN_CEILING)
    _save(app, world)
    with create_session_factory(app.state.engine)() as session:
        ScopeRepository(session).set_study_spend_confirm(_scope(world, session), 1.0)
        session.commit()
    first = _type(researcher, world, "Spusť výzkum").json()["turns"][0]["turn_id"]
    asked = _approve(researcher, world, first)
    assert asked.status_code == 409 and asked.json()["code"] == "cost_confirmation_required"
    ceiling = asked.json()["details"]["ceiling_usd"]
    run_id = _approve(researcher, world, first, confirm_cost_usd=ceiling).json()["run_id"]
    second = _type(researcher, world, "Spusť výzkum").json()["turns"][0]["turn_id"]
    again = _approve(researcher, world, second)
    assert again.status_code == 200, again.text
    assert again.json()["run_id"] == run_id
    assert [r.decision for r in _chat_starts(app)] == ["start", "reuse"]


def test_in_one_switched_off_state_the_typed_card_starts_and_the_models_card_waits(
    app: FastAPI, researcher: TestClient, world: Any
) -> None:
    """D22: the guard tells the two kinds of card apart from the stored turn. With the Lead
    off, a card its model prepared is 409 research_lead_disabled; the person's typed card is
    approved and writes chat_start."""
    app.state.settings = app.state.settings.model_copy(update={"ai_research_lead_enabled": True})
    assert researcher.post("/api/v1/lead").status_code == 201
    _save(app, world)
    posted = _type(researcher, world, "Co dál?")
    assert posted.status_code == 201, posted.text
    lead_turn = posted.json()["turns"][-1]["turn_id"]
    with create_session_factory(app.state.engine)() as session:
        workflows = WorkflowRepository(session, _scope(world, session))
        work = workflows.claim_next(worker_id="w", kinds={RESEARCH_LEAD_TURN})
        assert work is not None
        workflows.complete_attempt(
            work.attempt_id,
            worker_id="w",
            output={
                "lead_output": {
                    "reply": "Připraveno.",
                    "request": {"kind": "agent_job", "action": "analyze_brief", "why": WHY},
                },
                "dropped": [],
                "self_update_applied": None,
            },
        )
        session.commit()
    typed = _type(researcher, world, "Zkontroluj návrh").json()["turns"][0]["turn_id"]

    app.state.settings = app.state.settings.model_copy(update={"ai_research_lead_enabled": False})
    refused = _approve(researcher, world, lead_turn)
    assert refused.status_code == 409 and refused.json()["code"] == "research_lead_disabled"
    approved = _approve(researcher, world, typed)
    assert approved.status_code == 200, approved.text
    assert [r.run_id for r in _chat_starts(app)] == [approved.json()["run_id"]]


def test_the_threshold_asks_a_typed_start_as_it_asks_every_start(
    researcher: TestClient, world: Any, app: FastAPI
) -> None:
    """LO15's rule holds on the typed path: at the threshold the server's ceiling is asked
    for, and once confirmed the job's spend row and the chat_start row are both written."""
    _save(app, world)
    with create_session_factory(app.state.engine)() as session:
        ScopeRepository(session).set_study_spend_confirm(_scope(world, session), 1.0)
        session.commit()
    turn_id = _type(researcher, world, "Analyzuj zadání").json()["turns"][0]["turn_id"]
    asked = _approve(researcher, world, turn_id)
    assert asked.status_code == 409 and asked.json()["code"] == "cost_confirmation_required"
    assert asked.json()["details"] == {"ceiling_usd": JOB_RESERVATION, "limit_usd": 1.0}
    assert _written(app) == {"runs": 0, "chat_start": 0, "charges": 0}
    approved = _approve(researcher, world, turn_id, confirm_cost_usd=JOB_RESERVATION)
    assert approved.status_code == 200, approved.text
    with create_session_factory(app.state.engine)() as session:
        spend = session.scalars(
            select(ApprovalDecisionRow).where(
                ApprovalDecisionRow.subject_type == ApprovalSubject.SPEND
            )
        ).all()
        assert [r.run_id for r in spend] == [approved.json()["run_id"]]
    assert _written(app)["chat_start"] == 1


def test_a_typed_research_run_starts_on_the_deployments_run_settings(
    researcher: TestClient, world: Any, app: FastAPI
) -> None:
    _save(app, world)
    turn_id = _type(researcher, world, "Spusť výzkum").json()["turns"][0]["turn_id"]
    approved = _approve(researcher, world, turn_id)
    assert approved.status_code == 200, approved.text
    run_id = approved.json()["run_id"]
    runs = researcher.get(f"/api/v1/studies/{world.study_id()}/research/runs").json()
    assert [r["run_id"] for r in runs["items"]] == [run_id]
    (row,) = _chat_starts(app)
    comment = json.loads(row.comment)
    assert (row.run_id, comment["start"]) == (run_id, "research_run")
    assert comment["ceiling_usd"] == pytest.approx(450 * 0.5)
    # The run's own start: the same revision asked again returns it and starts nothing. The
    # second card is decided by a reuse row, which names the run in its comment only: the run
    # still has one start approval.
    again = _type(researcher, world, "Spusť výzkum").json()["turns"][0]["turn_id"]
    second = _approve(researcher, world, again)
    assert second.status_code == 200 and second.json()["run_id"] == run_id
    assert [(r.run_id, r.decision) for r in _chat_starts(app)] == [
        (run_id, "start"),
        (None, "reuse"),
    ]
    assert _written(app)["runs"] == 1


def test_a_typed_run_on_a_design_that_is_not_ready_is_refused_by_the_runs_own_rule(
    researcher: TestClient, world: Any, app: FastAPI
) -> None:
    _save(app, world, {"title": "Prázdné", "sections": []})
    turn_id = _type(researcher, world, "Spusť výzkum").json()["turns"][0]["turn_id"]
    refused = _approve(researcher, world, turn_id)
    assert refused.status_code in (409, 422), refused.text
    assert _written(app) == {"runs": 0, "chat_start": 0, "charges": 0}


def test_someone_elses_typed_card_is_not_found(
    researcher: TestClient, reviewer: TestClient, world: Any, app: FastAPI
) -> None:
    _save(app, world)
    turn_id = _type(researcher, world, "Analyzuj zadání").json()["turns"][0]["turn_id"]
    other = _approve(reviewer, world, turn_id)
    assert other.status_code == 404, other.text
    assert _written(app)["runs"] == 0


# --------------------------------------------------------------------------- the analysis retry


def _analysed_run(app: FastAPI, client: TestClient, world: Any) -> str:
    """A research run that ran analysis, started by its typed start (still queued: no worker)."""
    app.state.settings = app.state.settings.model_copy(update={"ai_analysis_enabled": True})
    _save(app, world)
    turn_id = _type(client, world, "Spusť výzkum").json()["turns"][0]["turn_id"]
    approved = _approve(client, world, turn_id)
    assert approved.status_code == 200, approved.text
    return str(approved.json()["run_id"])


def test_a_typed_analysis_retry_with_no_analysed_run_is_refused_by_name(
    researcher: TestClient, world: Any, app: FastAPI
) -> None:
    turn = _type(researcher, world, "Zopakuj analýzu").json()["turns"][0]
    assert turn["command"] == "analysis_retry"
    refused = _approve(researcher, world, turn["turn_id"])
    assert refused.status_code == 409, refused.text
    assert refused.json()["code"] == "analysis_not_retryable"
    # Named as the study's, not a run's: there is no run to speak of.
    assert refused.json()["details"]["reason"] == "no_analysed_run"
    assert "Studie zatím nemá" in refused.json()["message"]
    assert _written(app) == {"runs": 0, "chat_start": 0, "charges": 0}


def test_a_typed_analysis_retry_of_a_run_still_going_is_refused_as_the_stage_route_is(
    researcher: TestClient, world: Any, app: FastAPI
) -> None:
    run_id = _analysed_run(app, researcher, world)
    turn_id = _type(researcher, world, "Zopakuj analýzu").json()["turns"][0]["turn_id"]
    refused = _approve(researcher, world, turn_id)
    assert refused.status_code == 409, refused.text
    assert refused.json()["details"]["reason"] == "run_not_finished"
    # The stage's own route answers the same run the same way: one rule for both starts.
    stage = researcher.post(
        f"/api/v1/studies/{world.study_id()}/research/runs/{run_id}/analysis/retry"
    )
    assert stage.json()["details"]["reason"] == refused.json()["details"]["reason"]
    assert _written(app) == {"runs": 1, "chat_start": 1, "charges": 0}


def test_a_typed_analysis_retry_starts_the_stage_retry_on_the_newest_analysed_run(
    researcher: TestClient, world: Any, app: FastAPI, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Through the stage route's own start (retry_failed_modules), on the newest run that ran
    analysis, with the confirmation passed on; recorded as chat_start, never charged to the
    wallet (the product manager's decision (b), 2026-10-22; F-LO1-1 decides both starts)."""
    from aia_core.application import lead_chat_start
    from aia_core.application.workflows import StartedRun

    run_id = _analysed_run(app, researcher, world)
    _wallet_on(app, researcher, world, cap=50.0)
    charges_before = _written(app)["charges"]
    asked: list[dict[str, Any]] = []

    def stage_retry(session: Any, scope: Any, store: Any, **kw: Any) -> StartedRun:
        asked.append(kw)
        run = WorkflowRepository(session, scope).get_run(kw["run_id"])
        return StartedRun(
            run_id=run["run_id"],
            project_id=run["project_id"],
            project_revision=run["project_revision"],
            workflow_type=RESEARCH,
            created=True,
            run=run,
        )

    monkeypatch.setattr(lead_chat_start, "retry_failed_modules", stage_retry)
    turn_id = _type(researcher, world, "Zopakuj analýzu").json()["turns"][0]["turn_id"]
    approved = _approve(researcher, world, turn_id, confirm_cost_usd=3.0)
    assert approved.status_code == 200, approved.text
    assert [(a["run_id"], a["confirm_cost_usd"]) for a in asked] == [(run_id, 3.0)]
    retry_row = _chat_starts(app)[-1]
    comment = json.loads(retry_row.comment)
    assert (comment["start"], comment["turn_id"], comment["ceiling_usd"]) == (
        "analysis_retry",
        turn_id,
        None,
    )
    assert _written(app)["charges"] == charges_before


def test_a_typed_analysis_retry_names_its_run_and_never_retries_a_newer_one_unasked(
    researcher: TestClient, world: Any, app: FastAPI, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The card names the run it retries (GET /lead ``analysis_retry_run``); approved with that
    run while a newer one has run analysis since, it is refused by name and nothing starts, and
    the newer one starts only once the person names it (the PM on #744, 2026-10-22)."""
    from aia_core.application import lead_chat_start
    from aia_core.application.workflows import StartedRun

    first = _analysed_run(app, researcher, world)
    state = researcher.get(_lead(world)).json()
    assert state["analysis_retry_run"]["run_id"] == first
    assert state["wallet_enabled"] is False
    turn_id = _type(researcher, world, "Zopakuj analýzu").json()["turns"][0]["turn_id"]
    # A newer run on a changed design runs analysis before the card is approved.
    _save(app, world, {**DESIGN, "title": "Ranní nápoj 2"})
    newer = _approve(
        researcher, world, _type(researcher, world, "Spusť výzkum").json()["turns"][0]["turn_id"]
    ).json()["run_id"]
    assert newer != first
    written = _written(app)
    moved = _approve(researcher, world, turn_id, retry_run_id=first)
    assert moved.status_code == 409, moved.text
    assert moved.json()["code"] == "analysis_retry_target_moved"
    assert moved.json()["details"]["current_run_id"] == newer
    assert _written(app) == written
    asked: list[str] = []

    def stage_retry(session: Any, scope: Any, store: Any, **kw: Any) -> StartedRun:
        asked.append(kw["run_id"])
        run = WorkflowRepository(session, scope).get_run(kw["run_id"])
        return StartedRun(
            run_id=run["run_id"],
            project_id=run["project_id"],
            project_revision=run["project_revision"],
            workflow_type=RESEARCH,
            created=True,
            run=run,
        )

    monkeypatch.setattr(lead_chat_start, "retry_failed_modules", stage_retry)
    named = _approve(researcher, world, turn_id, retry_run_id=newer)
    assert named.status_code == 200, named.text
    assert asked == [newer]


def test_the_conversation_says_whether_the_wallet_is_on(
    researcher: TestClient, world: Any, app: FastAPI
) -> None:
    assert researcher.get(_lead(world)).json()["wallet_enabled"] is False
    assert researcher.get(_lead(world)).json()["analysis_retry_run"] is None
    _wallet_on(app, researcher, world, cap=5.0)
    assert researcher.get(_lead(world)).json()["wallet_enabled"] is True


# --------------------------------------------------------------------------- the wallet


def _wallet_on(app: FastAPI, client: TestClient, world: Any, cap: float | None) -> None:
    app.state.settings = app.state.settings.model_copy(update={"study_wallet_enabled": True})
    study = f"/api/v1/studies/{world.study_id()}"
    assert client.put(f"{study}/budget", json={"budget_usd": 100.0}).status_code == 200
    if cap is not None:
        set_cap = client.put(f"{study}/wallet", json={"cap_usd": cap})
        assert set_cap.status_code == 200, set_cap.text


def test_with_the_wallet_on_a_typed_start_is_charged_under_its_chat_start_row(
    researcher: TestClient, world: Any, app: FastAPI
) -> None:
    _wallet_on(app, researcher, world, cap=5.0)
    _save(app, world)
    turn_id = _type(researcher, world, "Analyzuj zadání").json()["turns"][0]["turn_id"]
    approved = _approve(researcher, world, turn_id)
    assert approved.status_code == 200, approved.text
    (row,) = _chat_starts(app)
    with create_session_factory(app.state.engine)() as session:
        (charge,) = session.scalars(select(StudyWalletChargeRow)).all()
        assert (charge.run_id, charge.kind, charge.ceiling_usd, charge.approval_decision_id) == (
            approved.json()["run_id"],
            "agent_job",
            JOB_RESERVATION,
            row.decision_id,
        )
    assert _approve(researcher, world, turn_id).json()["run_id"] == approved.json()["run_id"]
    assert _written(app) == {"runs": 1, "chat_start": 1, "charges": 1}


@pytest.mark.parametrize("cap", [None, 1.0])
def test_outside_the_wallet_a_typed_start_writes_nothing(
    researcher: TestClient, world: Any, app: FastAPI, cap: float | None
) -> None:
    """No wallet, or one whose remainder is below the job's ceiling: 409 outside_wallet, and no
    run, no chat_start row, no charge."""
    _wallet_on(app, researcher, world, cap=cap)
    _save(app, world)
    turn_id = _type(researcher, world, "Analyzuj zadání").json()["turns"][0]["turn_id"]
    refused = _approve(researcher, world, turn_id)
    assert refused.status_code == 409 and refused.json()["code"] == "outside_wallet", refused.text
    assert refused.json()["details"]["ceiling_usd"] == JOB_RESERVATION
    assert _written(app) == {"runs": 0, "chat_start": 0, "charges": 0}


def test_an_unknown_ceiling_is_refused_never_charged_as_zero(
    researcher: TestClient, world: Any, app: FastAPI
) -> None:
    _wallet_on(app, researcher, world, cap=5.0)
    app.state.settings = app.state.settings.model_copy(update={"ai_research_reservation_usd": None})
    _save(app, world)
    turn_id = _type(researcher, world, "Analyzuj zadání").json()["turns"][0]["turn_id"]
    refused = _approve(researcher, world, turn_id)
    assert refused.status_code == 409 and refused.json()["code"] == "ceiling_unknown"
    assert _written(app) == {"runs": 0, "chat_start": 0, "charges": 0}


def test_a_charge_refused_after_the_create_leaves_no_run_no_row_and_no_charge(
    researcher: TestClient, world: Any, app: FastAPI, monkeypatch: pytest.MonkeyPatch
) -> None:
    """LO1's order: the charge names the run created in the same transaction, so a charge
    refused after the create (another start took the wallet meanwhile) rolls the run and its
    chat_start row back with it."""
    _wallet_on(app, researcher, world, cap=1.0)
    _save(app, world)
    # The quote is told the start fits; the charge, under the same lock, finds it does not.
    monkeypatch.setattr(StudyWallets, "quote", lambda self, ceiling: (WalletVerdict.FITS, 10.0))
    turn_id = _type(researcher, world, "Analyzuj zadání").json()["turns"][0]["turn_id"]
    refused = _approve(researcher, world, turn_id)
    assert refused.status_code == 409 and refused.json()["code"] == "outside_wallet", refused.text
    assert _written(app) == {"runs": 0, "chat_start": 0, "charges": 0}
