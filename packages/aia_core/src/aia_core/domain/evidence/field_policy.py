"""Per-field evidence status and claim policy, derived from the field dictionary.

The reference's ``FIELD_DICTIONARY_v17_1.csv`` states, for each of the 400
population fields, what it is (``evidence_status``), how good it is
(``production_grade``) and what may be claimed from it (``recommended_use``, as
prose). The reference reads **none** of those columns at runtime
(methodology-ledger M02): a field marked *"never measured fact"* is not
structurally prevented from backing a client-facing measured claim.

This module makes that policy typed and enforceable:

* :func:`provenance_class_for`, :func:`claim_rules_for` and
  :func:`derive_eligibility` are an **exact** port of the reference derivation
  (``tools/build_field_policy.py`` in ``AiAnalytics-AIA/AIA-reference``), so the
  eligibility of every field matches the reference export bit for bit. The
  parity suite checks all 400.
* :class:`FieldPolicyBook` is the only way a gate learns a field's policy, and it
  fails closed: an undeclared field, an unknown evidence status, an unknown grade
  or a stored policy whose flags disagree with the re-derivation is refused.

The dictionary itself is **not** vendored. It is reference material bound to one
population version, supplied at runtime with that version and checked against
its SHA-256 (see ``.planning/plans/evidence-governance-foundation.md``).
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Final

__all__ = [
    "ClaimRule",
    "EvidenceStatus",
    "FieldEligibility",
    "FieldPolicy",
    "FieldPolicyBook",
    "FieldPolicyError",
    "FieldPolicyInconsistent",
    "FieldUse",
    "ProductionGrade",
    "ProvenanceClass",
    "UndeclaredField",
    "claim_rules_for",
    "derive_eligibility",
    "derive_field_policy",
    "mandated_weight_scheme",
    "provenance_class_for",
]


class EvidenceStatus(StrEnum):
    """The 22 evidence roles the dictionary declares. Verbatim; persisted; never renamed.

    A status outside this set is not "unclassified" -- it is a dictionary this
    code has never seen, and a book containing one is refused.
    """

    POPULATION_ANCHOR = "POPULATION_ANCHOR"
    CANONICAL_CORE = "CANONICAL_CORE"
    MEASURED_CORE_PIAAC = "MEASURED_CORE_PIAAC"
    HYBRID_MEASURED_PIAAC_OR_MODELED = "HYBRID_MEASURED_PIAAC_OR_MODELED"
    MATCHED_WHOLE_BLOCK = "MATCHED_WHOLE_BLOCK"
    MATCHED_WHOLE_BLOCK_CANONICAL = "MATCHED_WHOLE_BLOCK_CANONICAL"
    MATCHED_POLITICS_CANONICAL = "MATCHED_POLITICS_CANONICAL"
    DERIVED_TRANSPARENT = "DERIVED_TRANSPARENT"
    DERIVED_QC = "DERIVED_QC"
    CALIBRATED_MODELED = "CALIBRATED_MODELED"
    CALIBRATED_MODELED_BINARY = "CALIBRATED_MODELED_BINARY"
    CALIBRATED_MODELED_COMPOSITE = "CALIBRATED_MODELED_COMPOSITE"
    CALIBRATED_BENCHMARK = "CALIBRATED_BENCHMARK"
    CALIBRATED_CZ_BENCHMARK = "CALIBRATED_CZ_BENCHMARK"
    CALIBRATED_CZ_BENCHMARK_WITH_MEASURED_GUARD = "CALIBRATED_CZ_BENCHMARK_WITH_MEASURED_GUARD"
    CALIBRATED_ONLINE_SAMPLE = "CALIBRATED_ONLINE_SAMPLE"
    MODELED_MARKETING_PRIOR = "MODELED_MARKETING_PRIOR"
    MODELED_VALUE_PROXY = "MODELED_VALUE_PROXY"
    MODELED_METADATA = "MODELED_METADATA"
    PROVENANCE_OR_CORE = "PROVENANCE_OR_CORE"
    NEW_WEIGHT = "NEW_WEIGHT"
    BENCHMARK_WEIGHT = "BENCHMARK_WEIGHT"


class ProvenanceClass(StrEnum):
    """Coarse observed / matched / modelled class of an evidence status."""

    OBSERVED = "OBSERVED"
    DONOR_MATCHED = "DONOR_MATCHED"
    DERIVED = "DERIVED"
    CALIBRATED = "CALIBRATED"
    MODELLED = "MODELLED"
    HYBRID = "HYBRID"
    PROVENANCE = "PROVENANCE"
    UNCLASSIFIED = "UNCLASSIFIED"


class ProductionGrade(StrEnum):
    """Dictionary production grades, verbatim. Only 10 of 400 fields are ``A``."""

    A = "A"
    B = "B"
    B_WEIGHTED = "B_WEIGHTED"
    C = "C"
    C_RAW_B_WEIGHTED = "C_RAW/B_WEIGHTED"
    D = "D"
    T = "T"


class ClaimRule(StrEnum):
    """Machine-checkable claim restrictions extracted from ``recommended_use`` prose."""

    NEVER_MEASURED_FACT = "NEVER_MEASURED_FACT"
    NEVER_DIRECT_SCHWARTZ = "NEVER_DIRECT_SCHWARTZ"
    PERSON_VALUE_MODELED = "PERSON_VALUE_MODELED"
    AUDIT_ONLY = "AUDIT_ONLY"
    AGGREGATE_ONLY = "AGGREGATE_ONLY"
    REQUIRES_SCOPE = "REQUIRES_SCOPE"
    REQUIRES_MODELED_DISCLOSURE = "REQUIRES_MODELED_DISCLOSURE"
    HISTORICAL_OR_EXPLORATORY = "HISTORICAL_OR_EXPLORATORY"
    SPECIFIED_WEIGHT_REQUIRED = "SPECIFIED_WEIGHT_REQUIRED"


class FieldUse(StrEnum):
    """The uses a field can be eligible for."""

    ANALYSIS = "analysis"
    CLIENT_FACING_MEASURED_CLAIM = "client_facing_measured_claim"
    FILTERING = "filtering"
    SIMULATION = "simulation"
    PERSONA_CONSTRUCTION = "persona_construction"
    WEIGHTING = "weighting"


# Order matters: it is the order the reference lists rules in, and a field's
# ``claim_rules`` is compared as a list by the parity suite.
_CLAIM_RULE_PATTERNS: Final[tuple[tuple[ClaimRule, re.Pattern[str]], ...]] = (
    (ClaimRule.NEVER_MEASURED_FACT, re.compile(r"never measured fact", re.I)),
    (ClaimRule.NEVER_DIRECT_SCHWARTZ, re.compile(r"never claim direct schwartz", re.I)),
    (
        ClaimRule.PERSON_VALUE_MODELED,
        re.compile(
            r"(person value is modeled|individual value modeled|modeled at person level)", re.I
        ),
    ),
    (ClaimRule.AUDIT_ONLY, re.compile(r"^AUDIT_ONLY$|audit.only|technical/provenance only", re.I)),
    (ClaimRule.AGGREGATE_ONLY, re.compile(r"(aggregate|segmentation)", re.I)),
    (ClaimRule.REQUIRES_SCOPE, re.compile(r"WITH_SCOPE", re.I)),
    (ClaimRule.REQUIRES_MODELED_DISCLOSURE, re.compile(r"modeled.value disclosure", re.I)),
    (ClaimRule.HISTORICAL_OR_EXPLORATORY, re.compile(r"HISTORICAL_OR_EXPLORATORY", re.I)),
    (ClaimRule.SPECIFIED_WEIGHT_REQUIRED, re.compile(r"use vaha_\w+", re.I)),
)

_MANDATED_WEIGHT: Final = re.compile(r"use (vaha_\w+)", re.I)
_WEIGHT_FIELD: Final = re.compile(r"^vaha_")

# Provenance classes whose values are not measurements of the person.
_NOT_MEASURED: Final = frozenset({ProvenanceClass.MODELLED, ProvenanceClass.UNCLASSIFIED})
_SIMULATION_INPUTS: Final = frozenset(
    {
        ProvenanceClass.MODELLED,
        ProvenanceClass.CALIBRATED,
        ProvenanceClass.DERIVED,
        ProvenanceClass.HYBRID,
    }
)


def provenance_class_for(evidence_status: str) -> ProvenanceClass:
    """Classify an evidence status. Exact port of the reference derivation."""
    s = evidence_status.upper()
    if s.startswith("MEASURED") or s in {"CANONICAL_CORE", "POPULATION_ANCHOR"}:
        return ProvenanceClass.OBSERVED
    if s.startswith("MATCHED"):
        return ProvenanceClass.DONOR_MATCHED
    if s.startswith("DERIVED"):
        return ProvenanceClass.DERIVED
    if s.startswith("CALIBRATED"):
        return ProvenanceClass.CALIBRATED
    if s.startswith("MODELED"):
        return ProvenanceClass.MODELLED
    if s.startswith("HYBRID"):
        return ProvenanceClass.HYBRID
    if s.startswith("PROVENANCE"):
        return ProvenanceClass.PROVENANCE
    return ProvenanceClass.UNCLASSIFIED


def claim_rules_for(recommended_use: str) -> tuple[ClaimRule, ...]:
    """Extract claim rules from the verbatim ``recommended_use``, in reference order."""
    return tuple(rule for rule, pattern in _CLAIM_RULE_PATTERNS if pattern.search(recommended_use))


def mandated_weight_scheme(recommended_use: str) -> str | None:
    """The weight scheme a ``SPECIFIED_WEIGHT_REQUIRED`` field names, or None."""
    match = _MANDATED_WEIGHT.search(recommended_use)
    return match.group(1) if match else None


@dataclass(frozen=True, slots=True)
class FieldEligibility:
    """What a field may be used for. Derived, never hand-set."""

    analysis: bool
    client_facing_measured_claim: bool
    filtering: bool
    simulation: bool
    persona_construction: bool
    weighting: bool

    def permits(self, use: FieldUse) -> bool:
        return bool(getattr(self, use.value))

    def as_dict(self) -> dict[str, bool]:
        return {use.value: self.permits(use) for use in FieldUse}


def derive_eligibility(
    field: str,
    provenance: ProvenanceClass,
    rules: Iterable[ClaimRule],
    recommended_use: str,
    persona_eligible: bool,
) -> FieldEligibility:
    """Derive eligibility from the verbatim policy. Exact port of the reference derivation."""
    rule_set = frozenset(rules)
    audit_only = ClaimRule.AUDIT_ONLY in rule_set or recommended_use.upper() == "AUDIT_ONLY"
    never_fact = ClaimRule.NEVER_MEASURED_FACT in rule_set
    return FieldEligibility(
        analysis=not audit_only,
        client_facing_measured_claim=not (audit_only or never_fact or provenance in _NOT_MEASURED),
        filtering=not audit_only,
        simulation=provenance in _SIMULATION_INPUTS or not audit_only,
        persona_construction=persona_eligible and not audit_only,
        weighting=bool(_WEIGHT_FIELD.match(field)),
    )


@dataclass(frozen=True, slots=True)
class FieldPolicy:
    """The complete, typed policy of one population field."""

    field: str
    block: str
    source: str
    evidence_status: EvidenceStatus
    provenance_class: ProvenanceClass
    production_grade: ProductionGrade
    recommended_use_verbatim: str
    description: str
    persona_eligible: bool
    claim_rules: tuple[ClaimRule, ...]
    eligibility: FieldEligibility
    mandated_weight_scheme: str | None

    def has(self, rule: ClaimRule) -> bool:
        return rule in self.claim_rules


class FieldPolicyError(ValueError):
    """A policy source cannot be turned into a trustworthy book. Loading stops."""


class FieldPolicyInconsistent(FieldPolicyError):
    """A stored policy's derived flags disagree with its own verbatim text."""

    def __init__(self, mismatches: Mapping[str, tuple[str, ...]]) -> None:
        self.mismatches = dict(mismatches)
        shown = ", ".join(f"{f} ({'/'.join(k)})" for f, k in list(self.mismatches.items())[:10])
        super().__init__(
            f"{len(self.mismatches)} field(s) disagree with their re-derived policy: {shown}"
        )


