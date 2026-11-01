"""A person's typed Deep Research start, stop and retry, over HTTP (lead-orchestration LO5a.3).

"Spusť rešerši k návrhu", "Spusť rešerši výsledků" (each "rychlou" for QUICK), "Zopakuj rešerši"
and "Zastav rešerši" are matched by code and stored as the person's command; no model is in the
path, so they are approvable with the Lead off (Q43). Approval freezes once, quotes, holds the
ceiling to the wallet when it is on, creates the run, writes ``chat_start`` naming it and charges
it at the ceiling the run pinned (LO1's order). An Interpretation start's target is never read from
the text: the person approves a candidate id from the server's code-built list, rebuilt when the
card is approved. The same card approved twice is decided once, by its ``chat_start`` row under the
conversation's lock, never by timing. No Deep Research runtime runs, so nothing is sent.
"""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import timedelta
from pathlib import Path
from typing import Any

import pytest
from aia_core.application.deep_research import DeepResearchRuns
from aia_core.application.scope import AuthenticatedPrincipal, ScopeResolver
from aia_core.domain.approval_ledger import ApprovalSubject
from aia_core.domain.deep_research.workflow import DEEP_RESEARCH
from aia_core.domain.edit_log import ActorKind, OpSource, WriteBy
from aia_core.domain.fieldwork import FieldworkSource
from aia_core.infrastructure.build_identity import BuildIdentity
from aia_core.infrastructure.db import create_session_factory
from aia_core.infrastructure.scope_repository import ScopeRepository
from aia_core.infrastructure.study_workspace_repository import StudyWorkspaceRepository
from aia_core.infrastructure.tables import (
    ApprovalDecisionRow,
    StudyWalletChargeRow,
    WorkflowRunRow,
)
from aia_executors import workbench
from aia_worker.settings import WorkerSettings
from aia_worker.worker import Worker
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select

from aia_api.config import Settings

API = "/api/v1"
DESIGN: dict[str, Any] = {
    "title": "Ranní nápoj",
    "goal": "Zjistit, zda nový nápoj dává smysl dojíždějícím.",
    "n": 450,
    "research_plan": {"research_questions": ["Co dojíždějící ráno pijí?"]},
    "sections": [
        {
            "type": "questions",
            "questions": [
                {"id": "q1", "text": "Jak často pijete kávu?", "typ": "skala", "skala": [1, 5]},
            ],
        },
        {
            "type": "object_battery",
            "title": "Nápoje",
            "object_family": "nápoje",
            "objects": ["Káva", "Čaj", "Kakao"],
            "object_question": "Jak hodnotíte {object}?",
            "scale": [1, 10],
        },
    ],
}


@pytest.fixture
def settings(settings: Settings, tmp_path: Path) -> Settings:
    """A file-backed database (a worker runs the research steps), fictional fieldwork, the
    route's prices, and the Lead off: a typed start needs no model."""
    update: dict[str, Any] = {
        "bedrock_input_usd_per_mtok": 3.0,
        "bedrock_output_usd_per_mtok": 15.0,
        "bedrock_context_window_tokens": 200_000,
        "ai_research_max_output_tokens": 8_192,
        "research_fieldwork_source": FieldworkSource.SYNTHETIC_FIXTURE,
        "ai_research_lead_enabled": False,
        "ai_research_reservation_usd": 2.0,
    }
    if not settings.database_url or ":memory:" in settings.database_url:
        update["database_url"] = f"sqlite+pysqlite:///{tmp_path / 'api.db'}"
    return settings.model_copy(update=update)


def _study(world: Any) -> str:
    return f"{API}/studies/{world.study_id()}"


def _scope(world: Any, session: Any) -> Any:
    return ScopeResolver(session).study_context(
        AuthenticatedPrincipal(
            user_id=world.users["researcher"], organization_id=world.organization_id
        ),
        study_id=world.study_id(),
    )


