"""Native design assistance: scope, frozen context and typed proposals."""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError

from aia_core.application.research import ResearchAgentJobs, ResearchRunNotFound
from aia_core.domain.ai_contracts import schema_node_is_open, schema_object_nodes
from aia_core.domain.ai_material import MaterialApproval, material_sha256
from aia_core.domain.design import DesignRejected
from aia_core.domain.knowledge import KnowledgeItem, KnowledgeKind
from aia_core.domain.research_agents import (
    CONTRACTS,
    Advice,
    BriefAnalysis,
    ResearchAction,
    agent_request,
    context_snapshot,
    proposal_result,
    snapshot_hash,
)
from aia_core.domain.residency import DataClass
from aia_core.domain.scope import ScopeDenied
from aia_core.infrastructure.study_design_repository import StudyDesignRepository

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
        assert request.data_classification is DataClass.CLASS_C_INTERNAL
    with pytest.raises(ValidationError):
        BriefAnalysis.model_validate({**analysis().model_dump(), "approved": True})


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
    revision, _ = StudyDesignRepository(session, scope).submit(content=DESIGN, source_stage="brief")
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
    with pytest.raises(ScopeDenied):
        scoped.scope(user="outsider")
    with pytest.raises(DesignRejected, match="completed"):
        from aia_core.infrastructure.storage import InMemoryArtifactStore

        jobs.result(first.run_id, store=InMemoryArtifactStore())


def test_reviewed_proposal_refuses_newer_design(session: Any, scoped: Any) -> None:
    designs = StudyDesignRepository(session, scoped.scope(user="lead"))
    first, _ = designs.submit(content=DESIGN, source_stage="brief")
    second, _ = designs.submit(content={**DESIGN, "title": "Edited"}, source_stage="brief")
    with pytest.raises(DesignRejected) as error:
        designs.submit_if_current(
            content={**DESIGN, "title": "Agent"},
            source_stage="plan",
            expected_revision_id=first.revision_id,
        )
    assert error.value.reason == "stale_proposal"
    accepted, created = designs.submit_if_current(
        content={**DESIGN, "title": "Reviewed"},
        source_stage="plan",
        expected_revision_id=second.revision_id,
    )
    assert created and accepted.parent_revision == second.revision


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
                        }
                    ],
                }
            ],
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
