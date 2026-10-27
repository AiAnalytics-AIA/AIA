"""Native design assistance: scope, frozen context and typed proposals."""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError

from aia_core.application.research import ResearchAgentJobs, ResearchRunNotFound, _Probed
from aia_core.domain.ai_contracts import canonical_json, schema_node_is_open, schema_object_nodes
from aia_core.domain.ai_material import MaterialApproval, material_sha256
from aia_core.domain.design import DesignRejected
from aia_core.domain.edit_log import ActorKind, OpSource, WriteBy
from aia_core.domain.knowledge import KnowledgeItem, KnowledgeKind
from aia_core.domain.prompts import PromptPin
from aia_core.domain.research_agents import (
    CONTEXT_MAX_BYTES,
    CONTRACTS,
    EXTERNAL_ACTIONS,
    EXTERNAL_KEY,
    EXTERNAL_RAIL,
    Advice,
    BriefAnalysis,
    ResearchAction,
    agent_request,
    context_snapshot,
    external_record,
    proposal_result,
    snapshot_hash,
    with_external_context,
)
from aia_core.domain.residency import DataClass
from aia_core.domain.scope import ScopeRole
from aia_core.infrastructure.study_design_repository import StudyDesignRepository
from aia_core.infrastructure.study_workspace_repository import StudyWorkspaceRepository

DESIGN = {"title": "Fictional", "goal": "Test concept", "sections": []}
APPROVALS = (
    MaterialApproval(
        sha256=material_sha256(DESIGN),
        data_class=DataClass.CLASS_C_INTERNAL,
        provenance="test-generated design; no client input",
    ),
)


def analysis() -> BriefAnalysis:
    return BriefAnalysis(
        title="Concept",
        problem_summary="Test a concept",
        decision_use="Launch",
        objectives=["Test appeal"],
        research_questions=["Why?"],
        hypotheses=[],
        recommended_topics=[],
        tracked_sets=[],
        non_object_measures=[],
        questions_for_user=[],
        complexity="short",
        method_reason="A short study",
        ready_for_questionnaire=True,
    )


def test_every_contract_is_closed_and_has_no_tools_or_fallback() -> None:
    snapshot = context_snapshot(DESIGN, [])
    for action in ResearchAction:
        request = agent_request(
            action,
            snapshot,
            instruction="",
            policy_version="test",
            material_approvals=APPROVALS,
            max_output_tokens=8192,
        )
        assert request.agent.output_contract is CONTRACTS[action]
        assert all(not schema_node_is_open(n) for n in schema_object_nodes(request.agent.schema))
        assert not request.agent.allowed_tools
        assert not request.fallback_policy.alternates
        assert request.requested_model is None and request.requested_provider is None
        # The design is Class B by the owner's rule; the operator's Class C cannot lower it.
        assert request.data_classification is DataClass.CLASS_B_DERIVED_CLIENT
    with pytest.raises(ValidationError):
        BriefAnalysis.model_validate({**analysis().model_dump(), "approved": True})


