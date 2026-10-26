"""A Lead card starts Deep Research on the server (lead-orchestration LO5a.2).

``POST …/lead/turns/{turn_id}/request`` on a turn whose request is ``design_research``,
``interpretation_research`` or ``deep_research_retry``: frozen once, priced as the stage's start
is, held to the threshold, the live settings and (with ``AIA_STUDY_WALLET_ENABLED``) the wallet,
recorded once. A worker runs the research executors on fictional fieldwork for the result an
Interpretation card names; no Deep Research runtime runs, so nothing is sent.
"""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
from aia_core.application.deep_research import DeepResearchRuns
from aia_core.application.scope import AuthenticatedPrincipal, ScopeResolver
from aia_core.domain.approval_ledger import ApprovalSubject
from aia_core.domain.deep_research.workflow import DEEP_RESEARCH
from aia_core.domain.edit_log import ActorKind, OpSource, WriteBy
from aia_core.domain.fieldwork import FieldworkSource
from aia_core.domain.item_ids import list_ids, with_item_ids
from aia_core.domain.workflow_templates import RESEARCH_LEAD_TURN
from aia_core.infrastructure.db import create_session_factory
from aia_core.infrastructure.scope_repository import ScopeRepository
from aia_core.infrastructure.study_workspace_repository import StudyWorkspaceRepository
from aia_core.infrastructure.tables import (
    ApprovalDecisionRow,
    BudgetReservationRow,
    ProjectArtifactRow,
    StepRunRow,
    StudyWalletChargeRow,
    WorkflowRunRow,
)
from aia_core.infrastructure.workflow_repository import WorkflowRepository
from aia_worker.settings import WorkerSettings
from aia_worker.worker import Worker
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from aia_api.config import Settings

