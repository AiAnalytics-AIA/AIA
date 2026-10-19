"""Workflow templates: the closed set of graphs a run may be created from."""

from __future__ import annotations

import pytest

from aia_core.domain.analysis import ANALYSIS_MODULES
from aia_core.domain.analysis.steps import analysis_node_key
from aia_core.domain.pipeline import ProjectType
from aia_core.domain.workflow import validate_dag
from aia_core.domain.workflow_templates import (
    CLIENT_SOURCE_PROPOSALS,
    DEVELOP_SNAPSHOT,
    POPULATION_MATERIALIZE,
    REPORT_PDF,
    REPORT_PDF_STEP_KIND,
    REPORT_STEP_KIND,
    RESEARCH,
    RESEARCH_AGENT,
    RESEARCH_LEAD,
    RESEARCH_LEAD_TURN,
    WORKFLOW_TYPES,
    UnknownWorkflowType,
    steps_for_workflow,
)


def test_the_set_of_workflow_types_is_closed() -> None:
    assert (
        frozenset(
            {
                DEVELOP_SNAPSHOT,
                RESEARCH,
                RESEARCH_AGENT,
                RESEARCH_LEAD,
                POPULATION_MATERIALIZE,
                CLIENT_SOURCE_PROPOSALS,
                REPORT_PDF,
            }
        )
        == WORKFLOW_TYPES
    )
    with pytest.raises(UnknownWorkflowType):
        steps_for_workflow("anything_else", project_type=ProjectType.RESEARCH)


def test_a_research_lead_turn_is_one_step_tried_once() -> None:
    """ADR 0026: one model request and its one repair; a retry would pay for the turn again."""
    (step,) = steps_for_workflow(RESEARCH_LEAD, project_type=ProjectType.RESEARCH)
    assert (step.node_key, step.kind, step.max_attempts) == ("turn", RESEARCH_LEAD_TURN, 1)
    assert step.depends_on == ()
    with pytest.raises(UnknownWorkflowType):
        steps_for_workflow(RESEARCH_LEAD, project_type=ProjectType.SIMULATION)


@pytest.mark.parametrize("project_type", list(ProjectType))
def test_develop_snapshot_is_one_valid_step_under_brief(project_type: ProjectType) -> None:
    steps = steps_for_workflow(DEVELOP_SNAPSHOT, project_type=project_type)
    validate_dag(steps)
    (step,) = steps
    assert step.kind == DEVELOP_SNAPSHOT
    assert step.stage_type == "BRIEF"
    assert step.depends_on == ()
    assert step.consumes_population is False
    assert step.max_attempts == 3


def test_research_agent_is_one_step_without_automatic_paid_retries() -> None:
    steps = steps_for_workflow(RESEARCH_AGENT, project_type=ProjectType.RESEARCH)
    validate_dag(steps)
    (step,) = steps
    assert step.kind == RESEARCH_AGENT
    assert step.max_attempts == 1
    assert step.consumes_population is False
    with pytest.raises(UnknownWorkflowType):
        steps_for_workflow(RESEARCH_AGENT, project_type=ProjectType.SIMULATION)


def test_client_source_proposals_is_one_step_without_automatic_paid_retries() -> None:
    """Lifecycle K2d3: one paid step; a lost answer is asked again by a person, never resent."""
    steps = steps_for_workflow(CLIENT_SOURCE_PROPOSALS, project_type=ProjectType.RESEARCH)
    validate_dag(steps)
    (step,) = steps
    assert (step.node_key, step.kind) == ("extract", CLIENT_SOURCE_PROPOSALS)
    assert step.max_attempts == 1
    assert step.consumes_population is False


def test_report_waits_for_every_analysis_module_when_analysis_is_enabled() -> None:
    graph = steps_for_workflow(RESEARCH, project_type=ProjectType.RESEARCH, analysis_enabled=True)
    validate_dag(graph)
    report = graph[-1]
    assert (report.node_key, report.kind, report.stage_type) == (
        "report",
        REPORT_STEP_KIND,
        "REPORT",
    )
    assert report.depends_on == (
        *tuple(analysis_node_key(m.module_id) for m in ANALYSIS_MODULES),
        "sociomap",
    )
    assert all(
        s.node_key != "report"
        for s in steps_for_workflow(RESEARCH, project_type=ProjectType.RESEARCH)
    )


def test_report_pdf_is_one_step_rendering_a_stored_report() -> None:
    steps = steps_for_workflow(REPORT_PDF, project_type=ProjectType.RESEARCH)
    validate_dag(steps)
    (step,) = steps
    assert (step.node_key, step.kind, step.stage_type) == ("pdf", REPORT_PDF_STEP_KIND, "REPORT")
    assert step.consumes_population is False
    with pytest.raises(UnknownWorkflowType):
        steps_for_workflow(REPORT_PDF, project_type=ProjectType.SIMULATION)
