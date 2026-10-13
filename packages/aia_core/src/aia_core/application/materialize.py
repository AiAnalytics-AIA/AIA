"""Asking for a materialized dimension: the checks, and the request a run is made from (P4d2).

A researcher asks, from a study of the client the dimension is for (owner, 2026-10-12: a run
lives under a study and is charged to it; the child is the client's, usable by all of its
studies). :func:`prepare_materialization` refuses anything that cannot become a child before
anything is enqueued, and returns a :class:`MaterializationRequest` frozen to:

* the **owner**: the study's organization and client, from the scope, never an argument (M5);
* the **base**: LIVE as it stands now, recorded; a retry keeps it, never re-chooses it;
* the **definition**, by its hash.

Its :attr:`~MaterializationRequest.child_key` is the owner, the base and the definition: one
child, from any of the client's studies. The run's :attr:`~MaterializationRequest.idempotency_key`
is that child's key within the study, so asking again finds the same run.

The checks read the base version's kept dictionary and build the policy the loader builds
(``shared_version_policy``); no respondent row is read. The materialize step (P4d3) asks the
same question of the loaded population before it derives anything.

:func:`start_materialization` enqueues the request as a ``population_materialize`` run under
the study's population project (``projects.owner = study_population``, created on first use),
recording LIVE's binding as the run's population.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any, Final

from sqlalchemy.orm import Session

from ..domain.pipeline import ProjectType
from ..domain.population import (
    CZ_LIVE,
    MATERIALIZE_PROJECT_OWNER,
    DatasetVersion,
    MaterializedKind,
    PopulationBinding,
    PopulationImportContract,
    VersionOwner,
    target_met,
)
from ..domain.population.czech import CZ_SYNTHETIC_V17
from ..domain.population.definition import DimensionDefinition
from ..domain.population.policy import FieldUse
from ..domain.scope import Permission, StudyContext
from ..domain.workflow_templates import POPULATION_MATERIALIZE
from ..infrastructure.population_repository import PopulationRegistryRepository
from ..infrastructure.repositories import ProjectRepository
from ..infrastructure.workflow_repository import WorkflowNotFound, WorkflowRepository
from .population import live_binding
from .population_characteristics import shared_version_policy
from .workflows import StartedRun, start_workflow

__all__ = [
    "MATERIALIZE_KEY_PREFIX",
    "ChildOutcome",
    "MaterializationNotFound",
    "MaterializationRefused",
    "MaterializationRequest",
    "child_outcome",
    "materialization_run",
    "materialization_runs",
    "prepare_materialization",
    "start_materialization",
]

#: Every materialize run's idempotency key starts with this.
MATERIALIZE_KEY_PREFIX: Final = "population_materialize"


class MaterializationNotFound(LookupError):
    """No materialize run with this id in the Study in scope."""


class MaterializationRefused(Exception):
    """The request cannot become a child; ``reason`` names why. Nothing was enqueued."""

    def __init__(self, message: str, *, reason: str) -> None:
        super().__init__(message)
        self.reason = reason


@dataclass(frozen=True, slots=True)
class MaterializationRequest:
    """What a materialize run is made from, checked and frozen."""

    definition: DimensionDefinition
    owner: VersionOwner
    #: The study the run lives under and is charged to.
    study_id: str
    #: LIVE as it stood when asked: the base the child extends, recorded by the run.
    base: PopulationBinding

    @property
    def child_key(self) -> str:
        """The owner, the base and the definition: the one child they make, from any study.

        The child itself is deduplicated by its owner-qualified version id and the write-once
        store; this names it for a reader.
        """
        material = "\n".join(
            (
                self.owner.organization_id,
                self.owner.client_id,
                self.base.version_id,
                self.definition.sha256,
            )
        )
        return hashlib.sha256(material.encode("utf-8")).hexdigest()

    @property
    def idempotency_key(self) -> str:
        """The run's key: the child's, within this study.

        A run's key is unique across every study but looked up within one
        (``WorkflowRepository.find_run_by_idempotency_key``), so a sibling study asking for the
        same child starts its own run, which finds the child already made.
        """
        return f"{MATERIALIZE_KEY_PREFIX}:{self.study_id}:{self.child_key}"

    def step_input(self) -> dict[str, Any]:
        """What the materialize step is given: everything it needs, nothing it could re-choose."""
        return {
            "definition": self.definition.payload(),
            "definition_sha256": self.definition.sha256,
            "owner": {
                "organization_id": self.owner.organization_id,
                "client_id": self.owner.client_id,
            },
            "base_version_id": self.base.version_id,
        }


def prepare_materialization(
    session: Session,
    scope: StudyContext,
    *,
    definition: DimensionDefinition,
    contract: PopulationImportContract = CZ_SYNTHETIC_V17,
    population_id: str = CZ_LIVE,
) -> MaterializationRequest:
    """Check ``definition`` against the base version and freeze the request, or refuse.

    Refused (:class:`MaterializationRefused`) when the scope may not run work or the study is
    closed (``ScopeDenied``, as every start), when LIVE is not established, when the base
    keeps no dictionary, when the dimension's name is already a field of the base, and for any
    predictor the base does not have or its policy does not allow to build a persona.
    """
    scope.require(Permission.RUN_WORKFLOW)
    scope.require_open_study()
    base = live_binding(session, contract=contract, population_id=population_id)
    if base is None:
        raise MaterializationRefused(
            f"{population_id} is not established; there is no base to extend",
            reason="population_not_established",
        )
    version = PopulationRegistryRepository(session).visible_version(
        base.version_id, organization_id=scope.organization_id
    )
    if version is None or not version.shared:
        raise MaterializationRefused(
            f"{base.version_id} is not a shared version", reason="base_not_shared"
        )
    kept = shared_version_policy(session, contract=contract, version=version)
    if kept is None:
        raise MaterializationRefused(
            f"{version.label} keeps no dictionary; its fields cannot be checked",
            reason="dictionary_not_kept",
        )
    dictionary, policy = kept
    if definition.dimension_id in policy.entries or definition.dimension_id in dictionary.fields:
        raise MaterializationRefused(
            f"{definition.dimension_id} is already a field of {version.label}",
            reason="name_taken",
        )
    for predictor in definition.predictors:
        if predictor.field not in policy.entries:
            raise MaterializationRefused(
                f"predictor {predictor.field} is not a field of {version.label}",
                reason="predictor_unknown",
            )
        decision = policy.decide(predictor.field, FieldUse.PERSONA_CONSTRUCTION)
        if not decision.allowed:
            raise MaterializationRefused(
                f"predictor {predictor.field} may not build a persona ({decision.reason})",
                reason="predictor_not_permitted",
            )
    return MaterializationRequest(
        definition=definition,
        owner=VersionOwner(organization_id=scope.organization_id, client_id=scope.client_id),
        study_id=scope.study_id,
        base=base,
    )


def _existing_population_project(session: Session, scope: StudyContext) -> str | None:
    projects = ProjectRepository(session, scope, owner=MATERIALIZE_PROJECT_OWNER)
    found = projects.list_projects(limit=1).items
    return found[0].project_id if found else None


def _population_project(session: Session, scope: StudyContext) -> str:
    """The study's population project, created on first use; seen by no generic route."""
    existing = _existing_population_project(session, scope)
    if existing is not None:
        return existing
    projects = ProjectRepository(session, scope, owner=MATERIALIZE_PROJECT_OWNER)
    project, _ = projects.create(
        title="Population materializations",
        project_type=ProjectType.RESEARCH,
        content={},
        created_by=scope.actor_id,
        reason="population_materialize",
    )
    return project.project_id


