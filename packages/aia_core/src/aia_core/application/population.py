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

Establish and promote need a population-operator context
(``aia_core.domain.population.authority``), issued only by
``PopulationAuthority`` from trusted configuration; the actor they record is the
operator's verified user id. Not here yet, deliberately: a process-wide cache.
"""

from __future__ import annotations

import json
from collections import OrderedDict
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from typing import Any, Protocol, runtime_checkable

from sqlalchemy.orm import Session

from ..domain.population import (
    FIELD_POLICY_VERSION,
    CompanionKind,
    CompanionReport,
    CompanionSet,
    CompanionsIncomplete,
    DatasetVersion,
    EnrichmentFailed,
    ImportRejected,
    JointState,
    JointStatus,
    LineageError,
    MaterializedField,
    MaterializedKind,
    OwnedVersionNotShared,
    ParsedDictionary,
    ParsedPanel,
    Population,
    PopulationBinding,
    PopulationContractExtension,
    PopulationError,
    PopulationImportContract,
    PopulationKind,
    PopulationNotEstablished,
    PopulationOperatorContext,
    PopulationPermission,
    PopulationSelector,
    PopulationView,
    ResolutionMode,
    RuntimePopulation,
    UnknownDatasetVersion,
    VersionIntegrityError,
    VersionOwner,
    VersionStatus,
    WeightResolutionError,
    analysis_weights,
    build_field_policy,
    check_child_version,
    companion_set_sha256,
    content_sha256,
    dataset_version_id,
    evaluate_joint_certificate,
    field_names_fingerprint,
    owned_version_id,
    plan_establish,
    plan_promotion,
    require_operator,
    require_runtime_eligible,
    resolve_binding,
    resolve_weight_scheme,
    validate_companions,
    validate_import,
    version_status,
    with_materialized_fields,
)
from ..domain.population.audience_catalogue import AUDIENCE_CATALOGUE_VERSION, catalogue_of
from ..domain.population.definition import DimensionDefinition
from ..domain.population.derivation import (
    DERIVATION_METHOD_ID,
    DERIVATION_METHOD_VERSION,
    DerivationRefused,
    derive_dimension,
    numeric_column,
)
from ..domain.population.policy import FieldUse
from ..infrastructure.population_parser import parse_dictionary, parse_panel, write_panel
from ..infrastructure.population_repository import PopulationRegistryRepository
from ..infrastructure.population_source import PopulationAssetMissing, PopulationAssetSource
from ..infrastructure.workflow_repository import WorkflowRepository

__all__ = [
    "ChildStore",
    "Enricher",
    "MaterializedChild",
    "PopulationRuntime",
    "child_binding",
    "kept_audience_catalogue",
    "live_binding",
]

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


class ChildStore(Protocol):
    """Where a materialized child's bytes are written once (``S3PopulationStore``)."""

    def put_once(self, key: str, data: bytes) -> str:
        """Write ``data`` at ``key`` unless it is already there; return its location."""
        ...


@dataclass(frozen=True, slots=True)
class MaterializedChild:
    """A registered child, and what its derivation asked for and achieved."""

    version: DatasetVersion
    #: False when the same owner's same bytes were already registered (a retry).
    created: bool
    target: float
    achieved: float
    usable_predictors: tuple[str, ...]


def _child_outcome(outcome: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "target": float(outcome["target"]),
        "achieved": float(outcome["achieved"]),
        "usable_predictors": tuple(outcome["usable_predictors"]),
    }


def _holds(kind: MaterializedKind, cell: str | None) -> bool:
    """Whether ``cell`` is a value a materialized field of ``kind`` may hold (never missing)."""
    if cell is None:
        return False
    if kind is MaterializedKind.BINARY:
        return cell in ("0", "1")
    try:
        value = float(cell)
    except ValueError:
        return False
    return 1.0 <= value <= 10.0