def test_knowledge_lineage_is_the_recorded_datasets_else_the_placeholder() -> None:
    # CR-4: the union of the items' recorded datasets; the placeholder for each
    # dataset-derived item that records none, which the data owner cleared for the EU Bedrock
    # route alone (Q60, licence_determinations.CLIENT_KNOWLEDGE_DATASET): this route refuses it.
    from aia_core.domain.knowledge import recorded_datasets
    from aia_core.domain.licence import LicenceDenied
    from aia_core.domain.licence_determinations import (
        SYNTHETIC_FIXTURE_DATASET,
        recorded_policy,
    )
    from aia_core.domain.research_agents import UNRECORDED_KNOWLEDGE_LINEAGE, knowledge_lineage
    from aia_core.domain.residency import ProviderRoute

    def item(kind: KnowledgeKind, datasets: tuple[str, ...] | None) -> KnowledgeItem:
        return KnowledgeItem(
            item_id=f"K-{kind.value}",
            client_id="C1",
            kind=kind,
            title="t",
            revision=1,
            datasets=datasets,
        )

    route = ProviderRoute(route_id="any-route", provider="bedrock")
    recorded = context_snapshot(
        DESIGN,
        [
            item(KnowledgeKind.DATASET, (SYNTHETIC_FIXTURE_DATASET,)),
            item(KnowledgeKind.FINDING, (SYNTHETIC_FIXTURE_DATASET,)),
            item(KnowledgeKind.TERM, None),
        ],
    )
    lineage = knowledge_lineage(recorded["knowledge"])
    assert lineage.datasets == {SYNTHETIC_FIXTURE_DATASET}
    recorded_policy().authorise(lineage=lineage, route=route)

    for unrecorded in (KnowledgeKind.DATASET, KnowledgeKind.FINDING, KnowledgeKind.ARTIFACT):
        snapshot = context_snapshot(
            DESIGN,
            [item(KnowledgeKind.DATASET, (SYNTHETIC_FIXTURE_DATASET,)), item(unrecorded, None)],
        )
        mixed = knowledge_lineage(snapshot["knowledge"])
        assert UNRECORDED_KNOWLEDGE_LINEAGE in mixed.datasets
        with pytest.raises(LicenceDenied, match=UNRECORDED_KNOWLEDGE_LINEAGE) as refused:
            recorded_policy().authorise(lineage=mixed, route=route)
        assert refused.value.reason == "not_approved_for_route"

    # A stored snapshot from before lineage was recorded reads exactly as it did.
    legacy = [{"item_id": "K1", "kind": "FINDING", "title": "t", "summary": "", "revision": 1}]
    assert knowledge_lineage(legacy).datasets == {UNRECORDED_KNOWLEDGE_LINEAGE}
    assert knowledge_lineage([]).datasets == frozenset()
    # Only a list of nonempty names is a record; anything else is unrecorded, never "none".
    assert recorded_datasets({}) is None
    assert recorded_datasets({"datasets": []}) is None
    assert recorded_datasets({"datasets": [""]}) is None
    assert recorded_datasets({"datasets": "aia_synthetic_fixture"}) is None
    assert recorded_datasets({"datasets": ["b", "a", "a"]}) == ("a", "b")
    assert knowledge_lineage([{"kind": "DATASET", "datasets": []}]).datasets == {
        UNRECORDED_KNOWLEDGE_LINEAGE
    }


def test_memory_is_frozen_bounded_and_never_downgraded_by_fictional_client() -> None:
    item = KnowledgeItem(
        item_id="K1",
        client_id="C1",
        kind=KnowledgeKind.FINDING,
        title="A finding",
        summary="Approved detail",
        revision=7,
    )
    snapshot = context_snapshot(DESIGN, [item])
    digest = snapshot_hash(snapshot)
    item.content["new"] = "not included"
    design_copy = {**DESIGN, "provider": "anthropic", "api_key": "test-secret"}
    assert snapshot_hash(context_snapshot(design_copy, [item])) == digest
    request = agent_request(
        ResearchAction.MEMORY,
        snapshot,
        instruction="",
        policy_version="test",
        material_approvals=APPROVALS,
        max_output_tokens=8192,
    )
    assert request.data_classification is DataClass.CLASS_A_CLIENT_CONFIDENTIAL
    assert request.data_lineage is not None and request.data_lineage.datasets
    huge = item.model_copy(update={"summary": "x" * 21000})
    omitted = context_snapshot(DESIGN, [huge])
    assert omitted["knowledge"] == [] and omitted["omitted_knowledge_ids"] == ["K1"]
    with pytest.raises(ValueError, match="64 KB"):
        context_snapshot({"brief": "x" * 64000}, [])


def test_agent_cannot_cite_sources_outside_its_context_or_mutate_scope() -> None:
    snapshot = context_snapshot(DESIGN, [])
    output = Advice(
        answer="Found it", source_ids=["other-client-source"], followup_questions=[], limitations=[]
    )
    with pytest.raises(ValueError, match="outside"):
        proposal_result(ResearchAction.MEMORY, DESIGN, output, snapshot)
    result = proposal_result(ResearchAction.ANALYZE, DESIGN, analysis(), snapshot)
    assert DESIGN["sections"] == [] and "research_plan" not in DESIGN
    assert result["project"]["research_plan"]["status"] == "analyzed"
    assert "organization_id" not in result["project"]


