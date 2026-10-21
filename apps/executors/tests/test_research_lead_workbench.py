"""The workbench's scripted Research Lead: no model, the rest of the pipeline for real."""

from __future__ import annotations

from typing import Any

from aia_core.application.research_lead import ResearchLead
from aia_core.application.scope import AuthenticatedPrincipal, ScopeResolver
from aia_core.infrastructure.researcher_lead_repository import ResearcherLeadRepository
from aia_core.infrastructure.study_design_repository import StudyDesignRepository
from aia_core.infrastructure.study_workspace_repository import StudyWorkspaceRepository
from aia_core.infrastructure.workflow_repository import WorkflowRepository
from aia_executors.registry import registry_for
from aia_executors.research_lead import ResearchLeadExecutor
from aia_executors.workbench import (
    SCRIPTED_PREFIX,
    ScriptedLeadExecutor,
    workbench_registry_for,
)
from aia_worker.settings import WorkerSettings
from aia_worker.worker import Worker

CONTENT: dict[str, Any] = {
    "title": "Fiktivní koncept",
    "sections": [
        {"id": "s1", "type": "questions", "questions": [{"id": "q1", "text": "Znáte značku?"}]}
    ],
}


def _worker(world: Any, database_url: str, store: Any, build: Any) -> Worker:
    return Worker(
        session_factory=world.sessions,
        executors=workbench_registry_for(store=store, build=build),
        settings=WorkerSettings(
            database_url=database_url,
            worker_id="workbench-lead",
            executors="aia_executors.workbench:build_registry",
            lease_seconds=30,
            heartbeat_seconds=0.1,
            poll_seconds=0.05,
            maintenance_seconds=0.2,
        ),
    )


def _setup(world: Any) -> None:
    with world.sessions() as session:
        org = ScopeResolver(session).organization_context(
            AuthenticatedPrincipal(user_id=world.lead_id, organization_id=world.organization_id)
        )
        ResearcherLeadRepository(session, org).hatch()
        StudyWorkspaceRepository(session).save(
            world.lead_scope(session), content=CONTENT, base_revision=None
        )
        session.commit()


def _post(world: Any, **kw: Any) -> None:
    with world.sessions() as session:
        ResearchLead(session, world.lead_scope(session), enabled=True).post(stage="brief", **kw)
        session.commit()


def _last(world: Any) -> dict[str, Any]:
    with world.sessions() as session:
        turns = ResearchLead(session, world.lead_scope(session), enabled=True).state()["turns"]
    return dict(turns[-1])


def test_only_the_workbench_composition_answers_without_a_model(store: Any, build: Any) -> None:
    production = registry_for(store=store, build=build)["research_lead_turn"]
    assert type(production) is ResearchLeadExecutor
    assert isinstance(
        workbench_registry_for(store=store, build=build)["research_lead_turn"],
        ScriptedLeadExecutor,
    )


