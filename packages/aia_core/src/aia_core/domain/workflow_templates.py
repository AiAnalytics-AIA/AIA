"""Workflow templates: the step graphs a run may be created from, by name.

A caller names a **workflow type**; the template says which steps that means.
Keeping the mapping here, in the domain, means the API cannot compose a DAG from
a request body and the worker cannot invent one -- both only ever see a
template's output, and the templates are tested like any other rule.

Today there is one template, ``develop_snapshot``: a single deterministic step
that records what a project's current revision looks like, as an artifact. It
exists to prove the deployed path browser -> API -> PostgreSQL -> worker ->
ArtifactStore -> browser with no model call (ADR 0009; the AI step follows the
gateway, ADR 0010). The research pipeline's 24-node graph lands as a second
template when its steps have executors.
"""

from __future__ import annotations

from typing import Final

from .pipeline import ProjectType, stage_ids
from .workflow import StepDefinition

__all__ = [
    "DEVELOP_SNAPSHOT",
    "WORKFLOW_TYPES",
    "UnknownWorkflowType",
    "steps_for_workflow",
]

#: The develop vertical slice: one deterministic step, no population, no model.
DEVELOP_SNAPSHOT: Final = "develop_snapshot"

#: Every workflow type a run may be created with. Closed: an unknown type is refused.
WORKFLOW_TYPES: Final[frozenset[str]] = frozenset({DEVELOP_SNAPSHOT})


class UnknownWorkflowType(LookupError):
    """The named workflow type has no template."""


def steps_for_workflow(workflow_type: str, *, project_type: ProjectType) -> list[StepDefinition]:
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
    raise UnknownWorkflowType(workflow_type)