class UndeclaredField(LookupError):
    """A field has no dictionary entry, so it has no epistemic status at all."""

    def __init__(self, field: str, *, known_runtime_column: bool) -> None:
        self.field = field
        self.known_runtime_column = known_runtime_column
        why = (
            "a runtime column with no dictionary entry"
            if known_runtime_column
            else "not in the field dictionary"
        )
        super().__init__(f"{field!r} is {why}; it carries no evidence status or claim rule")


def _parse_enum[E: StrEnum](kind: type[E], raw: object, field: str, what: str) -> E:
    try:
        return kind(str(raw).strip())
    except ValueError:
        raise FieldPolicyError(f"field {field!r}: unknown {what} {raw!r}") from None


def derive_field_policy(
    *,
    field: str,
    block: str,
    source: str,
    evidence_status: str,
    production_grade: str,
    recommended_use: str,
    description: str,
    persona_eligible: bool,
) -> FieldPolicy:
    """Build one field's policy from the dictionary's verbatim columns."""
    field = field.strip()
    if not field:
        raise FieldPolicyError("a dictionary row has no field name")
    use = recommended_use.strip()
    status = _parse_enum(EvidenceStatus, evidence_status, field, "evidence_status")
    grade = _parse_enum(ProductionGrade, production_grade, field, "production_grade")
    provenance = provenance_class_for(status.value)
    rules = claim_rules_for(use)
    return FieldPolicy(
        field=field,
        block=block.strip(),
        source=source.strip(),
        evidence_status=status,
        provenance_class=provenance,
        production_grade=grade,
        recommended_use_verbatim=use,
        description=description.strip(),
        persona_eligible=persona_eligible,
        claim_rules=rules,
        eligibility=derive_eligibility(field, provenance, rules, use, persona_eligible),
        mandated_weight_scheme=mandated_weight_scheme(use),
    )