def test_jobs_are_idempotent_and_hidden_across_studies(session: Any, scoped: Any) -> None:
    scope = scoped.scope(user="lead")
    revision, _ = StudyDesignRepository(session, scope).submit_as_working_copy(
        content=DESIGN, source_stage="brief"
    )
    jobs = ResearchAgentJobs(session, scope)
    first = jobs.start(design_revision_id=revision.revision_id, action=ResearchAction.ANALYZE)
    second = jobs.start(design_revision_id=revision.revision_id, action=ResearchAction.ANALYZE)
    assert first.run_id == second.run_id and first.created and not second.created
    changed = jobs.start(
        design_revision_id=revision.revision_id,
        action=ResearchAction.ANALYZE,
        instruction="Change the goal",
    )
    assert changed.run_id != first.run_id
    sibling = ResearchAgentJobs(session, scoped.scope(user="lead", study="sibling"))
    with pytest.raises(ResearchRunNotFound):
        sibling.get(first.run_id)
    # ADR 0019: the former viewer holds EDIT_STUDY and RUN_WORKFLOW like anyone; asking for the
    # job that is already there is the same job, whoever asks. No grant means no study scope.
    by_viewer = ResearchAgentJobs(session, scoped.scope(user="viewer")).start(
        design_revision_id=revision.revision_id, action=ResearchAction.ANALYZE
    )
    assert by_viewer.run_id == first.run_id and not by_viewer.created
    assert scoped.scope(user="outsider").role is ScopeRole.RESEARCHER  # ADR 0019: a member is in
    with pytest.raises(DesignRejected, match="completed"):
        from aia_core.infrastructure.storage import InMemoryArtifactStore

        jobs.result(first.run_id, store=InMemoryArtifactStore())


def test_reviewed_proposal_refuses_newer_design(session: Any, scoped: Any) -> None:
    scope = scoped.scope(user="lead")
    designs = StudyDesignRepository(session, scope)
    first, _ = designs.submit_as_working_copy(content=DESIGN, source_stage="brief")
    second, _ = designs.submit_as_working_copy(
        content={**DESIGN, "title": "Edited"}, source_stage="brief"
    )
    assert second.workspace_revision is not None
    reviewed = StudyWorkspaceRepository(session).save(
        scope,
        content={**DESIGN, "title": "Reviewed"},
        base_revision=second.workspace_revision,
        by=WriteBy(ActorKind.PERSON, scope.actor_id, OpSource.UI),
    )
    with pytest.raises(DesignRejected) as error:
        designs.submit_if_current(
            content={**DESIGN, "title": "Reviewed"},
            source_stage="plan",
            expected_revision_id=first.revision_id,
            workspace_revision=reviewed.revision,
        )
    assert error.value.reason == "stale_proposal"
    accepted, created = designs.submit_if_current(
        content={**DESIGN, "title": "Reviewed"},
        source_stage="plan",
        expected_revision_id=second.revision_id,
        workspace_revision=reviewed.revision,
    )
    assert created and accepted.parent_revision == second.revision
    assert accepted.workspace_revision == reviewed.revision


def test_questionnaire_proposal_preserves_library_sections_and_unique_ids() -> None:
    from aia_core.domain.research_agents import QuestionnaireProposal

    canonical = {
        "id": "ai_section_1",
        "type": "questions",
        "metadata": {"instrument_id": "canonical-library"},
        "questions": [{"id": "ai_q_1_1", "text": "Canonical question"}],
    }
    baseline = {**DESIGN, "sections": [canonical]}
    output = QuestionnaireProposal.model_validate(
        {
            "message": "Proposal",
            "warnings": [],
            "sections": [
                {
                    "type": "questions",
                    "title": "Custom",
                    "purpose": "Concept",
                    "questions": [
                        {
                            "text": "Appeal?",
                            "typ": "skala",
                            "kategorie": [],
                            "skala": [1, 5],
                            "popisky_skaly": ["Low", "High"],
                            "povolit_nevim": True,
                            "max_slov": 20,
                            "topics": [],
                            "research_questions": [],
                        }
                    ],
                }
            ],
            "comparisons": [],
        }
    )
    result = proposal_result(ResearchAction.BUILD, baseline, output, context_snapshot(baseline, []))
    sections = result["project"]["sections"]
    assert sections[0] == canonical
    assert sections[1]["id"] != canonical["id"]
    assert sections[1]["questions"][0]["id"] != canonical["questions"][0]["id"]
    assert baseline["sections"] == [canonical]


