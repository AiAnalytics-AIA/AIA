"""What a population version is made of, without a respondent row (population-operations P7c).

Společenská inteligence shows a researcher, for one dataset version:

- the contract's weights, with their roles and declared totals;
- the field blocks, and every field with its dictionary facts (block, source, evidence
  status, grade, recommended use, description, persona eligibility);
- for every field, the field policy's answer for each ``FieldUse``: allowed or refused, the
  reason, and the obligations;
- the 18 built-in subpanels, each checked against this version's policy.

All of it comes from the dictionary the version keeps (``population_version_dictionaries``,
P7a), re-hashed here against the version's ``dictionary_sha256`` before it is read. A
mismatch refuses (``VersionIntegrityError``), and the policy is built exactly as the loader
builds it (``build_field_policy`` with the contract's weight and derived fields). Nothing
here reads the asset source or the panel.

A version whose dictionary is not kept yet answers ``dictionary_kept=False``, with no
fields, and every subpanel check left unknown. It never answers "usable".

An owned child (population-operations P4c) is read only by its own organization; to any
other it is an unknown version. Its dictionary is its base's (``check_child_version``
requires the same hash), read from the child's own row or else its parent's, and re-hashed
either way. Its added fields follow the base's, each with the fixed policy of a
materialized field (``with_materialized_fields``), from its stored extension.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from sqlalchemy.orm import Session

from ..domain.population import (
    DatasetVersion,
    ParsedDictionary,
    PopulationImportContract,
    UnknownDatasetVersion,
    VersionIntegrityError,
    content_sha256,
)
from ..domain.population.materialized import with_materialized_fields
from ..domain.population.policy import FieldPolicy, FieldUse, build_field_policy
from ..domain.population.subpanels import BUILTIN_SUBPANELS, BuiltinSubpanel, check_subpanel
from ..infrastructure.population_parser import parse_dictionary
from ..infrastructure.population_repository import PopulationRegistryRepository

__all__ = [
    "FieldCharacteristics",
    "SubpanelCharacteristics",
    "UseAnswer",
    "VersionCharacteristics",
    "WeightCharacteristics",
    "shared_version_policy",
    "version_characteristics",
]


@dataclass(frozen=True, slots=True)
class UseAnswer:
    """The field policy's answer for one field and one use."""

    use: FieldUse
    allowed: bool
    reason: str
    obligations: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class FieldCharacteristics:
    """One field: what its dictionary row says, and what its policy permits."""

    field: str
    block: str
    source: str
    evidence_status: str
    provenance_class: str
    production_grade: str
    recommended_use: str
    #: The dictionary's description; empty for a runtime field without a dictionary row.
    description: str
    persona_eligible: bool
    is_weight: bool
    #: True for a runtime field (enrichment, analysis weight) with no dictionary row.
    derived: bool
    uses: tuple[UseAnswer, ...]
    #: True for a field an owned child adds: modelled values, its policy fixed (P4, M3).
    materialized: bool = False


@dataclass(frozen=True, slots=True)
class WeightCharacteristics:
    """One declared weight scheme of the contract."""

    role: str
    column: str
    is_default: bool
    expected_total: float | None
    tolerance: float | None


@dataclass(frozen=True, slots=True)
class SubpanelCharacteristics:
    """A built-in subpanel, and whether this version's policy lets its filter be used."""

    subpanel: BuiltinSubpanel
    #: ``None`` while the version's dictionary is not kept: unknown, never "usable".
    usable: bool | None
    reason: str | None


@dataclass(frozen=True, slots=True)
class VersionCharacteristics:
    """Everything Společenská inteligence shows about one version. No respondent row."""

    version_id: str
    label: str
    dictionary_sha256: str
    dictionary_kept: bool
    weights: tuple[WeightCharacteristics, ...]
    #: ``(block, field count)`` in the order blocks first appear.
    blocks: tuple[tuple[str, int], ...]
    fields: tuple[FieldCharacteristics, ...]
    subpanels: tuple[SubpanelCharacteristics, ...]
    #: Set on an owned child: the client it belongs to and its extension's hash.
    owner_client_id: str | None = None
    extension_sha256: str | None = None


def _weights(contract: PopulationImportContract) -> tuple[WeightCharacteristics, ...]:
    return tuple(
        WeightCharacteristics(
            role=w.role,
            column=w.column,
            is_default=w.role == contract.default_weight_role,
            expected_total=w.expected_total,
            tolerance=w.tolerance,
        )
        for w in contract.weight_schemes
    )


