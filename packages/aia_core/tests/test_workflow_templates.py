"""Workflow templates: the closed set of graphs a run may be created from."""

from __future__ import annotations

import pytest

from aia_core.domain.pipeline import ProjectType
from aia_core.domain.workflow import validate_dag
from aia_core.domain.workflow_templates import (
    DEVELOP_SNAPSHOT,
    RESEARCH,
    RESEARCH_AGENT,
    WORKFLOW_TYPES,
    UnknownWorkflowType,
    steps_for_workflow,
)


def test_the_set_of_workflow_types_is_closed() -> None:
    assert frozenset({DEVELOP_SNAPSHOT, RESEARCH, RESEARCH_AGENT}) == WORKFLOW_TYPES
    with pytest.raises(UnknownWorkflowType):
        steps_for_workflow("anything_else", project_type=ProjectType.RESEARCH)


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