def test_audience_and_dimension_proposals_never_approve_filters_or_dimensions() -> None:
    from aia_core.domain.research_agents import AudienceProposal, DimensionsProposal

    baseline = {
        **DESIGN,
        "audience": {"filters": {"region": ["A"]}, "strategy": "filters"},
        "persona_dimensions": {"approved": ["existing"]},
    }
    snapshot = context_snapshot(baseline, [])
    audience = AudienceProposal(
        description="Proposed audience",
        inclusion_criteria=["Interested"],
        exclusion_criteria=[],
        questions_for_user=[],
        limitations=["Verify feasibility"],
    )
    result = proposal_result(ResearchAction.AUDIENCE, baseline, audience, snapshot)
    assert result["project"]["audience"]["filters"] == {"region": ["A"]}
    dimensions = DimensionsProposal.model_validate(
        {
            "new_dimension_suggestions": [
                {
                    "label": "New dimension",
                    "why": "Relevant",
                    "evidence_needed": ["Source evidence"],
                    "suggested_predictors": [],
                    "source_strategy": "document",
                }
            ],
            "limitations": [],
        }
    )
    result = proposal_result(ResearchAction.DIMENSIONS, baseline, dimensions, snapshot)
    assert result["project"]["persona_dimensions"]["approved"] == ["existing"]
    assert result["dimensions"] == []


RQ_HABIT = "Jak často lidé pijí kávu?"
RQ_IMAGE = "Jak lidé vnímají ranní nápoje?"


def _question(text: str, links: list[str]) -> dict[str, Any]:
    return {
        "text": text,
        "typ": "skala",
        "kategorie": [],
        "skala": [1, 5],
        "popisky_skaly": ["Málo", "Hodně"],
        "povolit_nevim": False,
        "max_slov": 20,
        "topics": [],
        "research_questions": links,
    }


def _linked_proposal(comparisons: list[dict[str, str]]) -> Any:
    from aia_core.domain.research_agents import QuestionnaireProposal

    return QuestionnaireProposal.model_validate(
        {
            "message": "Návrh",
            "warnings": [],
            "sections": [
                {
                    "type": "questions",
                    "title": "Zvyky",
                    "purpose": "Frekvence",
                    "questions": [
                        _question(
                            "Jak často pijete kávu?", [f"  {RQ_HABIT} ", "Vymyšlená otázka?"]
                        ),
                        _question("Kolik šálků denně?", []),
                    ],
                },
                {
                    "type": "object_battery",
                    "title": "Nápoje",
                    "purpose": "Vnímání",
                    "object_family": "nápoje",
                    "object_type": "nápoje",
                    "objects": ["Káva", "Čaj", "Kakao"],
                    "object_question": "Jak hodnotíte {object}?",
                    "scale": [1, 10],
                    "scale_labels": ["vůbec", "velmi"],
                    "familiarity_required": False,
                    "visualize": True,
                    "output_type": "test_konceptu",
                    "research_questions": [RQ_IMAGE, RQ_IMAGE],
                },
            ],
            "comparisons": comparisons,
        }
    )


def test_the_questionnaire_contract_stays_strict_compatible() -> None:
    """Plan 3e: the new fields are required, so the strict tier still applies."""
    from aia_core.domain.ai_contracts import output_schema, schema_supports_strict
    from aia_core.domain.research_agents import QuestionnaireProposal

    assert schema_supports_strict(output_schema(QuestionnaireProposal))


def test_a_proposal_keeps_only_links_to_stated_research_questions_in_their_wording() -> None:
    baseline = {**DESIGN, "research_plan": {"research_questions": [RQ_HABIT, RQ_IMAGE]}}
    result = proposal_result(
        ResearchAction.BUILD,
        baseline,
        _linked_proposal([]),
        context_snapshot(baseline, []),
    )
    questions, battery = result["project"]["sections"]
    assert questions["questions"][0]["research_questions"] == [RQ_HABIT]
    # None declared is no declaration: the key is left out, as the editor leaves it.
    assert "research_questions" not in questions["questions"][1]
    assert battery["research_questions"] == [RQ_IMAGE]
    assert battery["output_type"] == "test_konceptu"
    assert result["dropped_links"] == [
        {"item": questions["questions"][0]["id"], "research_question": "Vymyšlená otázka?"}
    ]


