"""Workflow templates: the step graphs a run may be created from, by name.

A caller names a **workflow type**; the template says which steps that means.
Keeping the mapping here, in the domain, means the API cannot compose a DAG from
a request body and the worker cannot invent one -- both only ever see a
template's output, and the templates are tested like any other rule.

Two templates:

* ``develop_snapshot`` -- a single deterministic step that records what a
  project's current revision looks like, as an artifact. It proves the deployed
  path browser -> API -> PostgreSQL -> worker -> ArtifactStore -> browser with no
  model call (ADR 0009).
* ``research`` -- a research Study's run over one Design Revision (ADR 0016). It
  carries the reference's node keys (``workflow_engine.STANDARD``,
  ``docs/architecture/workflows.md``): ``compile -> preflight -> run -> aggregate``,
  plus AIA's ``sociomap``. ``run`` is fieldwork, the reference's name for it. The
  remaining reference nodes (``donor_qc``, the analysis modules, ``interpret`` ...
  ``delivery``) join this template as their executors land; a node without an
  executor is never added, because a step no worker can claim would leave the run
  "running" forever.
"""

from __future__ import annotations

from typing import Final

from .analysis.steps import analysis_step_definitions
from .pipeline import ProjectType, stage_ids
from .workflow import StepDefinition

__all__ = [
    "DEVELOP_SNAPSHOT",
    "RESEARCH",
    "RESEARCH_KINDS",
    "WORKFLOW_TYPES",
    "UnknownWorkflowType",
    "steps_for_workflow",
]

#: The develop vertical slice: one deterministic step, no population, no model.
DEVELOP_SNAPSHOT: Final = "develop_snapshot"

#: A research Study's run over one Design Revision (ADR 0016).
RESEARCH: Final = "research"
RESEARCH_AGENT: Final = "research_agent"

#: Every workflow type a run may be created with. Closed: an unknown type is refused.
WORKFLOW_TYPES: Final[frozenset[str]] = frozenset({DEVELOP_SNAPSHOT, RESEARCH, RESEARCH_AGENT})

#: The research template's step kinds, by node key -- what an executor registers for.
RESEARCH_KINDS: Final[dict[str, str]] = {
    "compile": "research_compile",
    "preflight": "research_preflight",
    "run": "research_fieldwork",
    "aggregate": "research_aggregate",
    "sociomap": "research_sociomap",
}

# (node key, stage, depends on). Stages are the research lifecycle's
# (``pipeline.RESEARCH_STAGES``): the design is compiled at BRIEF, readiness is
# checked against the sample plan, fieldwork fills FIELDWORK, aggregation and the
# Sociomap are the first analysis outputs.
_RESEARCH_GRAPH: Final[tuple[tuple[str, str, tuple[str, ...]], ...]] = (
    ("compile", "BRIEF", ()),
    ("preflight", "SAMPLE_PLAN", ("compile",)),
    ("run", "FIELDWORK", ("preflight",)),
    ("aggregate", "AGGREGATION", ("run",)),
    ("sociomap", "ANALYSIS", ("run",)),
)


class UnknownWorkflowType(LookupError):
    """The named workflow type has no template."""


def steps_for_workflow(
    workflow_type: str, *, project_type: ProjectType, analysis_enabled: bool = False
) -> list[StepDefinition]:
    """Return the step graph for ``workflow_type`` against a project of ``project_type``.

    The snapshot step is filed under the project's **first** stage (``BRIEF`` in
    both lifecycles): it describes the project as briefed and depends on nothing
    downstream, so an edit to any later stage leaves it valid and reusable.
    """
    if workflow_type == DEVELOP_SNAPSHOT:
        first_stage = stage_ids(project_type)[0]
        return [
            StepDefinition(
                node_key="snapshot",
                kind=DEVELOP_SNAPSHOT,
                stage_type=first_stage,
                artifact_target=DEVELOP_SNAPSHOT,
                max_attempts=3,
            )
        ]
    if workflow_type == RESEARCH_AGENT:
        if project_type is not ProjectType.RESEARCH:
            raise UnknownWorkflowType(f"{RESEARCH_AGENT} needs a research project")
        return [
            StepDefinition(
                node_key="agent",
                kind=RESEARCH_AGENT,
                stage_type="BRIEF",
                artifact_target="research_agent_proposal",
                max_attempts=1,
            )
        ]
    if workflow_type == RESEARCH:
        if project_type is not ProjectType.RESEARCH:
            raise UnknownWorkflowType(f"{RESEARCH} needs a research project")
        steps = [
            StepDefinition(
                node_key=node,
                kind=RESEARCH_KINDS[node],
                depends_on=depends_on,
                stage_type=stage,
                artifact_target=f"research_{node}",
                max_attempts=3,
            )
            for node, stage, depends_on in _RESEARCH_GRAPH
        ]
        return [*steps, *analysis_step_definitions()] if analysis_enabled else steps
    raise UnknownWorkflowType(workflow_type)