def _refuse_owned(version: DatasetVersion) -> None:
    """Refuse an owned child before anything else is checked (P4c, M5).

    The registry's planning reads shared versions only, so without this an owned child
    would be refused as unknown, or for its companions, rather than for what it is.
    """
    if not version.shared:
        raise OwnedVersionNotShared(
            f"{version.version_id} belongs to one organization; STATIC and LIVE are shared"
        )


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
        companion_locations: Mapping[str, str] | None = None,
    ) -> DatasetVersion:
        """Validate a bundle and register it as a new version. Never promotes.

        Idempotent for the same bytes under the same label: the existing version is
        returned. The same bytes under another label, or another label's bytes
        under this one, are refused.

        ``companion_locations`` (asset id -> location) validates the companion set
        with the panel, in one decision: a failing companion rejects the whole
        import. Omitted, the version is registered without companions and is not
        usable until :meth:`attach_companions` records a valid set.
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
        companions: CompanionReport | None = None
        if companion_locations is not None or not contract.companions:
            companions = self._validate_companions(
                label=label,
                panel=panel,
                panel_sha256=panel_sha,
                locations=companion_locations or {},
            )
        failures = (*report.failures, *(companions.failures if companions else ()))
        if failures:
            raise ImportRejected(f"{label} failed {len(failures)} import checks", failures=failures)
        report = replace(report, companions_validated=companions is not None)

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
        self._registry.insert_dictionary(
            version.version_id,
            sha256=version.dictionary_sha256,
            content=dictionary_bytes,
            recorded_at=version.imported_at,
            recorded_by=imported_by,
        )
        if companions is not None:
            self._registry.insert_companion_set(
                version.version_id,
                specs=contract.companions,
                report=companions,
                locations=companion_locations or {},
                attached_by=imported_by,
                attached_at=version.imported_at,
            )
        return version

    def record_dictionary(self, version_id: str, *, recorded_by: str) -> bool:
        """Keep the dictionary of a version imported before dictionaries were kept.

        Reads the version's own ``dictionary_location`` and stores the bytes only when
        they hash to the ``dictionary_sha256`` the version was imported with: nothing is
        judged, so nobody's permission is asked. ``False`` when the version already has
        its dictionary, ``True`` when this stored it. Never reads the panel.
        """
        version = self._registry.get_version(version_id)
        if version is None or version.dataset_id != self._contract.dataset_id:
            raise UnknownDatasetVersion(f"unknown dataset version {version_id}")
        if self._registry.dictionary(version_id) is not None:
            return False
        content = self._source.read(version.dictionary_location)
        if content_sha256(content) != version.dictionary_sha256:
            raise VersionIntegrityError(
                f"the dictionary at {version.dictionary_location!r} is not the one "
                f"{version.label} was imported with"
            )
        self._registry.insert_dictionary(
            version_id,
            sha256=version.dictionary_sha256,
            content=content,
            recorded_at=self._clock(),
            recorded_by=recorded_by,
        )
        return True

    def record_audience_catalogue(self, version_id: str, *, recorded_by: str) -> bool:
        """Compute and keep a version's audience factor catalogue (panel-grounded 6b).

        Loads the version's ANALYSIS view exactly as a run would (every hash re-verified, the
        enricher's derived dimensions attached), computes
        :func:`~..domain.population.audience_catalogue.catalogue_of` and keeps it as canonical
        JSON with its SHA-256. ``False`` when this catalogue version is already kept for it,
        ``True`` when this stored it. Nothing is judged, so nobody's permission is asked; the
        catalogue holds counts and ranges, never a row.
        """
        if self._registry.get_version(version_id) is None:
            raise UnknownDatasetVersion(f"unknown dataset version {version_id}")
        if self._registry.audience_catalogue(version_id, AUDIENCE_CATALOGUE_VERSION) is not None:
            return False
        population = self.load(
            self.resolve(PopulationSelector.pinned(version_id), view=PopulationView.ANALYSIS)
        )
        content = json.dumps(
            catalogue_of(population), ensure_ascii=False, sort_keys=True, separators=(",", ":")
        )
        self._registry.insert_audience_catalogue(
            version_id,
            catalogue_version=AUDIENCE_CATALOGUE_VERSION,
            sha256=content_sha256(content.encode("utf-8")),
            content=content,
            recorded_at=self._clock(),
            recorded_by=recorded_by,
        )
        return True

    def audience_catalogue(self, version_id: str) -> dict[str, Any] | None:
        """A version's kept audience catalogue, re-hashed on read, or ``None`` when none is."""
        return kept_audience_catalogue(self._registry, version_id)

    def attach_companions(
        self, *, version_id: str, companion_locations: Mapping[str, str], attached_by: str
    ) -> CompanionSet:
        """Validate and record the companion set of an already-registered version.

        Once per version: a set is never replaced, because a run already bound to
        this version recorded the set it was computed with.
        """
        version = self._registry.get_version(version_id)
        if version is None:
            raise UnknownDatasetVersion(f"unknown dataset version {version_id}")
        if self._registry.companion_set(version_id) is not None:
            raise PopulationError(
                f"{version_id} already has its companion set; a set is never replaced",
                reason="companions_already_attached",
            )
        panel, _ = self._verified_panel(version)
        report = self._validate_companions(
            label=version.label,
            panel=panel,
            panel_sha256=version.content_sha256,
            locations=companion_locations,
        )
        if not report.passed:
            raise ImportRejected(
                f"{version.label}'s companions failed {len(report.failures)} checks",
                failures=report.failures,
            )
        self._registry.insert_companion_set(
            version_id,
            specs=self._contract.companions,
            report=report,
            locations=companion_locations,
            attached_by=attached_by,
            attached_at=self._clock(),
        )
        attached = self._registry.companion_set(version_id)
        assert attached is not None  # just inserted in this unit of work
        return attached

    def _validate_companions(
        self,
        *,
        label: str,
        panel: ParsedPanel,
        panel_sha256: str,
        locations: Mapping[str, str],
    ) -> CompanionReport:
        contract = self._contract
        assets: dict[str, bytes] = {}
        for asset_id, location in locations.items():
            assets[asset_id] = self._source.read(location)
        return validate_companions(
            contract.companions,
            assets=assets,
            panel=panel,
            panel_sha256=panel_sha256,
            field_count=contract.field_count,
            joint_must_certify=label in contract.joint_certified_labels,
        )

    def _require_usable(self, version_id: str) -> None:
        """Refuse a version whose contract declares companions it does not have."""
        if self._contract.companions and self._registry.companion_set(version_id) is None:
            raise CompanionsIncomplete(
                f"{version_id} has no validated companion set; "
                f"{len(self._contract.companions)} companions are required before it is usable"
            )

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
        operator: PopulationOperatorContext,
        population_id: str,
        kind: PopulationKind,
        version_id: str,
        reason: str,
    ) -> Population:
        """Create a population pointing at ``version_id``. Once per population.

        Needs ``POPULATION_ESTABLISH``; the recorded actor is the operator's verified
        user id, never an argument.
        """
        actor_id = require_operator(operator, PopulationPermission.POPULATION_ESTABLISH)
        dataset = self._contract.dataset_id
        version = self._registry.get_version(version_id)
        if version is None:
            raise UnknownDatasetVersion(f"unknown dataset version {version_id}")
        _refuse_owned(version)
        self._require_usable(version_id)
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
        operator: PopulationOperatorContext,
        population_id: str,
        target_version_id: str,
        expected_current_version_id: str,
        reason: str,
    ) -> Population:
        """Explicitly move a LIVE population to ``target_version_id``.

        Needs ``POPULATION_PROMOTE``. Compare-and-set twice over: the domain rule
        checks the caller's expected version against a locked read, and the
        repository's conditional update refuses if the pointer moved anyway.
        """
        actor_id = require_operator(operator, PopulationPermission.POPULATION_PROMOTE)
        dataset = self._contract.dataset_id
        population = self._registry.population(population_id, for_update=True)
        if population is None:
            raise PopulationNotEstablished(f"population {population_id} has not been established")
        target = self._registry.get_version(target_version_id)
        if target is not None:
            _refuse_owned(target)
            self._require_usable(target_version_id)
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
        versions = self._registry.versions(dataset)
        target = selector.version_id
        if target is None:
            population = self._registry.population(selector.population_id or "")
            target = population.current_version_id if population is not None else None
        if target is not None and target in versions:
            self._require_usable(target)
        companions = self._registry.companion_set(target) if target is not None else None
        return resolve_binding(
            selector,
            contract=self._contract,
            versions=versions,
            populations=self._registry.populations(dataset),
            promotions=self._registry.promotions(dataset),
            view=view,
            weight_role=weight_role,
            at=self._clock(),
            companion_set_sha256=(
                companions.set_sha256 if companions is not None else companion_set_sha256({})
            ),
            joint_state=companions.joint_state if companions is not None else JointState.MISSING,
        )

    def resolve_child(
        self,
        version_id: str,
        *,
        organization_id: str,
        view: PopulationView = PopulationView.ANALYSIS,
        weight_role: str | None = None,
    ) -> PopulationBinding:
        """Resolve an owned child a study selected to the binding its run records (P4e).

        Only ``organization_id``'s own child resolves; any other answers as an unknown version.
        A child is never a population's version, so it is eligible when its shared base is (a
        version a run may be resolved against) and its base is usable. The binding pins the
        child (``PINNED``); its companions and certificate are the base's.
        """
        version = self._registry.visible_version(version_id, organization_id=organization_id)
        if version is None or version.shared or version.dataset_id != self._contract.dataset_id:
            raise UnknownDatasetVersion(f"unknown dataset version {version_id}")
        if version.contract_id != self._contract.contract_id:
            raise PopulationError(
                f"{version_id} was made under {version.contract_id}, not "
                f"{self._contract.contract_id}",
                reason="contract_mismatch",
            )
        base = self._joint_version(version)
        dataset = self._contract.dataset_id
        require_runtime_eligible(
            base.version_id,
            version_status(
                base.version_id,
                self._registry.populations(dataset),
                self._registry.promotions(dataset),
            ),
        )
        self._require_usable(base.version_id)
        companions = self._registry.companion_set(base.version_id)
        weight = resolve_weight_scheme(self._contract, weight_role)
        return PopulationBinding(
            dataset_id=version.dataset_id,
            version_id=version.version_id,
            version_label=version.label,
            content_sha256=version.content_sha256,
            contract_id=self._contract.contract_id,
            population_id=None,
            resolution=ResolutionMode.PINNED,
            weight_role=weight.role,
            weight_column=weight.column,
            view=view,
            resolved_at=self._clock(),
            dictionary_sha256=version.dictionary_sha256,
            field_policy_version=FIELD_POLICY_VERSION,
            companion_set_sha256=(
                companions.set_sha256 if companions is not None else companion_set_sha256({})
            ),
            joint_state=companions.joint_state if companions is not None else JointState.MISSING,
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
        # An owned child carries its shared base's companions and certificate: the certificate
        # is bound to the base panel's hash, and the child's base columns are verified equal to
        # the base's on every load (``_verified_child``).
        joint_version = self._joint_version(version)
        companions = self._registry.companion_set(joint_version.version_id)
        if contract.companions and companions is None:
            raise CompanionsIncomplete(f"{version.version_id} has no validated companion set")
        recorded_set = companions.set_sha256 if companions is not None else companion_set_sha256({})
        recorded_joint = companions.joint_state if companions is not None else JointState.MISSING
        policy_drift = [
            name
            for name, have, want in (
                ("dictionary_sha256", binding.dictionary_sha256, version.dictionary_sha256),
                ("field_policy_version", binding.field_policy_version, FIELD_POLICY_VERSION),
                ("companion_set_sha256", binding.companion_set_sha256, recorded_set),
                ("joint_state", binding.joint_state, recorded_joint),
            )
            if have != want
        ]
        if policy_drift:
            # The run would be computed under different claim rules, or a different
            # certificate, than it recorded. Refuse rather than silently re-rule it.
            raise VersionIntegrityError(
                f"binding for {binding.version_id} no longer matches on {policy_drift}"
            )

        enricher_id = self._enricher.enricher_id if self._enricher is not None else ""
        key = (
            version.version_id,
            version.content_sha256,
            binding.view.value,
            weight.column,
            enricher_id,
            recorded_set,
            FIELD_POLICY_VERSION,
        )
        cached = self._cache.get(key)
        if cached is not None:
            self._cache.move_to_end(key)
            return RuntimePopulation._issue(
                binding=binding,
                source_fields=cached.source_fields,
                derived_fields=cached.derived_fields,
                row_count=cached.row_count,
                field_policy=cached.field_policy,
                joint_status=cached.joint_status,
                columns=cached._columns,
                analysis_weight=cached._analysis_weight,
                companions=cached._companions,
                joint_certificate=cached.joint_certificate,
            )

        extension: PopulationContractExtension | None = None
        if version.shared:
            panel, dictionary = self._verified_panel(version)
        else:
            panel, dictionary, extension = self._verified_child(version)
        joint, companion_bytes = self._verified_joint(joint_version, companions)
        certificate = next(
            (
                companion_bytes[spec.asset_id]
                for spec in self._contract.companions
                if spec.kind is CompanionKind.CORE_JOINT_STATUS and spec.asset_id in companion_bytes
            ),
            None,
        )
        policy = build_field_policy(
            dictionary.rows,
            dictionary_sha256=version.dictionary_sha256,
            weight_columns=contract.weight_columns,
            derived_fields=contract.derived_policy_fields,
        )
        if extension is not None:
            policy = with_materialized_fields(policy, extension)
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
            field_policy=policy,
            joint_status=joint,
            columns=columns,
            analysis_weight=weights,
            companions=companion_bytes,
            joint_certificate=(
                None if certificate is None else (certificate, joint_version.content_sha256)
            ),
        )
        self._cache[key] = population
        while len(self._cache) > self._cache_size:
            self._cache.popitem(last=False)
        return population

    # ------------------------------------------------------------ materialize --

    def materialize_child(
        self,
        *,
        base_version_id: str,
        definition: DimensionDefinition,
        owner: VersionOwner,
        store: ChildStore,
        actor_id: str,
    ) -> MaterializedChild:
        """Derive ``definition`` over the base and register the owned child. Never promotes.

        The base is read and verified as every load is (bytes and dictionary against their
        pins, the contract re-applied). Before anything is derived, every predictor is asked
        again of the base's policy (``PERSONA_CONSTRUCTION``) and the name must be free, so a
        policy that moved since the request was checked refuses here (``DerivationRefused``).
        The child is the base's columns in order plus the new one, written once to ``store``
        under its content hash, then checked against the base (``check_child_version``) and
        registered with its extension. The same owner's same bytes are one version: a retry
        finds the child, a retry after the write but before registration finds the object.
        """
        base = self._registry.get_version(base_version_id)
        if base is None:
            raise UnknownDatasetVersion(f"unknown dataset version {base_version_id}")
        if not base.shared:
            raise OwnedVersionNotShared(f"{base_version_id} is owned; a child extends a shared one")
        panel, dictionary = self._verified_panel(base)
        policy = build_field_policy(
            dictionary.rows,
            dictionary_sha256=base.dictionary_sha256,
            weight_columns=self._contract.weight_columns,
            derived_fields=self._contract.derived_policy_fields,
        )
        name = definition.dimension_id
        if name in policy.entries or name in panel.header:
            raise DerivationRefused(
                f"{name} is already a field of {base.label}", reason="name_taken"
            )
        for predictor in definition.predictors:
            decision = policy.decide(predictor.field, FieldUse.PERSONA_CONSTRUCTION)
            if not decision.allowed:
                raise DerivationRefused(
                    f"predictor {predictor.field} may not build a persona ({decision.reason})",
                    reason="predictor_not_permitted",
                )
        numeric: dict[str, Sequence[float | None]] = {}
        for predictor in definition.predictors:
            if predictor.field in panel.header:
                values = numeric_column(panel.column(predictor.field))
                if values is not None:
                    numeric[predictor.field] = values
        weight = resolve_weight_scheme(self._contract, self._contract.default_weight_role)
        weights = numeric_column(panel.column(weight.column)) or [None] * panel.row_count
        row_ids = tuple(str(cell or "") for cell in panel.column(self._contract.primary_key))
        derived = derive_dimension(
            row_ids, numeric, weights, dimension_id=name, spec=definition.evidence_spec()
        )
        if derived.kind is MaterializedKind.BINARY:
            cells: tuple[str, ...] = tuple("1" if v else "0" for v in derived.values)
        else:
            cells = tuple(format(v, ".2f") for v in derived.values)
        data = write_panel((*panel.header, name), (*panel.columns, cells))
        sha = content_sha256(data)

        extension = PopulationContractExtension(
            base_contract_id=base.contract_id,
            base_field_names_sha256=base.field_names_sha256,
            base_dictionary_sha256=base.dictionary_sha256,
            fields=(
                MaterializedField(
                    name=name,
                    kind=definition.kind,
                    definition_sha256=definition.sha256,
                    method_id=DERIVATION_METHOD_ID,
                    method_version=DERIVATION_METHOD_VERSION,
                ),
            ),
        )
        outcome = {
            "definition_sha256": definition.sha256,
            "method": f"{DERIVATION_METHOD_ID}@{DERIVATION_METHOD_VERSION}",
            "target": derived.target,
            "achieved": derived.achieved,
            "usable_predictors": [p.column for p in derived.usable],
        }
        version_id = owned_version_id(base.dataset_id, sha, owner)
        existing = self._registry.get_version(version_id)
        if existing is not None:
            return MaterializedChild(version=existing, created=False, **_child_outcome(outcome))
        location = store.put_once(f"{base.dataset_id}/{sha}.csv.gz", data)
        child = DatasetVersion(
            version_id=version_id,
            dataset_id=base.dataset_id,
            label=f"{base.label}+{name}@{definition.sha256[:12]}",
            content_sha256=sha,
            byte_size=len(data),
            row_count=panel.row_count,
            column_count=len(panel.header) + 1,
            contract_id=base.contract_id,
            dictionary_sha256=base.dictionary_sha256,
            field_names_sha256=field_names_fingerprint(extension.field_names(panel.header)),
            parent_version_id=base.version_id,
            storage_location=location,
            dictionary_location=base.dictionary_location,
            provenance=(
                f"materialized {name} v{definition.version} over {base.label} by "
                f"{DERIVATION_METHOD_ID}@{DERIVATION_METHOD_VERSION}; every value modelled"
            ),
            imported_at=self._clock(),
            imported_by=actor_id,
            owner=owner,
            extension_sha256=extension.sha256,
        )
        check_child_version(
            base=base, child=child, extension=extension, base_field_names=panel.header
        )
        self._registry.insert_extension(extension, recorded_at=self._clock(), recorded_by=actor_id)
        self._registry.insert_version(child, validation={"materialized": outcome})
        return MaterializedChild(version=child, created=True, **_child_outcome(outcome))

    def _joint_version(self, version: DatasetVersion) -> DatasetVersion:
        """Whose companions and certificate apply: a child's shared base, else the version."""
        if version.shared:
            return version
        base = self._registry.get_version(version.parent_version_id or "")
        if base is None or not base.shared:
            raise VersionIntegrityError(f"{version.version_id} does not extend a shared version")
        return base

    def _verified_child(
        self, child: DatasetVersion
    ) -> tuple[ParsedPanel, ParsedDictionary, PopulationContractExtension]:
        """An owned child's panel, re-verified against its base and its extension.

        The base contract judges the base, read and verified as any load; the child's bytes
        must hash to their pin, the child must be exactly its base extended
        (``check_child_version``), every base column must be the base's cell for cell, and every
        added cell must be a value its kind holds. Anything else refuses the load.
        """
        base = self._joint_version(child)
        base_panel, dictionary = self._verified_panel(base)
        if child.extension_sha256 is None:  # pragma: no cover - an owned version names one
            raise VersionIntegrityError(f"{child.version_id} names no extension")
        extension = self._registry.extension(child.extension_sha256)
        if extension is None:
            raise VersionIntegrityError(f"{child.version_id} names an extension that is not stored")
        check_child_version(
            base=base, child=child, extension=extension, base_field_names=base_panel.header
        )
        data = self._source.read(child.storage_location)
        if content_sha256(data) != child.content_sha256:
            raise VersionIntegrityError(
                f"the bytes at {child.storage_location} are not {child.label}; refusing to load "
                "a swapped or altered child"
            )
        panel = parse_panel(data)
        width = len(base_panel.header)
        if (
            panel.header != extension.field_names(base_panel.header)
            or panel.row_count != base_panel.row_count
            or panel.columns[:width] != base_panel.columns
        ):
            raise VersionIntegrityError(
                f"{child.label} is not {base.label}'s rows and columns followed by its added fields"
            )
        for offset, added in enumerate(extension.fields):
            cells = panel.columns[width + offset]
            if not all(_holds(added.kind, cell) for cell in cells):
                raise VersionIntegrityError(
                    f"{child.label}: {added.name} holds a value a {added.kind.value} field cannot"
                )
        return panel, dictionary, extension

    def _verified_joint(
        self, version: DatasetVersion, companions: CompanionSet | None
    ) -> tuple[JointStatus, dict[str, bytes]]:
        """Re-verify every companion's bytes and re-evaluate the certificate.

        Returns the certificate's verdict and the verified bytes of every companion, which the
        loaded population hands out (``RuntimePopulation.companion``): one read, one check.
        """
        if companions is None:
            return (
                JointStatus.fallback(JointState.MISSING, "the contract declares no certificate"),
                {},
            )
        certificate: bytes | None = None
        verified: dict[str, bytes] = {}
        for spec in self._contract.companions:
            sha, location = companions.assets[spec.asset_id]
            data = self._source.read(location)
            if content_sha256(data) != sha:
                raise VersionIntegrityError(
                    f"companion {spec.asset_id} at {location} is not the one attached to "
                    f"{version.label}; refusing to load a swapped companion"
                )
            verified[spec.asset_id] = data
            if spec.kind is CompanionKind.CORE_JOINT_STATUS:
                certificate = data
        if certificate is None:
            return (
                JointStatus.fallback(JointState.MISSING, "the contract declares no certificate"),
                verified,
            )
        joint = evaluate_joint_certificate(certificate, panel_sha256=version.content_sha256)
        if joint.state is not companions.joint_state:
            raise VersionIntegrityError(
                f"{version.label}'s certificate now evaluates to {joint.state.value}, "
                f"not the recorded {companions.joint_state.value}"
            )
        return joint, verified

    def _verified_panel(self, version: DatasetVersion) -> tuple[ParsedPanel, ParsedDictionary]:
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
        dictionary = parse_dictionary(
            dictionary_bytes, field_column=self._contract.dictionary_field_column
        )
        # Defence in depth: the contract is re-applied on every load, so a contract
        # tightened after import stops an old version loading rather than letting it
        # through on its historical report.
        report = validate_import(
            self._contract,
            label=version.label,
            panel_sha256=version.content_sha256,
            panel_byte_size=len(panel_bytes),
            dictionary_sha256=version.dictionary_sha256,
            dictionary=dictionary,
            panel=panel,
        )
        if not report.passed:
            raise VersionIntegrityError(
                f"{version.label} no longer satisfies {self._contract.contract_id}: "
                + "; ".join(report.failures)
            )
        return panel, dictionary

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


