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
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from sqlalchemy.orm import Session

from ..domain.population import (
    PopulationImportContract,
    UnknownDatasetVersion,
    VersionIntegrityError,
    content_sha256,
)
from ..domain.population.policy import FieldUse, build_field_policy
from ..domain.population.subpanels import BUILTIN_SUBPANELS, BuiltinSubpanel, check_subpanel
from ..infrastructure.population_parser import parse_dictionary
from ..infrastructure.population_repository import PopulationRegistryRepository

__all__ = [
    "FieldCharacteristics",
    "SubpanelCharacteristics",
    "UseAnswer",
    "VersionCharacteristics",
    "WeightCharacteristics",
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


def version_characteristics(
    session: Session, *, contract: PopulationImportContract, version_id: str
) -> VersionCharacteristics:
    """The characteristics of ``version_id``, from the dictionary it keeps."""
    registry = PopulationRegistryRepository(session)
    version = registry.get_version(version_id)
    if version is None or version.dataset_id != contract.dataset_id:
        raise UnknownDatasetVersion(f"unknown dataset version {version_id}")
    weights = _weights(contract)
    kept = registry.dictionary(version_id)
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
        )
    _, content = kept
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
    )