def test_a_proposal_declares_comparisons_for_stated_questions_and_keeps_the_others() -> None:
    baseline = {
        **DESIGN,
        "research_plan": {
            "research_questions": [RQ_HABIT, RQ_IMAGE],
            "research_question_comparisons": {RQ_HABIT: "describe", f" {RQ_IMAGE}": "describe"},
        },
    }
    output = _linked_proposal(
        [
            {"research_question": RQ_IMAGE, "comparison": "ab_test"},
            {"research_question": "Vymyšlená otázka?", "comparison": "rank_objects"},
        ]
    )
    result = proposal_result(
        ResearchAction.OPTIMIZE, baseline, output, context_snapshot(baseline, [])
    )
    plan = result["project"]["research_plan"]
    assert plan["research_question_comparisons"] == {RQ_HABIT: "describe", RQ_IMAGE: "ab_test"}
    assert plan["research_questions"] == [RQ_HABIT, RQ_IMAGE]
    assert {"item": "comparison", "research_question": "Vymyšlená otázka?"} in result[
        "dropped_links"
    ]
    assert baseline["research_plan"]["research_question_comparisons"][RQ_HABIT] == "describe"


def test_without_stated_research_questions_every_link_is_dropped_not_invented() -> None:
    result = proposal_result(
        ResearchAction.BUILD,
        {**DESIGN, "goal": ""},
        _linked_proposal([{"research_question": RQ_HABIT, "comparison": "describe"}]),
        context_snapshot(DESIGN, []),
    )
    sections = result["project"]["sections"]
    assert all("research_questions" not in q for q in sections[0]["questions"])
    assert "research_questions" not in sections[1]
    assert "research_plan" not in result["project"]
    assert len(result["dropped_links"]) == 5


def test_an_accepted_proposal_compiles_with_its_links_and_concept_set() -> None:
    from aia_core.domain.research_design import compile_design

    baseline = {**DESIGN, "n": 400, "research_plan": {"research_questions": [RQ_HABIT, RQ_IMAGE]}}
    output = _linked_proposal([{"research_question": RQ_IMAGE, "comparison": "ab_test"}])
    project = proposal_result(
        ResearchAction.BUILD, baseline, output, context_snapshot(baseline, [])
    )["project"]
    spec, problems = compile_design(project)
    assert spec is not None, problems
    assert spec.questions[0].research_questions == (RQ_HABIT,)
    assert spec.batteries[0].research_questions == (RQ_IMAGE,)
    assert spec.batteries[0].output_type == "test_konceptu"


@pytest.mark.parametrize(
    ("plan", "kept"),
    [
        ("not an object", False),
        ({"research_questions": [RQ_HABIT], "research_question_comparisons": ["bad"]}, True),
    ],
)
def test_a_malformed_plan_never_loses_the_paid_proposal(plan: Any, kept: bool) -> None:
    """Review (Codex on #435): a design may hold any JSON below its top level; the mapping
    must still return the proposal, never raise after the model was paid for."""
    baseline = {**DESIGN, "goal": RQ_HABIT, "research_plan": plan}
    output = _linked_proposal([{"research_question": RQ_HABIT, "comparison": "describe"}])
    result = proposal_result(ResearchAction.BUILD, baseline, output, context_snapshot(baseline, []))
    project = result["project"]
    assert project["sections"][0]["questions"][0]["research_questions"] == [RQ_HABIT]
    if kept:
        assert project["research_plan"]["research_question_comparisons"] == {RQ_HABIT: "describe"}
    else:
        assert project["research_plan"] == "not an object"
        assert {"item": "comparison", "research_question": RQ_HABIT} in result["dropped_links"]