class _ResolutionReadsNoAssets:
    """The asset source of a runtime that only resolves: any read is a defect, said so."""

    def read(self, location: str) -> bytes:
        raise PopulationAssetMissing(
            f"resolving a binding reads no population asset; {location!r} was asked for"
        )


def live_binding(
    session: Session,
    *,
    contract: PopulationImportContract,
    population_id: str,
    clock: Callable[[], datetime] = _utcnow,
) -> PopulationBinding | None:
    """The binding a new run records: ``population_id`` as it stands now, or ``None``.

    ``None`` only when that population has not been established -- no population yet is
    not a refusal, and the run records none (as every run did before population
    operations existed). Every other refusal (an unusable version, a contract mismatch)
    raises: a run never records a population it could not later load.

    Resolution reads the registry, never a panel; the runtime it builds refuses a read.
    """
    registry = PopulationRegistryRepository(session)
    if registry.population(population_id) is None:
        return None
    runtime = PopulationRuntime(
        session, contract=contract, source=_ResolutionReadsNoAssets(), clock=clock
    )
    return runtime.resolve(
        PopulationSelector.population(population_id), view=PopulationView.ANALYSIS
    )


def child_binding(
    session: Session,
    *,
    contract: PopulationImportContract,
    version_id: str,
    owner: VersionOwner,
    clock: Callable[[], datetime] = _utcnow,
) -> PopulationBinding:
    """The binding a run records when its study selects ``owner``'s child ``version_id`` (P4e2).

    A child is its client's (P4d): another client's child, even in the same organization, and
    any shared version answer as unknown (:class:`UnknownDatasetVersion`), as a scope miss
    does. Resolution reads the registry, never a panel; the run's load verifies the child
    against its base (P4e1).
    """
    version = PopulationRegistryRepository(session).visible_version(
        version_id, organization_id=owner.organization_id
    )
    if version is None or version.owner != owner:
        raise UnknownDatasetVersion(f"unknown dataset version {version_id}")
    runtime = PopulationRuntime(
        session, contract=contract, source=_ResolutionReadsNoAssets(), clock=clock
    )
    return runtime.resolve_child(version_id, organization_id=owner.organization_id)


def kept_audience_catalogue(
    registry: PopulationRegistryRepository, version_id: str
) -> dict[str, Any] | None:
    """The audience catalogue kept for ``version_id``, re-hashed on read; ``None`` if none is.

    Reads the kept JSON, never the panel; a catalogue that does not hash to what was
    recorded with it raises :class:`VersionIntegrityError`.
    """
    kept = registry.audience_catalogue(version_id, AUDIENCE_CATALOGUE_VERSION)
    if kept is None:
        return None
    sha256, content = kept
    if content_sha256(content.encode("utf-8")) != sha256:
        raise VersionIntegrityError(f"the audience catalogue of {version_id} does not hash")
    catalogue: dict[str, Any] = json.loads(content)
    return catalogue