def _save(app: FastAPI, world: Any) -> None:
    with create_session_factory(app.state.engine)() as session:
        repo = StudyWorkspaceRepository(session)
        scope = _scope(world, session)
        repo.save(
            scope,
            content=DESIGN,
            base_revision=repo.content(scope).revision,
            by=WriteBy(ActorKind.PERSON, scope.actor_id, OpSource.UI),
        )
        session.commit()


def _typed(client: TestClient, world: Any, text: str) -> str:
    """The person's typed command, stored: its turn id."""
    posted = client.post(
        f"{_study(world)}/lead/turns", json={"kind": "message", "stage": "analysis", "text": text}
    )
    assert posted.status_code == 201, posted.text
    turn = posted.json()["turns"][-1]
    assert turn["actor"] == "person" and turn["command"] is not None
    return str(turn["turn_id"])


def _approve(client: TestClient, world: Any, turn_id: str, **body: Any) -> Any:
    return client.post(f"{_study(world)}/lead/turns/{turn_id}/request", json=body)


def _written(app: FastAPI) -> dict[str, int]:
    with create_session_factory(app.state.engine)() as session:
        runs = session.scalars(
            select(WorkflowRunRow.run_id).where(WorkflowRunRow.workflow_type == DEEP_RESEARCH)
        ).all()
        starts = session.scalars(
            select(ApprovalDecisionRow).where(
                ApprovalDecisionRow.subject_type == ApprovalSubject.CHAT_START
            )
        ).all()
        charges = session.scalars(select(StudyWalletChargeRow)).all()
        return {"runs": len(runs), "chat_start": len(starts), "charges": len(charges)}


def _chat_start(app: FastAPI) -> list[dict[str, Any]]:
    with create_session_factory(app.state.engine)() as session:
        rows = session.scalars(
            select(ApprovalDecisionRow)
            .where(ApprovalDecisionRow.subject_type == ApprovalSubject.CHAT_START)
            .order_by(ApprovalDecisionRow.decision_id)
        ).all()
        return [
            {**json.loads(r.comment or "{}"), "run_id": r.run_id, "decision": r.decision}
            for r in rows
        ]


def _metadata(app: FastAPI, run_id: str) -> dict[str, Any]:
    with create_session_factory(app.state.engine)() as session:
        run = session.get(WorkflowRunRow, run_id)
        assert run is not None
        return dict(run.metadata_json or {})


def _wallet_on(app: FastAPI, client: TestClient, world: Any, cap: float) -> None:
    app.state.settings = app.state.settings.model_copy(update={"study_wallet_enabled": True})
    assert client.put(f"{_study(world)}/budget", json={"budget_usd": 100.0}).status_code == 200
    assert client.put(f"{_study(world)}/wallet", json={"cap_usd": cap}).status_code == 200


def _completed_run(
    app: FastAPI, client: TestClient, world: Any, design: dict[str, Any] = DESIGN
) -> str:
    """A completed run with its analysis, answered by recorded models at zero price: its
    research-questions module is the Interpretation default (Q44)."""
    app.state.settings = app.state.settings.model_copy(update={"ai_analysis_enabled": True})
    revision = world.design(client, design)
    assert revision.status_code == 201, revision.text
    started = client.post(
        f"{_study(world)}/research/runs",
        json={"design_revision_id": revision.json()["revision_id"]},
    )
    assert started.status_code == 201, started.text
    settings = app.state.settings
    build = BuildIdentity(sha="a15be650937aacaa")
    worker = Worker(
        session_factory=create_session_factory(app.state.engine),
        executors=workbench.workbench_registry_for(
            store=app.state.artifact_store,
            build=build,
            analysis=workbench.recorded_analysis(store=app.state.artifact_store, build=build),
        ),
        settings=WorkerSettings(
            database_url=settings.database_url,
            executors="aia_executors.registry:build_registry",
            worker_id="typed-deep-research-worker",
            lease_seconds=30,
            heartbeat_seconds=0.1,
            poll_seconds=0.05,
        ),
    )
    while worker.run_once() is not None:
        pass
    run_id = str(started.json()["run_id"])
    assert client.get(f"{_study(world)}/research/runs/{run_id}").json()["status"] == "COMPLETED"
    return run_id


