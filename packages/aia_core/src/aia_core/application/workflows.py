"""Starting and reading workflow runs, from an authorised study scope.

The API validates a request and calls :func:`start_workflow`; the develop seed
and smoke command call the same function. Nothing here decides what a workflow
contains -- that is :mod:`aia_core.domain.workflow_templates` -- and nothing here
executes a step: a run is rows in PostgreSQL until a worker claims it.

Idempotency is by ``(workflow_type, project, revision)`` unless the caller
supplies its own key. Re-submitting the snapshot of a revision that already has
one therefore returns the existing run rather than spending a second execution,
which is what makes a browser's double click, or an at-least-once trigger, safe.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from aia_core.domain.pipeline import fingerprint
from aia_core.domain.scope import StudyContext
from aia_core.domain.workflow_templates import (
    WORKFLOW_TYPES,
    UnknownWorkflowType,
    steps_for_workflow,
)
from aia_core.infrastructure.repositories import ProjectRepository
from aia_core.infrastructure.workflow_repository import WorkflowRepository

__all__ = ["StartedRun", "start_workflow"]


@dataclass(frozen=True, slots=True)
class StartedRun:
    """What :func:`start_workflow` returns."""

    run_id: str
    project_id: str
    project_revision: int
    workflow_type: str
    #: False when an existing run satisfied the request and nothing was created.
    created: bool
    run: dict[str, Any]


def start_workflow(
    session: Session,
    scope: StudyContext,
    *,
    project_id: str,
    workflow_type: str,
    idempotency_key: str | None = None,
    metadata: dict[str, Any] | None = None,
    revision: int | None = None,
    step_inputs: dict[str, dict[str, Any]] | None = None,
    owner: str | None = None,
    analysis_enabled: bool = False,
    sociomapping_enabled: bool = False,
) -> StartedRun:
    """Create a run of ``workflow_type`` against a revision of the project.

    ``revision`` pins the run to one immutable revision (a research run names its
    Design Revision, ADR 0016); ``None`` means the project's current revision.
    ``step_inputs`` are recorded on the steps by node key, for their executors.
    ``owner`` reaches an owned project (``projects.owner``): a research run names
    the design repository's owner; every other caller runs ordinary projects only.

    Raises :class:`~aia_core.domain.workflow_templates.UnknownWorkflowType` for a
    type with no template, :class:`~aia_core.infrastructure.repositories.ProjectNotFound`
    for a project outside the scope, and :class:`~aia_core.domain.scope.ScopeDenied`
    when the scope lacks ``RUN_WORKFLOW`` or the study is closed -- each before
    anything is written.
    """
    if workflow_type not in WORKFLOW_TYPES:
        raise UnknownWorkflowType(workflow_type)

    projects = ProjectRepository(session, scope, owner=owner)
    project = projects.get(project_id)
    revision = project.current_revision if revision is None else revision
    content = projects.content(project_id, revision)
    steps = steps_for_workflow(
        workflow_type,
        project_type=project.project_type,
        analysis_enabled=analysis_enabled,
        sociomapping_enabled=sociomapping_enabled,
    )

    # The step's input fingerprint is the content it will describe, so a re-run
    # after a crash finds the artifact the first run stored and uploads nothing.
    content_fingerprint = fingerprint(content)
    key = idempotency_key or f"{workflow_type}:{project_id}:{revision}"

    workflows = WorkflowRepository(session, scope)
    existing = workflows.find_run_by_idempotency_key(key)
    run_id = workflows.create_run(
        project_id=project_id,
        project_revision=revision,
        workflow_type=workflow_type,
        steps=steps,
        idempotency_key=key,
        metadata={"content_fingerprint": content_fingerprint, **(metadata or {})},
        fingerprints={s.node_key: content_fingerprint for s in steps},
        step_inputs=step_inputs,
    )
    return StartedRun(
        run_id=run_id,
        project_id=project_id,
        project_revision=revision,
        workflow_type=workflow_type,
        created=existing is None,
        run=workflows.get_run(run_id),
    )
