"""Asking for a materialized dimension: the checks, and the request a run is made from (P4d2).

A researcher asks, from a study of the client the dimension is for (owner, 2026-10-12: a run
lives under a study and is charged to it; the child is the client's, usable by all of its
studies). :func:`prepare_materialization` refuses anything that cannot become a child before
anything is enqueued, and returns a :class:`MaterializationRequest` frozen to:

* the **owner**: the study's organization and client, from the scope, never an argument (M5);
* the **base**: LIVE as it stands now, recorded; a retry keeps it, never re-chooses it;
* the **definition**, by its hash.

Its :attr:`~MaterializationRequest.idempotency_key` is the owner, the base and the definition:
the same request again finds the same run, from any of the client's studies.

The checks read the base version's kept dictionary and build the policy the loader builds
(``shared_version_policy``); no respondent row is read. The materialize step (P4d3) asks the
same question of the loaded population before it derives anything.

The workflow template, its executor and the enqueue land together in P4d3: a step no worker
can claim is never added (``domain/workflow_templates.py``).
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any, Final

from sqlalchemy.orm import Session

from ..domain.population import (
    CZ_LIVE,
    PopulationBinding,
    PopulationImportContract,
    VersionOwner,
)
from ..domain.population.czech import CZ_SYNTHETIC_V17
from ..domain.population.definition import DimensionDefinition
from ..domain.population.policy import FieldUse
from ..domain.scope import Permission, StudyContext
from ..infrastructure.population_repository import PopulationRegistryRepository
from .population import live_binding
from .population_characteristics import shared_version_policy

__all__ = [
    "MATERIALIZE_KEY_PREFIX",
    "MaterializationRefused",
    "MaterializationRequest",
    "prepare_materialization",
]

#: Every materialize run's idempotency key starts with this.
MATERIALIZE_KEY_PREFIX: Final = "population_materialize"


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
    def idempotency_key(self) -> str:
        """The owner, the base and the definition: one run per such triple."""
        material = "\n".join(
            (
                self.owner.organization_id,
                self.owner.client_id,
                self.base.version_id,
                self.definition.sha256,
            )
        )
        digest = hashlib.sha256(material.encode("utf-8")).hexdigest()
        return f"{MATERIALIZE_KEY_PREFIX}:{digest}"

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