@dataclass(frozen=True, slots=True)
class FieldPolicyBook:
    """Every declared field's policy, bound to the dictionary it came from.

    The only lookup that gates use is :meth:`get`, which raises
    :class:`UndeclaredField` rather than returning a permissive default.
    """

    source_sha256: str
    fields: Mapping[str, FieldPolicy]
    undeclared_runtime_columns: frozenset[str] = frozenset()

    def __post_init__(self) -> None:
        if not re.fullmatch(r"[0-9a-f]{64}", self.source_sha256):
            raise FieldPolicyError("a field policy book must name its dictionary's SHA-256")
        if not self.fields:
            raise FieldPolicyError("a field policy book with no fields permits nothing")

    def __contains__(self, field: object) -> bool:
        return field in self.fields

    def __len__(self) -> int:
        return len(self.fields)

    def get(self, field: str) -> FieldPolicy:
        try:
            return self.fields[field]
        except KeyError:
            raise UndeclaredField(
                field, known_runtime_column=field in self.undeclared_runtime_columns
            ) from None

    @classmethod
    def from_dictionary_rows(
        cls,
        rows: Iterable[Mapping[str, str]],
        *,
        source_sha256: str,
        runtime_columns: Iterable[str] = (),
    ) -> FieldPolicyBook:
        """Build from raw ``FIELD_DICTIONARY`` CSV rows (``persona_eligible`` is ``yes``/``no``)."""
        fields: dict[str, FieldPolicy] = {}
        for row in rows:
            policy = derive_field_policy(
                field=row.get("field") or "",
                block=row.get("block") or "",
                source=row.get("source") or "",
                evidence_status=row.get("evidence_status") or "",
                production_grade=row.get("production_grade") or "",
                recommended_use=row.get("recommended_use") or "",
                description=row.get("description") or "",
                persona_eligible=(row.get("persona_eligible") or "").strip().lower() == "yes",
            )
            if policy.field in fields:
                raise FieldPolicyError(f"field {policy.field!r} is declared twice")
            fields[policy.field] = policy
        extra = frozenset(runtime_columns) - fields.keys()
        return cls(source_sha256, fields, extra)

    @classmethod
    def from_policy_document(cls, document: Mapping[str, Any]) -> FieldPolicyBook:
        """Load the machine-readable policy export, re-deriving and checking every field.

        The stored ``provenance_class``, ``claim_rules`` and ``eligibility`` are
        recomputed from the verbatim text. Any disagreement refuses the whole
        document: a hand-edited flag is exactly how a claim gets widened.
        """
        try:
            sha = str(document["source_sha256"])
            entries = list(document["fields"])
            declared = int(document["declared_field_count"])
        except (KeyError, TypeError, ValueError) as exc:
            raise FieldPolicyError(f"not a field policy document: {exc}") from None
        if declared != len(entries):
            raise FieldPolicyError(
                f"declared_field_count is {declared} but {len(entries)} fields are present"
            )

        fields: dict[str, FieldPolicy] = {}
        mismatches: dict[str, tuple[str, ...]] = {}
        for entry in entries:
            if not isinstance(entry, Mapping):
                raise FieldPolicyError("a field entry is not an object")
            persona = entry.get("persona_eligible")
            if not isinstance(persona, bool):
                raise FieldPolicyError(f"field {entry.get('field')!r}: persona_eligible not a bool")
            policy = derive_field_policy(
                field=str(entry.get("field") or ""),
                block=str(entry.get("block") or ""),
                source=str(entry.get("source") or ""),
                evidence_status=str(entry.get("evidence_status") or ""),
                production_grade=str(entry.get("production_grade") or ""),
                recommended_use=str(entry.get("recommended_use_verbatim") or ""),
                description=str(entry.get("description") or ""),
                persona_eligible=persona,
            )
            if policy.field in fields:
                raise FieldPolicyError(f"field {policy.field!r} is declared twice")
            wrong = tuple(
                key
                for key, stored, derived in (
                    ("provenance_class", entry.get("provenance_class"), policy.provenance_class),
                    (
                        "claim_rules",
                        entry.get("claim_rules"),
                        [r.value for r in policy.claim_rules],
                    ),
                    ("eligibility", entry.get("eligibility"), policy.eligibility.as_dict()),
                )
                if stored != derived
            )
            if wrong:
                mismatches[policy.field] = wrong
            fields[policy.field] = policy
        if mismatches:
            raise FieldPolicyInconsistent(mismatches)

        extra = frozenset(
            str(item["field"])
            for item in document.get("runtime_columns_without_dictionary_entry") or ()
            if isinstance(item, Mapping) and "field" in item
        )
        return cls(sha, fields, extra - fields.keys())