def _kept_policy(
    contract: PopulationImportContract, version: DatasetVersion, content: bytes
) -> tuple[ParsedDictionary, FieldPolicy]:
    """The kept dictionary, re-hashed against its pin, and the policy the loader builds."""
    if content_sha256(content) != version.dictionary_sha256:
        raise VersionIntegrityError(
            f"the dictionary kept for {version.label} does not hash to its pin"
        )
    dictionary = parse_dictionary(content, field_column=contract.dictionary_field_column)
    policy = build_field_policy(
        dictionary.rows,
        dictionary_sha256=version.dictionary_sha256,
        weight_columns=contract.weight_columns,
        derived_fields=contract.derived_policy_fields,
    )
    return dictionary, policy


def shared_version_policy(
    session: Session, *, contract: PopulationImportContract, version: DatasetVersion
) -> tuple[ParsedDictionary, FieldPolicy] | None:
    """A shared version's dictionary and field policy, from what it keeps; ``None`` if not kept.

    The same policy the loader builds (``build_field_policy`` with the contract's weight and
    derived fields), so a check made from it answers as the run's population would. Reads no
    respondent row. Refused (``VersionIntegrityError``) when the kept bytes do not hash to the
    version's pin.
    """
    if not version.shared:
        raise VersionIntegrityError(f"{version.version_id} is an owned version, not a shared one")
    kept = PopulationRegistryRepository(session).dictionary(version.version_id)
    return None if kept is None else _kept_policy(contract, version, kept[1])


def version_characteristics(
    session: Session,
    *,
    contract: PopulationImportContract,
    version_id: str,
    organization_id: str,
) -> VersionCharacteristics:
    """The characteristics of ``version_id`` as ``organization_id`` may read them."""
    registry = PopulationRegistryRepository(session)
    version = registry.visible_version(version_id, organization_id=organization_id)
    if version is None or version.dataset_id != contract.dataset_id:
        raise UnknownDatasetVersion(f"unknown dataset version {version_id}")
    owner_client_id = version.owner.client_id if version.owner is not None else None
    weights = _weights(contract)
    kept = registry.dictionary(version_id)
    if kept is None and not version.shared and version.parent_version_id is not None:
        kept = registry.dictionary(version.parent_version_id)
    if kept is None:
        return VersionCharacteristics(
            version_id=version.version_id,
            label=version.label,
            dictionary_sha256=version.dictionary_sha256,
            dictionary_kept=False,
            weights=weights,
            blocks=(),
            fields=(),
            subpanels=tuple(SubpanelCharacteristics(s, None, None) for s in BUILTIN_SUBPANELS),
            owner_client_id=owner_client_id,
            extension_sha256=version.extension_sha256,
        )
    dictionary, policy = _kept_policy(contract, version, kept[1])
    added: set[str] = set()
    if version.extension_sha256 is not None:
        extension = registry.extension(version.extension_sha256)
        if extension is None:
            raise VersionIntegrityError(f"{version.label} names an extension that is not stored")
        policy = with_materialized_fields(policy, extension)
        added = {f.name for f in extension.fields}
    descriptions = {
        str(row.get(contract.dictionary_field_column) or ""): (row.get("description") or "").strip()
        for row in dictionary.rows
    }
    derived = {name for name, _ in contract.derived_policy_fields}
    order = [*dictionary.fields, *(n for n in policy.entries if n not in descriptions)]
    fields: list[FieldCharacteristics] = []
    for name in order:
        entry = policy.entries[name]
        uses = []
        for use in FieldUse:
            decision = policy.decide(name, use)
            uses.append(
                UseAnswer(
                    use=use,
                    allowed=decision.allowed,
                    reason=decision.reason,
                    obligations=tuple(sorted(o.value for o in decision.obligations)),
                )
            )
        fields.append(
            FieldCharacteristics(
                field=name,
                block=entry.block,
                source=entry.source,
                evidence_status=entry.evidence_status,
                provenance_class=entry.provenance_class.value,
                production_grade=entry.production_grade,
                recommended_use=entry.recommended_use,
                description=descriptions.get(name, ""),
                persona_eligible=entry.persona_eligible,
                is_weight=entry.is_weight,
                derived=name in derived,
                uses=tuple(uses),
                materialized=name in added,
            )
        )
    counts = Counter(f.block for f in fields)
    blocks = tuple((block, counts[block]) for block in dict.fromkeys(f.block for f in fields))
    subpanels = []
    for subpanel in BUILTIN_SUBPANELS:
        check = check_subpanel(subpanel, policy)
        subpanels.append(SubpanelCharacteristics(subpanel, check.usable, check.reason))
    return VersionCharacteristics(
        version_id=version.version_id,
        label=version.label,
        dictionary_sha256=version.dictionary_sha256,
        dictionary_kept=True,
        weights=weights,
        blocks=blocks,
        fields=tuple(fields),
        subpanels=tuple(subpanels),
        owner_client_id=owner_client_id,
        extension_sha256=version.extension_sha256,
    )
