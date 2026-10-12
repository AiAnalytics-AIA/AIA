"""``population_materialize``: a client's dimension made into its owned child (P4d3).

The step the materialize service enqueues (``application/materialize.py``). It reads the
request its run was made from -- the definition by hash, the owner, the base -- and checks
that the base is the population the run recorded, so it derives over exactly what the request
was checked against. Then :meth:`PopulationRuntime.materialize_child` does the work inside the
one loader: the base verified, every predictor asked again of its policy, the values derived
(18.6.6's rule, P4b), the child written once to the population store and registered. It never
promotes.

Without a population store or the shared population's directory, the run **parks**
(``RUNTIME_UNAVAILABLE``): nothing is derived, written or substituted until the deployment
gives the worker both.

No model call and no money. Idempotent by construction: the child's bytes are deterministic,
its id is its content qualified by its owner, and the store writes once, so a retry at any
point finds what the first attempt made.
"""

from __future__ import annotations

from typing import Final

from aia_core.application.population import PopulationRuntime
from aia_core.domain.population import (
    PopulationImportContract,
    VersionOwner,
)
from aia_core.domain.population.czech import CZ_SYNTHETIC_V17
from aia_core.domain.population.definition import DefinitionRefused, DimensionDefinition
from aia_core.domain.population.derivation import DerivationRefused
from aia_core.domain.workflow import FailureClass
from aia_core.domain.workflow_templates import POPULATION_MATERIALIZE
from aia_core.infrastructure.population_source import PopulationAssetSource
from aia_core.infrastructure.population_store import RoutingPopulationSource, S3PopulationStore
from aia_worker.executor import Failed, StepContext, StepInput, StepOutcome, Succeeded

__all__ = ["KIND", "MaterializeExecutor"]

KIND: Final = POPULATION_MATERIALIZE

_PARKED_MESSAGE: Final = (
    "Úložiště populace pro materializované dimenze není v tomto prostředí nastaveno. Běh čeká; "
    "nic nebylo odvozeno, zapsáno ani nahrazeno."
)


class MaterializeExecutor:
    """Executes ``population_materialize`` steps."""

    def __init__(
        self,
        *,
        store: S3PopulationStore | None,
        shared: PopulationAssetSource | None,
        contract: PopulationImportContract = CZ_SYNTHETIC_V17,
    ) -> None:
        self._store = store
        self._shared = shared
        self._contract = contract

    def execute(self, step: StepInput, context: StepContext) -> StepOutcome:
        context.checkpoint()
        if self._store is None or self._shared is None:
            return Failed(
                FailureClass.RUNTIME_UNAVAILABLE,
                error={
                    "message": _PARKED_MESSAGE,
                    "reason": "population_store_unconfigured",
                    "store": self._store is not None,
                    "shared_population": self._shared is not None,
                },
            )
        payload = step.payload
        try:
            definition = DimensionDefinition.from_payload(payload.get("definition"))
        except DefinitionRefused as refused:
            return _refused(refused.reason, str(refused))
        if definition.sha256 != payload.get("definition_sha256"):
            return _refused("definition_changed", "the definition is not the one requested")
        owner_payload = payload.get("owner") or {}
        owner = VersionOwner(
            organization_id=str(owner_payload.get("organization_id", "")),
            client_id=str(owner_payload.get("client_id", "")),
        )
        scope = context.scope
        if (owner.organization_id, owner.client_id) != (scope.organization_id, scope.client_id):
            return _refused("owner_not_this_study", "the child's owner is not this study's client")
        base_version_id = str(payload.get("base_version_id", ""))

        with context.transaction() as (session, workflow):
            binding = workflow.population_binding(step.run_id)
            if binding.version_id != base_version_id:
                return _refused(
                    "base_not_recorded", "the base is not the population this run recorded"
                )
            runtime = PopulationRuntime(
                session,
                contract=self._contract,
                source=RoutingPopulationSource(self._shared, self._store),
            )
            try:
                child = runtime.materialize_child(
                    base_version_id=base_version_id,
                    definition=definition,
                    owner=owner,
                    store=self._store,
                    actor_id=scope.actor_id,
                )
            except DerivationRefused as refused:
                return _refused(refused.reason, str(refused))

        context.progress(
            "child registered" if child.created else "child found",
            version_id=child.version.version_id,
            target=child.target,
            achieved=child.achieved,
        )
        return Succeeded(
            output={
                "version_id": child.version.version_id,
                "label": child.version.label,
                "content_sha256": child.version.content_sha256,
                "storage_location": child.version.storage_location,
                "created": child.created,
                "target": child.target,
                "achieved": child.achieved,
                "usable_predictors": list(child.usable_predictors),
            }
        )


def _refused(reason: str, message: str) -> Failed:
    """A request the data does not support: permanent, never retried, said by name."""
    return Failed(FailureClass.SCHEMA_VIOLATION, error={"reason": reason, "message": message})
