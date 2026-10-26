"""The workbench's scripted Research Lead: no model, the rest of the pipeline for real."""

from __future__ import annotations

from typing import Any

from aia_core.application.research_lead import ResearchLead
from aia_core.application.scope import AuthenticatedPrincipal, ScopeResolver
from aia_core.domain.edit_log import ActorKind, OpSource, WriteBy
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
            world.lead_scope(session),
            content=CONTENT,
            base_revision=None,
            by=WriteBy(ActorKind.PERSON, world.lead_scope(session).actor_id, OpSource.UI),
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
            world.lead_scope(session),
            content=saved,
            base_revision=1,
            by=WriteBy(ActorKind.PERSON, world.lead_scope(session).actor_id, OpSource.UI),
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


def _frozen(message: str, content: dict[str, Any]) -> dict[str, Any]:
    return {
        "layers": [
            {"layer": "view", "kind": "message", "message": message},
            {"layer": "study", "name": "Fiktivní studie"},
            {"layer": "design", "content": content, "analysis": None},
        ]
    }


def test_a_scripted_message_about_the_goal_points_at_the_first_objective() -> None:
    """artifact-brief BRF6: the Brief's journey needs the scripted Lead to focus an objective."""
    from aia_core.domain.item_ids import list_ids, with_item_ids
    from aia_executors.workbench import scripted_lead_output

    with_objectives = {
        **CONTENT,
        "research_plan": {"objectives": ["Změřit zájem", "Najít cenu"]},
    }
    content, _ = with_item_ids(with_objectives)
    first = list_ids(content["research_plan"], "objectives", "objective_ids")
    assert first
    focused = scripted_lead_output(_frozen("Je cíl dost konkrétní?", with_objectives))
    assert [v.model_dump() for v in focused.view] == [
        {"op": "focus", "target": f"objective:{first[0]}"}
    ]
    # No objective, or no word about the goal: the target it always had.
    without = scripted_lead_output(_frozen("Je cíl dost konkrétní?", CONTENT))
    other = scripted_lead_output(_frozen("Kde jsme?", with_objectives))
    assert without.view == other.view
    assert not without.view[0].model_dump()["target"].startswith("objective:")


def test_a_scripted_message_asking_for_the_changes_shows_this_stage_s_waiting_ones() -> None:
    """research-lead-workbench 14: the journey needs the scripted Lead to run show_diff."""
    from aia_executors.workbench import scripted_lead_output

    frozen = _frozen("Ukaž mi změny", CONTENT)
    frozen["layers"][0]["stage"] = "questionnaire"
    assert [v.model_dump() for v in scripted_lead_output(frozen).view][1:] == [
        {"op": "show_diff", "stage": "questionnaire"}
    ]
    # Zadání shows no changes of its own; without the word, none either.
    frozen["layers"][0]["stage"] = "brief"
    assert len(scripted_lead_output(frozen).view) == 1
    frozen["layers"][0].update(stage="questionnaire", message="Kde jsme?")
    assert len(scripted_lead_output(frozen).view) == 1


def test_a_scripted_message_asking_for_a_detail_opens_the_first_research_question() -> None:
    """research-lead-workbench 14: the journey needs the scripted Lead to run ``inspect``."""
    from aia_core.domain.item_ids import list_ids, with_item_ids
    from aia_executors.workbench import scripted_lead_output

    with_rqs = {**CONTENT, "research_plan": {"research_questions": ["Kdo pije čaj?", "Proč?"]}}
    content, _ = with_item_ids(with_rqs)
    first = list_ids(content["research_plan"], "research_questions", "research_question_ids")
    assert first
    shown = scripted_lead_output(_frozen("Ukaž mi detail otázky", with_rqs))
    assert [v.model_dump() for v in shown.view][1:] == [
        {"op": "inspect", "target": f"rq:{first[0]}"}
    ]
    # No research question: the first hypothesis, also on Návrh.
    with_hypotheses = {**CONTENT, "research_plan": {"hypotheses": ["Čaj vede."]}}
    content, _ = with_item_ids(with_hypotheses)
    h = list_ids(content["research_plan"], "hypotheses", "hypothesis_ids")
    assert h
    shown = scripted_lead_output(_frozen("Ukaž mi detail", with_hypotheses))
    assert [v.model_dump() for v in shown.view][1:] == [
        {"op": "inspect", "target": f"hypothesis:{h[0]}"}
    ]
    # Without the word, or with neither: only the focus it always had.
    assert len(scripted_lead_output(_frozen("Kde jsme?", with_rqs)).view) == 1
    assert len(scripted_lead_output(_frozen("Ukaž mi detail otázky", CONTENT)).view) == 1


def test_a_scripted_message_about_research_prepares_deep_research() -> None:
    """lead-orchestration LO5a.1: the workbench journey needs both Deep Research cards without a
    model. Interpretation only over a default candidate: with none it would be refused."""
    from aia_core.domain.research_lead import lead_contract, request_ids
    from aia_executors.workbench import scripted_lead_output

    design = scripted_lead_output(_frozen("Udělej rešerši trhu", CONTENT))
    assert design.request is not None and design.request.kind == "design_research"
    assert design.request.preset == "STANDARD" and design.request.focus == []

    frozen = _frozen("Vysvětli výsledky", CONTENT)
    no_targets = scripted_lead_output(frozen)
    assert no_targets.request is not None and no_targets.request.kind == "agent_job"
    frozen["layers"].append({"layer": "targets", "candidates": [{"id": "t1"}], "default": "t1"})
    interpretation = scripted_lead_output(frozen)
    assert interpretation.request is not None
    assert interpretation.request.kind == "interpretation_research"
    assert interpretation.request.target is None
    # What the script prepares is grounded as a model's answer would be.
    contract = lead_contract("", ids=request_ids(frozen))
    contract.model_validate(interpretation.model_dump(mode="json"))