def test_a_scripted_greeting_and_message_go_through_the_real_gates(
    world: Any, database_url: str, store: Any, build: Any
) -> None:
    _setup(world)
    worker = _worker(world, database_url, store, build)

    _post(world, kind="greeting")
    assert worker.run_once()
    greeting = _last(world)
    assert greeting["status"] == "COMPLETED"
    reply = greeting["output"]["reply"]
    assert reply.startswith(SCRIPTED_PREFIX) and len(reply.splitlines()) == 3
    assert "Studie: S." in reply and "Otázek v pracovní verzi: 1." in reply
    assert len(greeting["output"]["follow"]) == 1

    _post(world, kind="message", text="Pamatuj si, že chci výsledky v tabulkách.")
    assert worker.run_once()
    turn = _last(world)
    output = turn["output"]
    assert output["reply"].startswith(SCRIPTED_PREFIX)
    assert output["edits"] == [
        {
            "op": "question_edit",
            "question_id": "q1",
            "text": "Znáte značku? (upřesněno)",
            "options": None,
            "why": "Ukázková úprava z workbench",
        }
    ]
    assert output["view"] == [{"op": "focus", "target": "question:q1"}]
    assert output["request"] == {
        "kind": "agent_job",
        "action": "optimize_questionnaire",
        "why": "Ukázka rozhodnutí",
    }
    # A personal note reaches every client's studies: it waits for the researcher's yes.
    assert turn["changes"] is None and turn["self_update_pending"] is True

    with world.sessions() as session:
        scope = world.lead_scope(session)
        lead = ResearchLead(session, scope, enabled=True)
        decided = lead.decide_edits(
            turn["turn_id"], decision="accept", indices=[0], base_revision=1
        )
        approved = lead.approve_request(
            turn["turn_id"], confirm_cost_usd=None, reservation_usd=None
        )
        assert ResearcherLeadRepository(session, scope).notes_for_study() == []
        lead.decide_self_update(turn["turn_id"], decision="accept")
        notes = ResearcherLeadRepository(session, scope).notes_for_study()
        working = StudyWorkspaceRepository(session).content(scope)
        session.commit()
    assert decided["results"] == [{"index": 0, "status": "accepted", "reason": None}]
    assert working.content is not None
    assert working.content["sections"][0]["questions"][0]["text"] == "Znáte značku? (upřesněno)"
    assert approved["run_id"].startswith("RUN-")
    assert [n.text for n in notes] == ["Pamatuj si, že chci výsledky v tabulkách."]


def test_the_scripted_step_output_says_it_is_scripted(
    world: Any, database_url: str, store: Any, build: Any
) -> None:
    _setup(world)
    _post(world, kind="greeting")
    assert _worker(world, database_url, store, build).run_once()
    with world.sessions() as session:
        from aia_core.infrastructure.workflow_repository import WorkflowRepository

        run = WorkflowRepository(session, world.lead_scope(session)).get_run(_last(world)["run_id"])
    output = run["steps"][0]["output"]
    assert output["scripted"] is True and output["data_class"] is None


def test_a_scripted_message_asking_to_start_prepares_the_research_run(
    world: Any, database_url: str, store: Any, build: Any
) -> None:
    _setup(world)
    _post(world, kind="message", text="Spusť výzkum, prosím.")
    assert _worker(world, database_url, store, build).run_once()
    output = _last(world)["output"]
    assert output["request"] == {"kind": "research_run", "why": "Ukázka spuštění výzkumu"}


def test_the_design_update_from_saved_answers_and_comments_goes_through_approve_request(
    world: Any, database_url: str, store: Any, build: Any
) -> None:
    """Návrh's answers and comments, saved into the working copy in the workbench (the owner,
    2026-10-21), reach the brief's analysis the Lead prepares: its frozen design holds them, and
    the approval is the ledger's, as any Lead-prepared job's."""
    _setup(world)
    saved = {
        **CONTENT,
        "briefing": {
            "what_is_known": "Doplnění k analýze:\n1. Jezdí hlavně vlakem.",
            "review_comments": "1. K textu „cíl“: zúžit na Prahu",
        },
        "ui_state": {"plan_changed26": True},
    }
    with world.sessions() as session:
        StudyWorkspaceRepository(session).save(
            world.lead_scope(session), content=saved, base_revision=1
        )
        session.commit()
    _post(world, kind="message", text="Aktualizuj návrh podle mých komentářů.")
    assert _worker(world, database_url, store, build).run_once()
    turn = _last(world)
    assert turn["output"]["request"]["action"] == "analyze_brief"

    with world.sessions() as session:
        scope = world.lead_scope(session)
        approved = ResearchLead(session, scope, enabled=True).approve_request(
            turn["turn_id"], confirm_cost_usd=None, reservation_usd=None
        )
        design = StudyDesignRepository(session, scope).content(approved["design_revision_id"])
        decisions = WorkflowRepository(session, scope).lead_decisions([turn["turn_id"]])
        session.commit()
    assert design["briefing"]["what_is_known"].endswith("Jezdí hlavně vlakem.")
    assert design["briefing"]["review_comments"] == "1. K textu „cíl“: zúžit na Prahu"
    assert decisions[turn["turn_id"]]["request"]["run_id"] == approved["run_id"]
