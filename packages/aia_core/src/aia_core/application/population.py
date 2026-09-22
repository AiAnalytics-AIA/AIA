"""``PopulationRuntime`` -- the one way into the synthetic population.

Every operation on the population goes through this class: import, establish,
promote, resolve and load. It is the answer to R4 ("four independent
population-selection mechanisms") and F10 ("two loaders, two populations"): there
is one resolver, one loader, and a :class:`RuntimePopulation` can only be issued
here. ``make layer_check`` refuses an issuance anywhere else.

What it guarantees, each as a refusal rather than a degradation:

* **Import never promotes.** :meth:`import_version` registers a validated version
  and stops. Only :meth:`establish` and :meth:`promote_live` move a population, and
  both need an actor and a reason.
* **Lossless or rejected.** Every contract check runs; any failure rejects the whole
  bundle with every failure listed.
* **Lineage is fact.** A preserved version's parent comes from the contract, not the
  caller; any other version must name a registered parent.
* **Bytes are re-verified on every load.** A moved, truncated or swapped file fails
  its hash and is refused, never silently used (the reference's
  ``_resolve_registered_path`` rule).
* **No silent enrichment failure** (R1). The ANALYSIS view without a configured
  enricher, or with one that returns anything but exactly the declared fields,
  does not load.
* **No silent weight substitution** (R3, F11). See ``domain.population.weights``.
* **A run reads only the population it recorded.** :meth:`load_for_run` takes the
  binding from the run; there is no "resolve the current one instead" path.

Not here yet, deliberately: authorization for establish/promote (there is no
platform-administrator role in the scope model), companion-asset validation, and a
process-wide cache. See ``.planning/plans/done/population-version-foundation.md``.
"""

from __future__ import annotations

from collections import OrderedDict
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime
from typing import Protocol, runtime_checkable

from sqlalchemy.orm import Session

from ..domain.population import (
    DatasetVersion,
    EnrichmentFailed,
    ImportRejected,
    LineageError,
    ParsedPanel,
    Population,
    PopulationBinding,
    PopulationImportContract,
    PopulationKind,
    PopulationNotEstablished,
    PopulationSelector,
    PopulationView,
    RuntimePopulation,
    UnknownDatasetVersion,
    VersionIntegrityError,
    VersionStatus,
    WeightResolutionError,
    analysis_weights,
    content_sha256,
    dataset_version_id,
    plan_establish,
    plan_promotion,
    resolve_binding,
    resolve_weight_scheme,
    validate_import,
    version_status,
)
from ..infrastructure.population_parser import parse_dictionary, parse_panel
from ..infrastructure.population_repository import PopulationRegistryRepository
from ..infrastructure.population_source import PopulationAssetSource
from ..infrastructure.workflow_repository import WorkflowRepository

__all__ = ["Enricher", "PopulationRuntime"]

Cell = str | None


@runtime_checkable
class Enricher(Protocol):
    """Computes the declared enrichment fields from the source fields.

    The seven ``*_derived`` fields of the reference's
    ``audience_dimensions.enrich_panel`` are not recovered -- their logic lives in
    the withheld archive -- so production has no implementation yet and the
    ANALYSIS view refuses to load. That is the correct state, not a gap to paper
    over with a guess.
    """

    #: Identifies the derivation logic; recorded in the cache key.
    enricher_id: str

    def derive(self, panel: ParsedPanel) -> Mapping[str, Sequence[Cell]]:
        """Return exactly one text column per declared enrichment field."""
        ...


def _utcnow() -> datetime:
    return datetime.now(UTC)