def test_a_proposal_on_a_design_with_no_working_revision_is_refused_as_unknown(
    session: Any, scoped: Any
) -> None:
    """ADR 0026 decision 5: a Design Revision written before every writer named its working
    revision cannot have its proposal checked item by item; the accept is refused as
    ``unknown_baseline`` before anything is read or written, never read as "nothing changed"."""
    from aia_core.application.proposal_accept import StaleProposal
    from aia_core.infrastructure.repositories import ProjectRepository
    from aia_core.infrastructure.storage import InMemoryArtifactStore

    scope = scoped.scope(user="lead")
    designs = StudyDesignRepository(session, scope)
    designs.submit_as_working_copy(content=DESIGN, source_stage="brief")
    project_id = designs.project_id()
    assert project_id is not None
    ProjectRepository(session, scope, owner="study_design").save(
        project_id, content={**DESIGN, "n": 7}, reason="design:brief"
    )
    legacy = designs.latest()
    assert legacy is not None and legacy.workspace_revision is None
    jobs = ResearchAgentJobs(session, scope)
    run_id = jobs.start(design_revision_id=legacy.revision_id, action=ResearchAction.ANALYZE).run_id
    assert jobs.get(run_id)["metadata"]["base_workspace_revision"] is None
    working = StudyWorkspaceRepository(session).content(scope).revision
    assert working is not None
    with pytest.raises(StaleProposal) as refused:
        jobs.accept(
            run_id,
            store=InMemoryArtifactStore(),
            expected_revision_id=legacy.revision_id,
            expected_workspace_revision=working,
        )
    assert refused.value.reason == "stale_proposal"
    assert refused.value.details() == {
        "reason": "unknown_baseline",
        "conflicting_items": [],
        "conflicting_wording": {},
    }
    assert designs.latest() == legacy
    assert StudyWorkspaceRepository(session).content(scope).revision == working


@pytest.mark.parametrize(
    ("action", "completed", "decision", "superseded", "state"),
    [
        ("analyze_brief", True, None, False, "pending"),
        ("analyze_brief", True, "accept", True, "accepted"),
        ("analyze_brief", True, "dismiss", True, "dismissed"),
        ("build_questionnaire", True, None, True, "superseded"),
        ("analyze_brief", False, None, False, None),
        ("design_copilot", True, None, False, None),
        ("not_an_action", True, None, False, None),
    ],
)
def test_a_proposals_state_is_derived_never_stored(
    action: str, completed: bool, decision: str | None, superseded: bool, state: str | None
) -> None:
    """ADR 0026 decision 8: accepted over dismissed over superseded over pending; advice and a
    job with no proposal have no state at all, never "pending" by default."""
    from aia_core.domain.research_agents import proposal_state

    found = proposal_state(
        action=action, completed=completed, decision=decision, superseded=superseded
    )
    assert (found.value if found else None) == state


PIN = {"deep_research_run_id": "RUN-dr1", "artifact_id": "ART-b1", "sha256": "ab" * 32}
NEWER = {"deep_research_run_id": "RUN-dr2", "artifact_id": "ART-b2", "sha256": "cd" * 32}
LINES = ["[EV-1] Fictional finding (https://example.test/a)", "[EV-2] Another (https://x.test)"]


def test_external_context_frames_the_findings_and_trims_them_to_the_bound() -> None:
    snapshot = context_snapshot(DESIGN, [])
    assert with_external_context(snapshot, PIN, []) is snapshot
    assert external_record(snapshot) is None
    framed = with_external_context(snapshot, PIN, LINES)
    assert framed[EXTERNAL_KEY] == {"pin": PIN, "findings": LINES}
    assert snapshot_hash(framed) != snapshot_hash(snapshot)
    assert snapshot_hash(with_external_context(snapshot, NEWER, LINES)) != snapshot_hash(framed)
    assert external_record(framed) == {"pin": PIN, "findings": 2, "omitted": 0, "unavailable": None}
    # Optional context never refuses a job the design fits: the findings past the bound go, counted.
    room = CONTEXT_MAX_BYTES - len(canonical_json(framed).encode())
    trimmed = with_external_context(snapshot, PIN, [*LINES, "x" * (room + 1)])
    assert trimmed[EXTERNAL_KEY] == {"pin": PIN, "findings": LINES, "omitted": 1}
    assert with_external_context(snapshot, PIN, ["x" * CONTEXT_MAX_BYTES])[EXTERNAL_KEY] == {
        "pin": PIN,
        "findings": [],
        "omitted": 1,
    }
    # A bundle that did not read is said, never read as no research.
    refused = with_external_context(snapshot, PIN, [], unavailable="context_moved")
    assert refused[EXTERNAL_KEY] == {"pin": PIN, "findings": [], "unavailable": "context_moved"}
    assert {ResearchAction.BUILD, ResearchAction.OPTIMIZE} == EXTERNAL_ACTIONS