# --------------------------------------------------------------------------- design


def test_with_the_lead_off_a_typed_design_research_starts_once_under_its_chat_start_row(
    app: FastAPI, researcher: TestClient, world: Any
) -> None:
    _save(app, world)
    turn_id = _typed(researcher, world, "Spusť rešerši k návrhu")
    approved = _approve(researcher, world, turn_id)
    assert approved.status_code == 200, approved.text
    body = approved.json()
    assert body["purpose"] == "DESIGN_RESEARCH" and body["research_run_id"] is None
    run = researcher.get(f"{_study(world)}/deep-research/runs/{body['run_id']}").json()
    assert run["purpose"] == "DESIGN_RESEARCH" and run["preset"] == "STANDARD"
    assert _written(app) == {"runs": 1, "chat_start": 1, "charges": 0}
    (row,) = _chat_start(app)
    assert (row["run_id"], row["decision"], row["start"], row["turn_id"]) == (
        body["run_id"],
        "start",
        "design_research",
        turn_id,
    )
    assert row["design_revision_id"] == body["design_revision_id"]
    assert row["ceiling_usd"] == _metadata(app, body["run_id"])["cost_ceiling_usd"]
    # A double click, or the request retried: the card's chat_start row decides it, the same run.
    again = _approve(researcher, world, turn_id)
    assert again.status_code == 200 and again.json()["run_id"] == body["run_id"]
    assert _written(app) == {"runs": 1, "chat_start": 1, "charges": 0}
    # The typed run is the stage's run: the same spec, found by its idempotency.
    stage = researcher.post(
        f"{_study(world)}/deep-research/runs",
        json={
            "design_revision_id": body["design_revision_id"],
            "preset_name": "STANDARD",
            "channels": ["WEB"],
        },
    )
    assert stage.status_code == 200 and stage.json()["run_id"] == body["run_id"]


def test_rychlou_is_the_quick_preset(app: FastAPI, researcher: TestClient, world: Any) -> None:
    _save(app, world)
    approved = _approve(
        researcher, world, _typed(researcher, world, "Spusť rychlou rešerši k návrhu")
    )
    assert approved.status_code == 200, approved.text
    run = researcher.get(f"{_study(world)}/deep-research/runs/{approved.json()['run_id']}").json()
    assert run["preset"] == "QUICK"
    assert _chat_start(app)[0]["start"] == "design_research_quick"


def test_with_the_wallet_on_a_typed_start_is_charged_its_pinned_ceiling_once(
    app: FastAPI, researcher: TestClient, world: Any
) -> None:
    _save(app, world)
    _wallet_on(app, researcher, world, cap=50.0)
    turn_id = _typed(researcher, world, "Spusť rešerši k návrhu")
    approved = _approve(researcher, world, turn_id)
    assert approved.status_code == 200, approved.text
    _approve(researcher, world, turn_id)
    assert _written(app) == {"runs": 1, "chat_start": 1, "charges": 1}
    with create_session_factory(app.state.engine)() as session:
        charge = session.scalars(select(StudyWalletChargeRow)).one()
        run = session.get(WorkflowRunRow, approved.json()["run_id"])
        assert run is not None
        row = session.scalars(
            select(ApprovalDecisionRow).where(
                ApprovalDecisionRow.subject_type == ApprovalSubject.CHAT_START
            )
        ).one()
        assert (charge.kind, charge.approval_decision_id) == ("deep_research", row.decision_id)
        assert charge.ceiling_usd == run.metadata_json["cost_ceiling_usd"]


def test_outside_the_wallet_a_typed_start_writes_nothing(
    app: FastAPI, researcher: TestClient, world: Any
) -> None:
    _save(app, world)
    _wallet_on(app, researcher, world, cap=0.01)
    refused = _approve(researcher, world, _typed(researcher, world, "Spusť rešerši k návrhu"))
    assert refused.status_code == 409 and refused.json()["code"] == "outside_wallet"
    assert _written(app) == {"runs": 0, "chat_start": 0, "charges": 0}