API = "/api/v1"
WHY = "Výsledek potřebuje kontext."
RQ1 = "Co dojíždějící ráno pijí?"
RQ2 = "Proč nepijí kávu?"
DESIGN: dict[str, Any] = {
    "title": "Ranní nápoj",
    "goal": "Zjistit, zda nový nápoj dává smysl dojíždějícím.",
    "n": 450,
    "research_plan": {"research_questions": [RQ1, RQ2]},
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
#: The route's prices, as ``test_deep_research_interpretation_api.py`` states them.
ROUTE = {
    "bedrock_input_usd_per_mtok": 3.0,
    "bedrock_output_usd_per_mtok": 15.0,
    "bedrock_context_window_tokens": 200_000,
    "ai_research_max_output_tokens": 8_192,
}


@pytest.fixture
def settings(settings: Settings, tmp_path: Path) -> Settings:
    """A file-backed database (these tests may start a worker), fictional fieldwork, the
    route's prices, and the Lead on."""
    update: dict[str, Any] = {
        **ROUTE,
        "research_fieldwork_source": FieldworkSource.SYNTHETIC_FIXTURE,
        "ai_research_lead_enabled": True,
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


def _save(app: FastAPI, world: Any, content: dict[str, Any] = DESIGN) -> int:
    with create_session_factory(app.state.engine)() as session:
        scope = _scope(world, session)
        current = StudyWorkspaceRepository(session).content(scope).revision
        saved = StudyWorkspaceRepository(session).save(
            scope,
            content=content,
            base_revision=current,
            by=WriteBy(ActorKind.PERSON, scope.actor_id, OpSource.UI),
        )
        session.commit()
        return saved.revision


def _complete(app: FastAPI, world: Any, output: dict[str, Any]) -> None:
    with create_session_factory(app.state.engine)() as session:
        workflows = WorkflowRepository(session, _scope(world, session))
        work = workflows.claim_next(worker_id="w", kinds={RESEARCH_LEAD_TURN})
        assert work is not None
        workflows.complete_attempt(
            work.attempt_id,
            worker_id="w",
            output={"lead_output": output, "dropped": [], "self_update_applied": None},
        )
        session.commit()


def _turn(client: TestClient, world: Any, app: FastAPI, request: dict[str, Any]) -> str:
    """A completed Lead turn whose card is ``request``, frozen over today's study."""
    if client.get(f"{API}/lead").json().get("hatched") is not True:
        assert client.post(f"{API}/lead").status_code == 201
    posted = client.post(
        f"{_study(world)}/lead/turns", json={"kind": "message", "stage": "brief", "text": "Co dál?"}
    )
    assert posted.status_code == 201, posted.text
    _complete(app, world, {"reply": "Připraveno.", "request": request})
    return str(posted.json()["turns"][-1]["turn_id"])


def _approve(client: TestClient, world: Any, turn_id: str, **body: Any) -> Any:
    return client.post(f"{_study(world)}/lead/turns/{turn_id}/request", json=body)


def _frozen(app: FastAPI, world: Any, turn_id: str) -> dict[str, Any]:
    """The context the turn froze, as the application reads it (its manifest's source)."""
    from aia_core.application.research_lead import ResearchLead

    with create_session_factory(app.state.engine)() as session:
        frozen = ResearchLead(session, _scope(world, session))._frozen(turn_id)
        assert frozen is not None
        return dict(frozen)


def _written(app: FastAPI) -> dict[str, int]:
    """Every row a card's approval may write."""
    with create_session_factory(app.state.engine)() as session:

        def count(*where: Any) -> int:
            return int(
                session.scalar(select(func.count()).select_from(where[0]).where(*where[1:])) or 0
            )

        return {
            "runs": count(WorkflowRunRow, WorkflowRunRow.workflow_type == DEEP_RESEARCH),
            "cards": count(
                ApprovalDecisionRow,
                ApprovalDecisionRow.subject_type == ApprovalSubject.LEAD_JOB_REQUEST,
            ),
            "lead_card": count(
                ApprovalDecisionRow, ApprovalDecisionRow.subject_type == ApprovalSubject.LEAD_CARD
            ),
            "charges": count(StudyWalletChargeRow, StudyWalletChargeRow.charge_id.is_not(None)),
            "holds": count(BudgetReservationRow, BudgetReservationRow.reservation_id.is_not(None)),
        }


def _card_row(app: FastAPI) -> dict[str, Any]:
    with create_session_factory(app.state.engine)() as session:
        row = session.scalars(
            select(ApprovalDecisionRow).where(
                ApprovalDecisionRow.subject_type == ApprovalSubject.LEAD_JOB_REQUEST
            )
        ).one()
        return {"gate_type": row.gate_type, **json.loads(row.comment or "{}")}


def _rq_ids() -> list[str]:
    ids = list_ids(
        with_item_ids(DESIGN)[0]["research_plan"], "research_questions", "research_question_ids"
    )
    assert ids is not None
    return ids


# --------------------------------------------------------------------------- design cards


def test_a_design_card_starts_one_run_on_its_focus_and_a_second_approval_returns_it(
    app: FastAPI, researcher: TestClient, world: Any
) -> None:
    _save(app, world)
    rq2 = _rq_ids()[1]
    card = {"kind": "design_research", "why": WHY, "preset": "QUICK", "focus": [rq2]}
    turn_id = _turn(researcher, world, app, card)
    approved = _approve(researcher, world, turn_id)
    assert approved.status_code == 200, approved.text
    body = approved.json()
    assert _written(app) == {"runs": 1, "cards": 1, "lead_card": 0, "charges": 0, "holds": 0}
    row = _card_row(app)
    assert row["gate_type"] == "design_research"
    assert (row["agent_run_id"], row["purpose"], row["preset"], row["focus"]) == (
        body["run_id"],
        "DESIGN_RESEARCH",
        "QUICK",
        [rq2],
    )
    assert row["target"] == {
        "kind": "DESIGN_REVISION",
        "design_revision_id": body["design_revision_id"],
    }
    assert row["ceiling_usd"] is not None and row["spend"] is None
    run = researcher.get(f"{_study(world)}/deep-research/runs/{body['run_id']}").json()
    assert run["purpose"] == "DESIGN_RESEARCH" and run["preset"] == "QUICK"
    # Approved once: asked again, the same run, nothing written.
    again = _approve(researcher, world, turn_id)
    assert again.json()["run_id"] == body["run_id"]
    assert _written(app)["runs"] == 1 and _written(app)["cards"] == 1
    # The card's run is the stage's run: the same spec, found by idempotency.
    stage = researcher.post(
        f"{_study(world)}/deep-research/runs",
        json={
            "design_revision_id": body["design_revision_id"],
            "preset_name": "QUICK",
            "channels": ["WEB"],
            "focus": [rq2],
        },
    )
    assert stage.status_code == 200 and stage.json()["run_id"] == body["run_id"]
    assert stage.json()["run_spec_fingerprint"] == run["run_spec_fingerprint"]


def test_a_design_card_on_a_moved_working_copy_waits_for_the_persons_yes(
    app: FastAPI, researcher: TestClient, world: Any
) -> None:
    _save(app, world)
    turn_id = _turn(researcher, world, app, {"kind": "design_research", "why": WHY})
    # The person saves a change after the card was prepared.
    current = _save(app, world, {**DESIGN, "title": "Ranní nápoj 2"})
    stale = _approve(researcher, world, turn_id)
    assert stale.status_code == 409 and stale.json()["code"] == "stale_card"
    assert _written(app)["runs"] == 0
    yes = _approve(researcher, world, turn_id, workspace_revision=current)
    assert yes.status_code == 200, yes.text


def test_the_threshold_asks_and_the_confirmation_is_recorded_as_spend(
    app: FastAPI, researcher: TestClient, world: Any
) -> None:
    _save(app, world)
    turn_id = _turn(researcher, world, app, {"kind": "design_research", "why": WHY})
    with create_session_factory(app.state.engine)() as session:
        ScopeRepository(session).set_study_spend_confirm(_scope(world, session), 0.01)
        session.commit()
    asked = _approve(researcher, world, turn_id)
    assert asked.status_code == 409 and asked.json()["code"] == "cost_confirmation_required"
    ceiling = asked.json()["details"]["ceiling_usd"]
    assert _written(app)["runs"] == 0 and _written(app)["cards"] == 0
    approved = _approve(researcher, world, turn_id, confirm_cost_usd=ceiling)
    assert approved.status_code == 200, approved.text
    assert _card_row(app)["spend"] == {
        "ceiling_usd": ceiling,
        "limit_usd": 0.01,
        "confirmed_usd": ceiling,
    }


def test_a_priced_route_without_approved_live_settings_writes_nothing(
    app: FastAPI, researcher: TestClient, world: Any
) -> None:
    _save(app, world)
    turn_id = _turn(researcher, world, app, {"kind": "design_research", "why": WHY})
    app.state.settings = app.state.settings.model_copy(
        update={"deep_research_web_search": "brave", "deep_research_brave_usd_per_1000": 5.0}
    )
    refused = _approve(researcher, world, turn_id)
    assert refused.status_code == 409 and refused.json()["code"] == "live_settings_unapproved"
    assert refused.json()["details"]["missing"] and refused.json()["details"]["routes"]
    assert _written(app) == {"runs": 0, "cards": 0, "lead_card": 0, "charges": 0, "holds": 0}


def test_with_the_lead_off_a_card_starts_nothing(
    app: FastAPI, researcher: TestClient, world: Any
) -> None:
    _save(app, world)
    turn_id = _turn(researcher, world, app, {"kind": "design_research", "why": WHY})
    app.state.settings = app.state.settings.model_copy(update={"ai_research_lead_enabled": False})
    refused = _approve(researcher, world, turn_id)
    assert refused.status_code == 409 and refused.json()["code"] == "research_lead_disabled"
    assert _written(app) == {"runs": 0, "cards": 0, "lead_card": 0, "charges": 0, "holds": 0}


def test_a_research_run_card_still_only_opens_its_stage(
    app: FastAPI, researcher: TestClient, world: Any
) -> None:
    _save(app, world)
    turn_id = _turn(researcher, world, app, {"kind": "research_run", "why": WHY})
    refused = _approve(researcher, world, turn_id)
    assert refused.status_code == 422 and refused.json()["code"] == "not_a_paid_request"


# --------------------------------------------------------------------------- the wallet


def _wallet_on(app: FastAPI, client: TestClient, world: Any, cap: float) -> None:
    app.state.settings = app.state.settings.model_copy(update={"study_wallet_enabled": True})
    assert client.put(f"{_study(world)}/budget", json={"budget_usd": 100.0}).status_code == 200
    set_cap = client.put(f"{_study(world)}/wallet", json={"cap_usd": cap})
    assert set_cap.status_code == 200, set_cap.text


def test_with_the_wallet_on_a_card_is_charged_once_under_its_lead_card_row(
    app: FastAPI, researcher: TestClient, world: Any
) -> None:
    _save(app, world)
    _wallet_on(app, researcher, world, cap=50.0)
    turn_id = _turn(researcher, world, app, {"kind": "design_research", "why": WHY})
    approved = _approve(researcher, world, turn_id)
    assert approved.status_code == 200, approved.text
    assert _written(app) == {"runs": 1, "cards": 1, "lead_card": 1, "charges": 1, "holds": 0}
    with create_session_factory(app.state.engine)() as session:
        charge = session.scalars(select(StudyWalletChargeRow)).one()
        card = session.scalars(
            select(ApprovalDecisionRow).where(
                ApprovalDecisionRow.subject_type == ApprovalSubject.LEAD_CARD
            )
        ).one()
        assert charge.run_id == approved.json()["run_id"] == card.run_id
        assert (charge.kind, charge.approval_decision_id) == ("deep_research", card.decision_id)
        assert card.decision == "start"
        assert charge.ceiling_usd == _card_row(app)["ceiling_usd"]
    _approve(researcher, world, turn_id)
    assert _written(app)["charges"] == 1


def test_a_card_over_the_wallets_remainder_starts_and_charges_nothing(
    app: FastAPI, researcher: TestClient, world: Any
) -> None:
    _save(app, world)
    _wallet_on(app, researcher, world, cap=0.01)
    turn_id = _turn(researcher, world, app, {"kind": "design_research", "why": WHY})
    refused = _approve(researcher, world, turn_id)
    assert refused.status_code == 409 and refused.json()["code"] == "outside_wallet"
    assert _written(app) == {"runs": 0, "cards": 0, "lead_card": 0, "charges": 0, "holds": 0}


def test_a_card_is_charged_the_ceiling_its_run_pinned_not_the_quote(
    app: FastAPI, researcher: TestClient, world: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A setting changed between the quote and the start moves the ceiling the start pins; the
    wallet holds the pinned one, so a run the quote under-priced cannot run past the remainder
    (review of #1006)."""
    real_quote = DeepResearchRuns.quote

    def underpriced(self: DeepResearchRuns, *a: Any, **k: Any) -> Any:
        quoted = real_quote(self, *a, **k)
        assert quoted.ceiling is not None and quoted.ceiling.total_usd is not None
        low = replace(quoted.ceiling, total_usd=quoted.ceiling.total_usd / 100)
        return replace(quoted, ceiling=low)

    monkeypatch.setattr(DeepResearchRuns, "quote", underpriced)
    _save(app, world)
    _wallet_on(app, researcher, world, cap=50.0)
    turn_id = _turn(researcher, world, app, {"kind": "design_research", "why": WHY})
    approved = _approve(researcher, world, turn_id)
    assert approved.status_code == 200, approved.text
    with create_session_factory(app.state.engine)() as session:
        run = WorkflowRepository(session, _scope(world, session)).get_run(approved.json()["run_id"])
        pinned = run["metadata"]["cost_ceiling_usd"]
        charge = session.scalars(select(StudyWalletChargeRow)).one()
    assert pinned is not None and charge.ceiling_usd == pinned
    assert _card_row(app)["ceiling_usd"] == pinned


def test_a_pinned_ceiling_over_the_wallets_remainder_rolls_the_start_back(
    app: FastAPI, researcher: TestClient, world: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    real_quote = DeepResearchRuns.quote

    def free(self: DeepResearchRuns, *a: Any, **k: Any) -> Any:
        quoted = real_quote(self, *a, **k)
        assert quoted.ceiling is not None
        return replace(quoted, ceiling=replace(quoted.ceiling, total_usd=0.0))

    monkeypatch.setattr(DeepResearchRuns, "quote", free)
    _save(app, world)
    _wallet_on(app, researcher, world, cap=0.01)
    turn_id = _turn(researcher, world, app, {"kind": "design_research", "why": WHY})
    refused = _approve(researcher, world, turn_id)
    assert refused.status_code == 409 and refused.json()["code"] == "outside_wallet"
    assert _written(app) == {"runs": 0, "cards": 0, "lead_card": 0, "charges": 0, "holds": 0}


# --------------------------------------------------------------------------- interpretation


def _worker(app: FastAPI) -> Worker:
    from aia_core.infrastructure.build_identity import BuildIdentity
    from aia_executors import workbench

    settings = app.state.settings
    return Worker(
        session_factory=create_session_factory(app.state.engine),
        executors=workbench.workbench_registry_for(
            store=app.state.artifact_store, build=BuildIdentity(sha="a15be650937aacaa")
        ),
        settings=WorkerSettings(
            database_url=settings.database_url,
            executors="aia_executors.registry:build_registry",
            worker_id="lead-card-worker",
            lease_seconds=30,
            heartbeat_seconds=0.1,
            poll_seconds=0.05,
        ),
    )


def _completed_run(app: FastAPI, client: TestClient, world: Any) -> str:
    revision = world.design(client, DESIGN)
    assert revision.status_code == 201, revision.text
    started = client.post(
        f"{_study(world)}/research/runs",
        json={"design_revision_id": revision.json()["revision_id"]},
    )
    assert started.status_code == 201, started.text
    worker = _worker(app)
    while worker.run_once() is not None:
        pass
    run_id = str(started.json()["run_id"])
    assert client.get(f"{_study(world)}/research/runs/{run_id}").json()["status"] == "COMPLETED"
    return run_id


def test_an_interpretation_card_starts_on_the_candidate_its_turn_was_shown(
    app: FastAPI, researcher: TestClient, world: Any
) -> None:
    run_id = _completed_run(app, researcher, world)
    turn_id = _turn(
        researcher, world, app, {"kind": "interpretation_research", "why": WHY, "target": "t1"}
    )
    candidate = next(
        c
        for c in next(e for e in _frozen(app, world, turn_id)["layers"] if e["layer"] == "targets")[
            "candidates"
        ]
        if c["id"] == "t1"
    )
    approved = _approve(researcher, world, turn_id)
    assert approved.status_code == 200, approved.text
    run = researcher.get(f"{_study(world)}/deep-research/runs/{approved.json()['run_id']}").json()
    assert run["purpose"] == "INTERPRETATION_RESEARCH"
    assert run["target"] == candidate["ref"] and run["target"]["research_run_id"] == run_id
    assert _card_row(app)["target"] == candidate["ref"]
    # The stage's start over the same target is the same run.
    stage = researcher.post(
        f"{_study(world)}/deep-research/runs/interpretation",
        json={"target": candidate["ref"], "preset_name": "STANDARD", "channels": ["WEB"]},
    )
    assert stage.status_code == 200 and stage.json()["run_id"] == approved.json()["run_id"]


def test_a_target_the_turn_was_not_shown_is_404_and_a_moved_pin_is_refused(
    app: FastAPI, researcher: TestClient, world: Any
) -> None:
    _completed_run(app, researcher, world)
    unknown = _turn(
        researcher, world, app, {"kind": "interpretation_research", "why": WHY, "target": "t99"}
    )
    assert _approve(researcher, world, unknown).status_code == 404
    shown = _turn(
        researcher, world, app, {"kind": "interpretation_research", "why": WHY, "target": "t1"}
    )
    # The aggregate the candidate pins no longer reads: the start refuses it, writing nothing.
    with create_session_factory(app.state.engine)() as session:
        aggregate = session.scalars(
            select(StepRunRow).where(StepRunRow.node_key == "aggregate")
        ).one()
        row = session.get(ProjectArtifactRow, aggregate.output_json["artifact_id"])
        assert row is not None
        app.state.artifact_store.delete(row.storage_key)
    moved = _approve(researcher, world, shown)
    assert moved.status_code == 409 and moved.json()["code"] == "artifact_corrupt"
    assert _written(app)["runs"] == 0 and _written(app)["cards"] == 0


# --------------------------------------------------------------------------- retry


def test_a_retry_card_retries_the_run_it_names_once(
    app: FastAPI, researcher: TestClient, world: Any
) -> None:
    _save(app, world)
    started = _approve(
        researcher, world, _turn(researcher, world, app, {"kind": "design_research", "why": WHY})
    ).json()
    cancelled = researcher.post(f"{_study(world)}/deep-research/runs/{started['run_id']}/cancel")
    assert cancelled.status_code == 200, cancelled.text
    turn_id = _turn(
        researcher,
        world,
        app,
        {"kind": "deep_research_retry", "why": WHY, "run_id": started["run_id"]},
    )
    retried = _approve(researcher, world, turn_id)
    assert retried.status_code == 200, retried.text
    assert retried.json()["run_id"] != started["run_id"]
    with create_session_factory(app.state.engine)() as session:
        run = WorkflowRepository(session, _scope(world, session)).get_run(retried.json()["run_id"])
        assert run["metadata"]["retry_of"] == started["run_id"]
    assert _approve(researcher, world, turn_id).json()["run_id"] == retried.json()["run_id"]