def start_materialization(
    session: Session, scope: StudyContext, request: MaterializationRequest
) -> StartedRun:
    """Enqueue ``request`` as a ``population_materialize`` run, or find the one already made.

    Only from the study the request was prepared in. The run records the base as its
    population, so the step loads exactly what was checked and a retry never re-chooses it.
    """
    if request.study_id != scope.study_id:
        raise MaterializationRefused(
            "a request is started in the study it was checked in", reason="other_study"
        )
    scope.require(Permission.RUN_WORKFLOW)
    scope.require_open_study()
    return start_workflow(
        session,
        scope,
        project_id=_population_project(session, scope),
        workflow_type=POPULATION_MATERIALIZE,
        idempotency_key=request.idempotency_key,
        metadata={
            "definition_sha256": request.definition.sha256,
            "dimension_id": request.definition.dimension_id,
            "kind": request.definition.kind.value,
            "child_key": request.child_key,
            "base_version_id": request.base.version_id,
        },
        step_inputs={"materialize": request.step_input()},
        owner=MATERIALIZE_PROJECT_OWNER,
        population=request.base,
    )


def materialization_run(session: Session, scope: StudyContext, run_id: str) -> dict[str, Any]:
    """One materialize run of this Study, in full; :class:`MaterializationNotFound` otherwise.

    Found only through the Study: scope confines the run to it, and its population project and
    type confine it to its materializations.
    """
    project_id = _existing_population_project(session, scope)
    try:
        run = WorkflowRepository(session, scope).get_run(run_id)
    except WorkflowNotFound as exc:
        raise MaterializationNotFound(run_id) from exc
    if (
        project_id is None
        or run["project_id"] != project_id
        or run["workflow_type"] != POPULATION_MATERIALIZE
    ):
        raise MaterializationNotFound(run_id)
    return run


def materialization_runs(
    session: Session, scope: StudyContext, *, limit: int = 20
) -> list[dict[str, Any]]:
    """This Study's materialize runs, newest first, without their steps."""
    project_id = _existing_population_project(session, scope)
    if project_id is None:
        return []
    return WorkflowRepository(session, scope).list_runs(
        project_id=project_id, limit=limit, workflow_type=POPULATION_MATERIALIZE
    )


@dataclass(frozen=True, slots=True)
class ChildOutcome:
    """What a materialized child adds and what its derivation reached (P4d4)."""

    dimension_id: str
    kind: MaterializedKind
    definition_sha256: str
    method: str
    target: float
    achieved: float
    #: Within :data:`~aia_core.domain.population.TARGET_TOLERANCE`; never presumed.
    target_met: bool
    usable_predictors: tuple[str, ...]


def child_outcome(session: Session, version: DatasetVersion) -> ChildOutcome | None:
    """A child's outcome from its stored extension and the record it was registered with.

    ``None`` for a shared version, or for a child whose record carries no outcome (nothing is
    reconstructed or guessed). The extension is re-hashed on read.
    """
    if version.shared or version.extension_sha256 is None:
        return None
    registry = PopulationRegistryRepository(session)
    extension = registry.extension(version.extension_sha256)
    record = (registry.validation_record(version.version_id) or {}).get("materialized")
    if extension is None or not isinstance(record, dict) or len(extension.fields) != 1:
        return None
    field = extension.fields[0]
    target, achieved = record.get("target"), record.get("achieved")
    if not isinstance(target, int | float) or not isinstance(achieved, int | float):
        return None
    return ChildOutcome(
        dimension_id=field.name,
        kind=field.kind,
        definition_sha256=field.definition_sha256,
        method=f"{field.method_id}@{field.method_version}",
        target=float(target),
        achieved=float(achieved),
        target_met=target_met(field.kind, float(target), float(achieved)),
        usable_predictors=tuple(str(p) for p in record.get("usable_predictors", ())),
    )