def test_a_charge_refused_after_the_create_leaves_no_run_no_row_and_no_charge(
    app: FastAPI, researcher: TestClient, world: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """LO1's order: the quote said it fits, the run pinned more than the wallet holds, so the
    charge refuses after the create and the request rolls the run and its row back with it."""
    real_quote = DeepResearchRuns.quote

    def free(self: DeepResearchRuns, *a: Any, **k: Any) -> Any:
        quoted = real_quote(self, *a, **k)
        assert quoted.ceiling is not None
        return replace(quoted, ceiling=replace(quoted.ceiling, total_usd=0.0))

    monkeypatch.setattr(DeepResearchRuns, "quote", free)
    _save(app, world)
    _wallet_on(app, researcher, world, cap=0.01)
    refused = _approve(researcher, world, _typed(researcher, world, "Spusť rešerši k návrhu"))
    assert refused.status_code == 409 and refused.json()["code"] == "outside_wallet"
    assert _written(app) == {"runs": 0, "chat_start": 0, "charges": 0}


def test_the_threshold_asks_a_typed_start_and_its_yes_starts_it(
    app: FastAPI, researcher: TestClient, world: Any
) -> None:
    _save(app, world)
    assert (
        researcher.put(f"{_study(world)}/spend-confirm", json={"limit_usd": 0.01}).status_code
        == 200
    )
    turn_id = _typed(researcher, world, "Spusť rešerši k návrhu")
    asked = _approve(researcher, world, turn_id)
    assert asked.status_code == 409 and asked.json()["code"] == "cost_confirmation_required"
    assert _written(app)["runs"] == 0
    ceiling = asked.json()["details"]["ceiling_usd"]
    yes = _approve(researcher, world, turn_id, confirm_cost_usd=ceiling)
    assert yes.status_code == 200, yes.text
    assert _written(app) == {"runs": 1, "chat_start": 1, "charges": 0}


# --------------------------------------------------------------------------- interpretation


def test_the_conversation_lists_the_interpretation_targets_built_by_code(
    app: FastAPI, researcher: TestClient, world: Any
) -> None:
    nothing = researcher.get(f"{_study(world)}/lead/interpretation-targets").json()
    assert nothing == {"candidates": [], "default": None, "omitted": 0, "unreadable_runs": []}
    run_id = _completed_run(app, researcher, world)
    targets = researcher.get(f"{_study(world)}/lead/interpretation-targets").json()
    assert targets["default"] == "t1"
    first = targets["candidates"][0]
    assert first["id"] == "t1" and first["ref"]["research_run_id"] == run_id
    assert first["ref"]["module_id"] == "research_questions"


def test_a_typed_interpretation_starts_on_the_default_or_a_listed_target_never_another(
    app: FastAPI, researcher: TestClient, world: Any
) -> None:
    run_id = _completed_run(app, researcher, world)
    candidates = researcher.get(f"{_study(world)}/lead/interpretation-targets").json()["candidates"]
    forged_ref = {**candidates[0]["ref"], "research_run_id": "RUN-0123456789abcdef"}
    forged = _approve(
        researcher, world, _typed(researcher, world, "Spusť rešerši výsledků"), target=forged_ref
    )
    assert forged.status_code == 404
    assert _written(app)["runs"] == 0

    default = _approve(researcher, world, _typed(researcher, world, "Spusť rešerši výsledků"))
    assert default.status_code == 200, default.text
    assert default.json()["purpose"] == "INTERPRETATION_RESEARCH"
    assert default.json()["research_run_id"] == run_id
    run = researcher.get(f"{_study(world)}/deep-research/runs/{default.json()['run_id']}").json()
    assert run["target"] == candidates[0]["ref"] and run["preset"] == "STANDARD"

    second = candidates[1]
    chosen = _approve(
        researcher,
        world,
        _typed(researcher, world, "Spusť rychlou rešerši výsledků"),
        target=second["ref"],
    )
    assert chosen.status_code == 200, chosen.text
    run = researcher.get(f"{_study(world)}/deep-research/runs/{chosen.json()['run_id']}").json()
    assert run["target"] == second["ref"] and run["preset"] == "QUICK"
    assert [r["start"] for r in _chat_start(app)] == [
        "interpretation_research",
        "interpretation_research_quick",
    ]


def test_a_chosen_target_stays_the_result_it_named_when_a_newer_run_completes(
    app: FastAPI, researcher: TestClient, world: Any
) -> None:
    """The card sends the candidate's reference, not its position: a run that completes between
    the read and the approval moves "t1" to its own result, never the person's choice (Codex P1
    on #1144)."""
    first_run = _completed_run(app, researcher, world)
    shown = researcher.get(f"{_study(world)}/lead/interpretation-targets").json()["candidates"]
    chosen = shown[0]
    assert chosen["ref"]["research_run_id"] == first_run
    turn_id = _typed(researcher, world, "Spusť rešerši výsledků")
    newer_run = _completed_run(app, researcher, world, {**DESIGN, "title": "Ranní nápoj 2"})
    now = researcher.get(f"{_study(world)}/lead/interpretation-targets").json()["candidates"]
    assert now[0]["ref"]["research_run_id"] == newer_run  # "t1" is the newer run's now
    approved = _approve(researcher, world, turn_id, target=chosen["ref"])
    assert approved.status_code == 200, approved.text
    assert approved.json()["research_run_id"] == first_run
    run = researcher.get(f"{_study(world)}/deep-research/runs/{approved.json()['run_id']}").json()
    assert run["target"] == chosen["ref"]


def test_a_typed_interpretation_with_nothing_to_interpret_is_refused_by_name(
    app: FastAPI, researcher: TestClient, world: Any
) -> None:
    refused = _approve(researcher, world, _typed(researcher, world, "Spusť rešerši výsledků"))
    assert refused.status_code == 409 and refused.json()["code"] == "no_default_target"
    assert _written(app) == {"runs": 0, "chat_start": 0, "charges": 0}


# --------------------------------------------------------------------------- stop and retry


def test_a_typed_stop_cancels_the_running_run_and_charges_nothing(
    app: FastAPI, researcher: TestClient, world: Any
) -> None:
    nothing = _approve(researcher, world, _typed(researcher, world, "Zastav rešerši"))
    assert nothing.status_code == 409 and nothing.json()["code"] == "no_running_deep_research"
    _save(app, world)
    started = _approve(researcher, world, _typed(researcher, world, "Spusť rešerši k návrhu"))
    run_id = started.json()["run_id"]
    shown = researcher.get(f"{_study(world)}/lead").json()["deep_research_stop_run"]
    assert shown["run_id"] == run_id
    turn_id = _typed(researcher, world, "Zastav rešerši")
    stopped = _approve(researcher, world, turn_id, deep_research_run_id=run_id)
    assert stopped.status_code == 200, stopped.text
    assert stopped.json()["run_id"] == run_id
    run = researcher.get(f"{_study(world)}/deep-research/runs/{run_id}").json()
    assert run["status"] == "CANCELLED"
    stop = _chat_start(app)[-1]
    # A stop authorises no spend: its row names the run in its comment, never as a start.
    assert (stop["decision"], stop["run_id"], stop["start"]) == (
        "stop",
        None,
        "deep_research_stop",
    )
    assert _approve(researcher, world, turn_id).json()["run_id"] == run_id
    assert _written(app) == {"runs": 1, "chat_start": 2, "charges": 0}


def _bury(app: FastAPI, run_id: str, status: str, count: int) -> None:
    """``count`` newer Deep Research runs in ``status``, copied from ``run_id``'s row: what a
    study with a long history looks like to the run listing."""
    with create_session_factory(app.state.engine)() as session:
        row = session.get(WorkflowRunRow, run_id)
        assert row is not None
        for i in range(count):
            session.add(
                WorkflowRunRow(
                    run_id=f"RUN-{i:016x}",
                    organization_id=row.organization_id,
                    client_id=row.client_id,
                    study_id=row.study_id,
                    project_id=row.project_id,
                    project_revision=row.project_revision,
                    workflow_type=row.workflow_type,
                    status=status,
                    idempotency_key=f"{row.idempotency_key}:buried:{i}",
                    metadata_json=dict(row.metadata_json),
                    created_at=row.created_at + timedelta(minutes=i + 1),
                    updated_at=row.updated_at + timedelta(minutes=i + 1),
                )
            )
        session.commit()


def test_a_run_behind_fifty_newer_ended_runs_is_still_the_one_a_stop_or_retry_names(
    app: FastAPI, researcher: TestClient, world: Any
) -> None:
    """Eligibility is read in the query, before its limit: 50 newer completed runs never hide
    an older one still running, nor an older cancelled one (Codex P2 on #1144)."""
    _save(app, world)
    started = _approve(researcher, world, _typed(researcher, world, "Spusť rešerši k návrhu"))
    run_id = started.json()["run_id"]
    _bury(app, run_id, "COMPLETED", 50)
    assert (
        researcher.get(f"{_study(world)}/lead").json()["deep_research_stop_run"]["run_id"] == run_id
    )
    stopped = _approve(
        researcher, world, _typed(researcher, world, "Zastav rešerši"), deep_research_run_id=run_id
    )
    assert stopped.status_code == 200, stopped.text
    assert (
        researcher.get(f"{_study(world)}/lead").json()["deep_research_retry_run"]["run_id"]
        == run_id
    )


def test_a_typed_retry_retries_the_run_its_card_named(
    app: FastAPI, researcher: TestClient, world: Any
) -> None:
    nothing = _approve(researcher, world, _typed(researcher, world, "Zopakuj rešerši"))
    assert nothing.status_code == 409 and nothing.json()["code"] == "no_retryable_deep_research"
    _save(app, world)
    first = _approve(researcher, world, _typed(researcher, world, "Spusť rešerši k návrhu")).json()
    assert (
        researcher.post(f"{_study(world)}/deep-research/runs/{first['run_id']}/cancel").status_code
        == 200
    )
    shown = researcher.get(f"{_study(world)}/lead").json()["deep_research_retry_run"]
    assert shown["run_id"] == first["run_id"]
    turn_id = _typed(researcher, world, "Zopakuj rešerši")
    moved = _approve(researcher, world, turn_id, deep_research_run_id="RUN-0123456789abcdef")
    assert moved.status_code == 409 and moved.json()["code"] == "deep_research_retry_target_moved"
    assert moved.json()["details"]["current_run_id"] == first["run_id"]
    retried = _approve(researcher, world, turn_id, deep_research_run_id=first["run_id"])
    assert retried.status_code == 200, retried.text
    assert retried.json()["run_id"] != first["run_id"]
    assert retried.json()["purpose"] == "DESIGN_RESEARCH"
    assert _metadata(app, retried.json()["run_id"])["retry_of"] == first["run_id"]
    assert _chat_start(app)[-1]["start"] == "deep_research_retry"
    assert _approve(researcher, world, turn_id).json()["run_id"] == retried.json()["run_id"]


def _other_organization(app: FastAPI) -> TestClient:
    """The OWNER of a second organization, signed in."""
    with create_session_factory(app.state.engine)() as session:
        ScopeRepository(session).create_organization(
            slug="elsewhere", name="Elsewhere", owner_email="o@elsewhere.example"
        )
        session.commit()
    token = "token-elsewhere-owner"
    app.state.identity_provider.register(
        token, subject="o@elsewhere.example", email="o@elsewhere.example"
    )
    client = TestClient(app)
    client.headers.update({"Authorization": f"Bearer {token}"})
    return client


def test_another_organization_reads_no_targets_and_approves_no_typed_start(
    app: FastAPI, researcher: TestClient, world: Any
) -> None:
    _save(app, world)
    turn_id = _typed(researcher, world, "Spusť rešerši k návrhu")
    theirs = _other_organization(app)
    assert theirs.get(f"{_study(world)}/lead/interpretation-targets").status_code == 404
    assert _approve(theirs, world, turn_id).status_code == 404
    assert _written(app) == {"runs": 0, "chat_start": 0, "charges": 0}