def test_the_external_rail_rides_the_system_prompt_whenever_the_layer_does() -> None:
    snapshot = context_snapshot(DESIGN, [])
    edited = PromptPin.of(
        prompt_id="aia.research.build_questionnaire",
        version="4",
        origin="stored",
        text="Sestav dotazník.",
        declared_class="CLASS_C_INTERNAL",
        declared_by="USR-author",
    )

    def system(context: dict[str, Any], prompt: PromptPin | None) -> str:
        return agent_request(
            ResearchAction.BUILD,
            context,
            instruction="",
            policy_version="test",
            material_approvals=APPROVALS,
            max_output_tokens=8192,
            prompt=prompt,
        ).system

    assert EXTERNAL_RAIL not in system(snapshot, None)
    framed = with_external_context(snapshot, PIN, LINES)
    # A stored edit replaces the task wording, never the rail.
    assert system(framed, None).endswith(EXTERNAL_RAIL)
    assert system(framed, edited).endswith(EXTERNAL_RAIL)


def test_questionnaire_jobs_freeze_the_pinned_findings_only_when_given_a_store(
    session: Any, scoped: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    from aia_core.application import analysis_results
    from aia_core.application.research import ResearchRuns
    from aia_core.infrastructure.storage import InMemoryArtifactStore
    from aia_core.infrastructure.workflow_repository import WorkflowRepository

    scope = scoped.scope(user="lead")
    revision, _ = StudyDesignRepository(session, scope).submit_as_working_copy(
        content=DESIGN, source_stage="brief"
    )
    state: dict[str, Any] = {"pin": PIN, "refused": False, "reads": 0}

    def read(_session: Any, _scope: Any, _store: Any, pin: Any) -> list[str]:
        assert pin == state["pin"]
        state["reads"] += 1
        if state["refused"]:
            raise analysis_results.SourcesRefused("context_moved", "the bundle moved")
        return LINES

    monkeypatch.setattr(ResearchRuns, "design_research_pin", lambda self: state["pin"])
    monkeypatch.setattr(analysis_results, "_external_context", read)
    workflows = WorkflowRepository(session, scope)
    store = InMemoryArtifactStore()

    def started(action: ResearchAction, *, store: Any = store) -> tuple[str, dict[str, Any]]:
        jobs = ResearchAgentJobs(session, scope, external_store=store)
        run = jobs.start(design_revision_id=revision.revision_id, action=action)
        step = workflows.step_input(run.run_id, "agent")
        assert step is not None
        return run.run_id, dict(step["snapshot"])

    _, plain = started(ResearchAction.BUILD, store=None)
    assert EXTERNAL_KEY not in plain and state["reads"] == 0  # the switch off: nothing read
    first, framed = started(ResearchAction.BUILD)
    assert framed[EXTERNAL_KEY] == {"pin": PIN, "findings": LINES}
    assert EXTERNAL_KEY not in started(ResearchAction.ANALYZE)[1]
    # A newer sealed run is a new job, never the old one's answer.
    state["pin"] = NEWER
    newer, _ = started(ResearchAction.BUILD)
    assert newer != first
    state["refused"] = True
    _, refused = started(ResearchAction.OPTIMIZE)
    assert refused[EXTERNAL_KEY] == {"pin": NEWER, "findings": [], "unavailable": "context_moved"}
    # A probe and the start it precedes read one bundle.
    reads = state["reads"]
    jobs = ResearchAgentJobs(session, scope, external_store=store)
    with pytest.raises(_Probed):
        jobs.start(
            design_revision_id=revision.revision_id, action=ResearchAction.BUILD, _probe=True
        )
    jobs.start(design_revision_id=revision.revision_id, action=ResearchAction.BUILD)
    assert state["reads"] == reads + 1