class PopulationRuntime:
    """Import, establish, promote, resolve and load -- for one import contract."""

    def __init__(
        self,
        session: Session,
        *,
        contract: PopulationImportContract,
        source: PopulationAssetSource,
        enricher: Enricher | None = None,
        clock: Callable[[], datetime] = _utcnow,
        cache_size: int = 3,
    ) -> None:
        self._contract = contract
        self._source = source
        self._enricher = enricher
        self._clock = clock
        self._registry = PopulationRegistryRepository(session)
        self._cache: OrderedDict[tuple[str, ...], RuntimePopulation] = OrderedDict()
        self._cache_size = cache_size

    @property
    def contract(self) -> PopulationImportContract:
        """The contract this runtime judges and resolves against."""
        return self._contract

    # ----------------------------------------------------------------- import --

    def import_version(
        self,
        *,
        label: str,
        panel_location: str,
        dictionary_location: str,
        provenance: str,
        imported_by: str,
        parent_version_id: str | None = None,
    ) -> DatasetVersion:
        """Validate a bundle and register it as a new version. Never promotes.

        Idempotent for the same bytes under the same label: the existing version is
        returned. The same bytes under another label, or another label's bytes
        under this one, are refused.
        """
        contract = self._contract
        panel_bytes = self._source.read(panel_location)
        dictionary_bytes = self._source.read(dictionary_location)
        panel_sha = content_sha256(panel_bytes)

        existing = self._registry.version_by_sha(panel_sha)
        if existing is not None:
            if (existing.label, existing.contract_id) == (label, contract.contract_id):
                return existing
            raise ImportRejected(
                f"these bytes are already registered as {existing.label} ({existing.version_id})",
                failures=("identity.distinct_labels",),
            )
        taken = self._registry.version_by_label(contract.dataset_id, label)
        if taken is not None:
            raise ImportRejected(
                f"{label} already names {taken.content_sha256}; a label is never re-pointed",
                failures=("identity.label_taken",),
            )
        parent_id = self._lineage_parent(label, parent_version_id)

        panel = parse_panel(panel_bytes)
        dictionary = parse_dictionary(
            dictionary_bytes, field_column=contract.dictionary_field_column
        )
        report = validate_import(
            contract,
            label=label,
            panel_sha256=panel_sha,
            panel_byte_size=len(panel_bytes),
            dictionary_sha256=content_sha256(dictionary_bytes),
            dictionary=dictionary,
            panel=panel,
        )
        if not report.passed:
            raise ImportRejected(
                f"{label} failed {len(report.failures)} import checks", failures=report.failures
            )

        version = DatasetVersion(
            version_id=dataset_version_id(contract.dataset_id, panel_sha),
            dataset_id=contract.dataset_id,
            label=label,
            content_sha256=panel_sha,
            byte_size=len(panel_bytes),
            row_count=panel.row_count,
            column_count=len(panel.header),
            contract_id=contract.contract_id,
            dictionary_sha256=content_sha256(dictionary_bytes),
            field_names_sha256=contract.field_names_sha256,
            parent_version_id=parent_id,
            storage_location=panel_location,
            dictionary_location=dictionary_location,
            provenance=provenance,
            imported_at=self._clock(),
            imported_by=imported_by,
        )
        self._registry.insert_version(version, validation=report.as_record())
        return version

    def _lineage_parent(self, label: str, parent_version_id: str | None) -> str | None:
        contract = self._contract
        known = contract.known_version(label)
        if known is not None:
            if known.parent_label is None:
                if parent_version_id is not None:
                    raise LineageError(f"{label} is a lineage root; it has no parent")
                return None
            parent = self._registry.version_by_label(contract.dataset_id, known.parent_label)
            if parent is None:
                raise LineageError(f"{label} is built from {known.parent_label}; import that first")
            if parent_version_id is not None and parent_version_id != parent.version_id:
                raise LineageError(
                    f"{label}'s parent is {known.parent_label} ({parent.version_id}), "
                    f"not {parent_version_id}"
                )
            return parent.version_id
        if parent_version_id is None:
            raise LineageError(
                f"{label} is not a preserved version; it must name the version it was built from"
            )
        parent = self._registry.get_version(parent_version_id)
        if parent is None or parent.dataset_id != contract.dataset_id:
            raise LineageError(f"parent {parent_version_id} is not a registered version")
        return parent.version_id

    # ------------------------------------------------------ establish/promote --

    def establish(
        self,
        *,
        population_id: str,
        kind: PopulationKind,
        version_id: str,
        actor_id: str,
        reason: str,
    ) -> Population:
        """Create a population pointing at ``version_id``. Once per population."""
        dataset = self._contract.dataset_id
        version = self._registry.get_version(version_id)
        if version is None:
            raise UnknownDatasetVersion(f"unknown dataset version {version_id}")
        population, record = plan_establish(
            population_id=population_id,
            kind=kind,
            version=version,
            versions=self._registry.versions(dataset),
            populations=self._registry.populations(dataset),
            static_label=self._contract.static_reference_label,
            actor_id=actor_id,
            reason=reason,
            at=self._clock(),
        )
        self._registry.insert_population(population, record)
        return population

    def promote_live(
        self,
        *,
        population_id: str,
        target_version_id: str,
        expected_current_version_id: str,
        actor_id: str,
        reason: str,
    ) -> Population:
        """Explicitly move a LIVE population to ``target_version_id``.

        Compare-and-set twice over: the domain rule checks the caller's expected
        version against a locked read, and the repository's conditional update
        refuses if the pointer moved anyway.
        """
        dataset = self._contract.dataset_id
        population = self._registry.population(population_id, for_update=True)
        if population is None:
            raise PopulationNotEstablished(f"population {population_id} has not been established")
        promoted, record = plan_promotion(
            population=population,
            target_version_id=target_version_id,
            expected_current_version_id=expected_current_version_id,
            versions=self._registry.versions(dataset),
            populations=self._registry.populations(dataset),
            actor_id=actor_id,
            reason=reason,
            at=self._clock(),
        )
        self._registry.apply_promotion(promoted, record)
        return promoted

    def version_status(self, version_id: str) -> VersionStatus:
        """Where ``version_id`` stands, derived from the registry."""
        dataset = self._contract.dataset_id
        if self._registry.get_version(version_id) is None:
            raise UnknownDatasetVersion(f"unknown dataset version {version_id}")
        return version_status(
            version_id, self._registry.populations(dataset), self._registry.promotions(dataset)
        )

    # ---------------------------------------------------------------- resolve --

    def resolve(
        self,
        selector: PopulationSelector,
        *,
        view: PopulationView = PopulationView.ANALYSIS,
        weight_role: str | None = None,
    ) -> PopulationBinding:
        """Resolve a selector to the binding a run records. No fallback."""
        dataset = self._contract.dataset_id
        return resolve_binding(
            selector,
            contract=self._contract,
            versions=self._registry.versions(dataset),
            populations=self._registry.populations(dataset),
            promotions=self._registry.promotions(dataset),
            view=view,
            weight_role=weight_role,
            at=self._clock(),
        )

    # ------------------------------------------------------------------- load --

    def load_for_run(self, workflow: WorkflowRepository, run_id: str) -> RuntimePopulation:
        """Load exactly the population ``run_id`` recorded. The path for run steps."""
        return self.load(workflow.population_binding(run_id))

    def load(self, binding: PopulationBinding) -> RuntimePopulation:
        """Load the population a binding names, re-verifying everything first."""
        contract = self._contract
        version = self._registry.get_version(binding.version_id)
        if version is None:
            raise UnknownDatasetVersion(f"unknown dataset version {binding.version_id}")
        mismatched = [
            name
            for name, have, want in (
                ("content_sha256", binding.content_sha256, version.content_sha256),
                ("version_label", binding.version_label, version.label),
                ("dataset_id", binding.dataset_id, version.dataset_id),
                ("contract_id", binding.contract_id, version.contract_id),
                ("contract_id", binding.contract_id, contract.contract_id),
            )
            if have != want
        ]
        if mismatched:
            raise VersionIntegrityError(
                f"binding for {binding.version_id} disagrees with the registry on {mismatched}"
            )
        weight = resolve_weight_scheme(contract, binding.weight_role)
        if weight.column != binding.weight_column:
            raise WeightResolutionError(
                f"binding records {binding.weight_role} as {binding.weight_column}; "
                f"{contract.contract_id} declares {weight.column}",
                reason="weight_mismatch",
            )

        enricher_id = self._enricher.enricher_id if self._enricher is not None else ""
        key = (
            version.version_id,
            version.content_sha256,
            binding.view.value,
            weight.column,
            enricher_id,
        )
        cached = self._cache.get(key)
        if cached is not None:
            self._cache.move_to_end(key)
            return RuntimePopulation._issue(
                binding=binding,
                source_fields=cached.source_fields,
                derived_fields=cached.derived_fields,
                row_count=cached.row_count,
                columns=cached._columns,
                analysis_weight=cached._analysis_weight,
            )

        panel = self._verified_panel(version)
        columns: dict[str, tuple[Cell, ...]] = {
            name: panel.columns[position] for position, name in enumerate(panel.header)
        }
        derived: tuple[str, ...] = ()
        weights: tuple[float, ...] | None = None
        if binding.view is PopulationView.ANALYSIS:
            columns.update(self._enrich(panel))
            weights = analysis_weights(panel.column(weight.column), weight)
            derived = (*contract.enrichment_fields, contract.analysis_weight_field)

        population = RuntimePopulation._issue(
            binding=binding,
            source_fields=panel.header,
            derived_fields=tuple(d for d in contract.derived_fields if d.name in derived),
            row_count=panel.row_count,
            columns=columns,
            analysis_weight=weights,
        )
        self._cache[key] = population
        while len(self._cache) > self._cache_size:
            self._cache.popitem(last=False)
        return population

    def _verified_panel(self, version: DatasetVersion) -> ParsedPanel:
        panel_bytes = self._source.read(version.storage_location)
        if content_sha256(panel_bytes) != version.content_sha256:
            raise VersionIntegrityError(
                f"the bytes at {version.storage_location} are not {version.label} "
                f"({version.content_sha256}); refusing to load a swapped or altered file"
            )
        dictionary_bytes = self._source.read(version.dictionary_location)
        if content_sha256(dictionary_bytes) != version.dictionary_sha256:
            raise VersionIntegrityError(
                f"the dictionary at {version.dictionary_location} is not the one "
                f"{version.label} was imported with"
            )
        panel = parse_panel(panel_bytes)
        # Defence in depth: the contract is re-applied on every load, so a contract
        # tightened after import stops an old version loading rather than letting it
        # through on its historical report.
        report = validate_import(
            self._contract,
            label=version.label,
            panel_sha256=version.content_sha256,
            panel_byte_size=len(panel_bytes),
            dictionary_sha256=version.dictionary_sha256,
            dictionary=parse_dictionary(
                dictionary_bytes, field_column=self._contract.dictionary_field_column
            ),
            panel=panel,
        )
        if not report.passed:
            raise VersionIntegrityError(
                f"{version.label} no longer satisfies {self._contract.contract_id}: "
                + "; ".join(report.failures)
            )
        return panel

    def _enrich(self, panel: ParsedPanel) -> dict[str, tuple[Cell, ...]]:
        declared = self._contract.enrichment_fields
        if self._enricher is None:
            raise EnrichmentFailed(
                "the ANALYSIS view needs the enrichment fields "
                f"{list(declared)} and no enricher is configured; the population is not "
                "loadable unenriched"
            )
        try:
            produced = self._enricher.derive(panel)
        except Exception as exc:
            # Not swallowed: re-raised as the typed refusal, with the cause chained.
            raise EnrichmentFailed(f"enricher {self._enricher.enricher_id} failed: {exc}") from exc
        if set(produced) != set(declared):
            raise EnrichmentFailed(
                f"enricher {self._enricher.enricher_id} produced {sorted(produced)}; "
                f"the contract declares exactly {sorted(declared)}"
            )
        result: dict[str, tuple[Cell, ...]] = {}
        for name in declared:
            column = tuple(produced[name])
            if len(column) != panel.row_count:
                raise EnrichmentFailed(
                    f"{name} has {len(column)} values for {panel.row_count} rows"
                )
            if any(cell is not None and not isinstance(cell, str) for cell in column):
                raise EnrichmentFailed(f"{name} must be text or null, like every source field")
            result[name] = column
        return result
