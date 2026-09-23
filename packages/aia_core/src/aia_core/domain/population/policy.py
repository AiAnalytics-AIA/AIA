"""Field policy as code: what each population field may be used for.

``FIELD_DICTIONARY_v17_1.csv`` carries the rules that keep the product honest --
*"behavioral prior / simulation modifier, never measured fact"*, *"simulation
prior; never claim direct Schwartz measurement"*, ``AUDIT_ONLY`` -- as prose, and
the reference enforced none of them (AIA-reference R5, methodology M02). Here they
are a closed, typed policy that answers one question deterministically:

    may field F be used for purpose U, and under which obligations?

**Closed tables, not pattern matching.** Each of the sixteen ``recommended_use``
phrases the dictionary contains is listed verbatim below with the claim rules it
carries and what it positively permits a client to be told. Each of the twenty-two
``evidence_status`` codes maps to a provenance class. A phrase, code, grade or
persona flag that is not in these tables is **unmapped**, and an unmapped field is
refused for every use. Import rejects a dictionary with any unmapped field, so a
reworded rule fails loudly instead of being read optimistically.

**Client-facing use needs positive support.** A field may back a client-facing
*measured* claim only when its phrase permits client claims, its evidence is
measured (observed, or donor-matched within its block), no rule forbids it and its
grade is not technical or ``D``. A client-facing *modelled* claim additionally
needs a phrase that permits one, and always carries the modelled-value disclosure.
Silence in the dictionary is a refusal, never a permission.

Internal uses (audience filtering, aggregate analysis, simulation) are allowed for
every non-audit field, as the reference allowed them; persona construction follows
``persona_eligible``. Weighting is allowed only for the contract's declared weight
columns.

The claim-rule extraction and provenance classification are reproduced exactly
from AIA-reference ``tools/build_field_policy.py``; the eligibility is deliberately
stricter than the flags that script derived, and
``tests/test_population_reference_parity.py`` enumerates every difference.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Final

from .errors import PopulationError

__all__ = [
    "EVIDENCE_STATUS_CLASS",
    "FIELD_POLICY_VERSION",
    "KNOWN_GRADES",
    "POLICY_COLUMNS",
    "RECOMMENDED_USE_POLICY",
    "ClaimRule",
    "ClientClaimPermit",
    "FieldPolicy",
    "FieldPolicyEntry",
    "FieldUse",
    "FieldUseRefused",
    "Obligation",
    "PhrasePolicy",
    "ProvenanceClass",
    "UsageDecision",
    "build_field_policy",
]

#: Identifies the mapping tables below. Recorded on every run binding, so a change
#: to what a phrase permits is attributable to the runs it applied to.
FIELD_POLICY_VERSION: Final = "field-policy/v1"


class ClaimRule(StrEnum):
    """Machine-checkable rules carried by ``recommended_use``. AIA-reference catalogue."""

    NEVER_MEASURED_FACT = "NEVER_MEASURED_FACT"
    NEVER_DIRECT_SCHWARTZ = "NEVER_DIRECT_SCHWARTZ"
    PERSON_VALUE_MODELED = "PERSON_VALUE_MODELED"
    AUDIT_ONLY = "AUDIT_ONLY"
    AGGREGATE_ONLY = "AGGREGATE_ONLY"
    REQUIRES_SCOPE = "REQUIRES_SCOPE"
    REQUIRES_MODELED_DISCLOSURE = "REQUIRES_MODELED_DISCLOSURE"
    HISTORICAL_OR_EXPLORATORY = "HISTORICAL_OR_EXPLORATORY"
    SPECIFIED_WEIGHT_REQUIRED = "SPECIFIED_WEIGHT_REQUIRED"


class ProvenanceClass(StrEnum):
    """Where a field's value comes from, from its ``evidence_status``."""

    OBSERVED = "OBSERVED"
    DONOR_MATCHED = "DONOR_MATCHED"
    DERIVED = "DERIVED"
    CALIBRATED = "CALIBRATED"
    MODELLED = "MODELLED"
    HYBRID = "HYBRID"
    PROVENANCE = "PROVENANCE"
    UNCLASSIFIED = "UNCLASSIFIED"

    @property
    def is_measured(self) -> bool:
        """True for a value measured on a person: observed, or donor-matched.

        A donor-matched value is a real measurement of a matched donor, and the
        joint certificate permits matched-block outputs; what it forbids --
        cross-block same-person claims -- is enforced on combinations, not here.
        Calibrated, modelled, hybrid ("measured or modelled"), derived and
        unclassified values are not measurements.
        """
        return self in (ProvenanceClass.OBSERVED, ProvenanceClass.DONOR_MATCHED)


class ClientClaimPermit(StrEnum):
    """What a ``recommended_use`` phrase positively permits a client to be told."""

    #: Nothing client-facing. Internal use only.
    NONE = "NONE"
    #: Measured claims (when the evidence is measured) or disclosed modelled claims.
    MEASURED_OR_MODELLED = "MEASURED_OR_MODELLED"
    #: Aggregate modelled claims with the modelled-value disclosure; never measured.
    MODELLED_AGGREGATE = "MODELLED_AGGREGATE"


class FieldUse(StrEnum):
    """The purposes a consumer asks about."""

    AUDIENCE_FILTERING = "AUDIENCE_FILTERING"
    PERSONA_CONSTRUCTION = "PERSONA_CONSTRUCTION"
    AGGREGATE_ANALYSIS = "AGGREGATE_ANALYSIS"
    SIMULATION = "SIMULATION"
    CLIENT_MEASURED_CLAIM = "CLIENT_MEASURED_CLAIM"
    CLIENT_MODELLED_CLAIM = "CLIENT_MODELLED_CLAIM"
    WEIGHTING = "WEIGHTING"

    @property
    def client_facing(self) -> bool:
        """True for a use whose output a client sees as a claim."""
        return self in (FieldUse.CLIENT_MEASURED_CLAIM, FieldUse.CLIENT_MODELLED_CLAIM)


class Obligation(StrEnum):
    """What a permitted use must also do. Consumers carry these to the output."""

    DISCLOSE_SCOPE = "DISCLOSE_SCOPE"
    DISCLOSE_MODELLED = "DISCLOSE_MODELLED"
    AGGREGATE_ONLY = "AGGREGATE_ONLY"
    USE_SPECIFIED_WEIGHT = "USE_SPECIFIED_WEIGHT"


@dataclass(frozen=True, slots=True)
class PhrasePolicy:
    """The policy one verbatim ``recommended_use`` phrase carries."""

    rules: frozenset[ClaimRule]
    client_permit: ClientClaimPermit


_R = ClaimRule
_P = ClientClaimPermit

#: Every ``recommended_use`` phrase in the v17 dictionary, verbatim. The rule sets
#: equal AIA-reference ``field-policy.json`` ``claim_rules`` field for field (parity
#: tier). The permits are this production system's reading: positive only where the
#: phrase names analysis or aggregate/segmentation output.
RECOMMENDED_USE_POLICY: Final[Mapping[str, PhrasePolicy]] = {
    "PERSONA_OR_ANALYSIS_WITH_SCOPE": PhrasePolicy(
        frozenset({_R.REQUIRES_SCOPE}), _P.MEASURED_OR_MODELLED
    ),
    "HISTORICAL_OR_EXPLORATORY": PhrasePolicy(frozenset({_R.HISTORICAL_OR_EXPLORATORY}), _P.NONE),
    "behavioral prior / simulation modifier, never measured fact": PhrasePolicy(
        frozenset({_R.NEVER_MEASURED_FACT}), _P.NONE
    ),
    "AUDIT_ONLY": PhrasePolicy(frozenset({_R.AUDIT_ONLY}), _P.NONE),
    "aggregate planning and persona background with modeled-value disclosure": PhrasePolicy(
        frozenset({_R.AGGREGATE_ONLY, _R.REQUIRES_MODELED_DISCLOSURE}), _P.MODELLED_AGGREGATE
    ),
    "simulation prior; never claim direct Schwartz measurement": PhrasePolicy(
        frozenset({_R.NEVER_DIRECT_SCHWARTZ}), _P.NONE
    ),
    "segmentation/aggregate; individual value modeled": PhrasePolicy(
        frozenset({_R.PERSON_VALUE_MODELED, _R.AGGREGATE_ONLY}), _P.MODELLED_AGGREGATE
    ),
    "population segmentation / reach; person value is modeled, not measured": PhrasePolicy(
        frozenset({_R.PERSON_VALUE_MODELED, _R.AGGREGATE_ONLY}), _P.MODELLED_AGGREGATE
    ),
    "modeled context only": PhrasePolicy(frozenset(), _P.NONE),
    "platform reach/segmentation among internet users; modeled at person level": PhrasePolicy(
        frozenset({_R.PERSON_VALUE_MODELED, _R.AGGREGATE_ONLY}), _P.MODELLED_AGGREGATE
    ),
    "technical/provenance only": PhrasePolicy(frozenset({_R.AUDIT_ONLY}), _P.NONE),
    "persona/context with provenance": PhrasePolicy(frozenset(), _P.NONE),
    "individual simulation background; aggregate components benchmarked": PhrasePolicy(
        frozenset({_R.AGGREGATE_ONLY}), _P.MODELLED_AGGREGATE
    ),
    "audience selection; use vaha_strukturalni_2025": PhrasePolicy(
        frozenset({_R.SPECIFIED_WEIGHT_REQUIRED}), _P.NONE
    ),
    "provenance/confidence": PhrasePolicy(frozenset(), _P.NONE),
    "AUDIT_AND_PERSONA_CONFIDENCE": PhrasePolicy(frozenset(), _P.NONE),
}

_C = ProvenanceClass

#: Every ``evidence_status`` code in the v17 dictionary. Equal to the reference's
#: prefix classification for each (parity tier); listed exhaustively so that a new
#: code is unmapped rather than silently classified by its prefix.
EVIDENCE_STATUS_CLASS: Final[Mapping[str, ProvenanceClass]] = {
    "MEASURED_CORE_PIAAC": _C.OBSERVED,
    "CANONICAL_CORE": _C.OBSERVED,
    "POPULATION_ANCHOR": _C.OBSERVED,
    "MATCHED_WHOLE_BLOCK": _C.DONOR_MATCHED,
    "MATCHED_WHOLE_BLOCK_CANONICAL": _C.DONOR_MATCHED,
    "MATCHED_POLITICS_CANONICAL": _C.DONOR_MATCHED,
    "DERIVED_TRANSPARENT": _C.DERIVED,
    "DERIVED_QC": _C.DERIVED,
    "CALIBRATED_BENCHMARK": _C.CALIBRATED,
    "CALIBRATED_CZ_BENCHMARK": _C.CALIBRATED,
    "CALIBRATED_CZ_BENCHMARK_WITH_MEASURED_GUARD": _C.CALIBRATED,
    "CALIBRATED_MODELED": _C.CALIBRATED,
    "CALIBRATED_MODELED_BINARY": _C.CALIBRATED,
    "CALIBRATED_MODELED_COMPOSITE": _C.CALIBRATED,
    "CALIBRATED_ONLINE_SAMPLE": _C.CALIBRATED,
    "MODELED_MARKETING_PRIOR": _C.MODELLED,
    "MODELED_VALUE_PROXY": _C.MODELLED,
    "MODELED_METADATA": _C.MODELLED,
    "HYBRID_MEASURED_PIAAC_OR_MODELED": _C.HYBRID,
    "PROVENANCE_OR_CORE": _C.PROVENANCE,
    "NEW_WEIGHT": _C.UNCLASSIFIED,
    "BENCHMARK_WEIGHT": _C.UNCLASSIFIED,
}

#: Production grades in the v17 dictionary. ``T`` (technical) and ``D`` never back
#: a client-facing claim.
KNOWN_GRADES: Final = frozenset({"A", "B", "B_WEIGHTED", "C", "C_RAW/B_WEIGHTED", "D", "T"})
_CLIENT_BLOCKING_GRADES: Final = frozenset({"T", "D"})

# The dictionary columns the policy reads. A dictionary without them cannot state
# a policy and is refused at import.
POLICY_COLUMNS: Final = (
    "field",
    "block",
    "source",
    "evidence_status",
    "production_grade",
    "recommended_use",
    "persona_eligible",
)


class FieldUseRefused(PopulationError):
    """A field was asked to serve a use its policy does not permit."""

    reason = "field_use_refused"

    def __init__(self, decision: UsageDecision) -> None:
        super().__init__(
            f"{decision.field} may not be used for {decision.use.value}: {decision.reason}"
        )
        self.decision = decision


@dataclass(frozen=True, slots=True)
class UsageDecision:
    """The answer to "may this field serve this use?"."""

    field: str
    use: FieldUse
    allowed: bool
    reason: str
    obligations: frozenset[Obligation] = frozenset()


@dataclass(frozen=True, slots=True)
class FieldPolicyEntry:
    """One field's policy, from its dictionary row or its derived-field declaration."""

    field: str
    block: str
    source: str
    evidence_status: str
    provenance_class: ProvenanceClass
    production_grade: str
    recommended_use: str
    persona_eligible: bool
    claim_rules: frozenset[ClaimRule]
    client_permit: ClientClaimPermit
    is_weight: bool
    #: Why this entry could not be mapped. Non-empty means refused for every use.
    unmapped: tuple[str, ...] = ()
    #: A runtime field with no dictionary entry: refused until the data owner
    #: classifies it (weighting excepted for the analysis weight).
    unclassified_derived: bool = False

    @property
    def mapped(self) -> bool:
        """True when every policy input was recognised."""
        return not self.unmapped


def _entry_from_row(
    row: Mapping[str, str | None], weight_columns: frozenset[str]
) -> FieldPolicyEntry:
    def text(name: str) -> str:
        return (row.get(name) or "").strip()

    name = text("field")
    use = text("recommended_use")
    status = text("evidence_status")
    grade = text("production_grade")
    persona_raw = text("persona_eligible").lower()

    unmapped: list[str] = []
    phrase = RECOMMENDED_USE_POLICY.get(use)
    if phrase is None:
        unmapped.append(f"recommended_use {use!r} is not a known phrase")
    provenance = EVIDENCE_STATUS_CLASS.get(status)
    if provenance is None:
        unmapped.append(f"evidence_status {status!r} is not a known code")
    if grade not in KNOWN_GRADES:
        unmapped.append(f"production_grade {grade!r} is not a known grade")
    if persona_raw not in ("yes", "no"):
        unmapped.append(f"persona_eligible {persona_raw!r} is neither yes nor no")

    return FieldPolicyEntry(
        field=name,
        block=text("block"),
        source=text("source"),
        evidence_status=status,
        provenance_class=provenance or ProvenanceClass.UNCLASSIFIED,
        production_grade=grade,
        recommended_use=use,
        persona_eligible=persona_raw == "yes",
        claim_rules=phrase.rules if phrase else frozenset(),
        client_permit=phrase.client_permit if phrase else ClientClaimPermit.NONE,
        is_weight=name in weight_columns,
        unmapped=tuple(unmapped),
    )


def _derived_entry(name: str, *, is_weight: bool) -> FieldPolicyEntry:
    return FieldPolicyEntry(
        field=name,
        block="",
        source="runtime-derived",
        evidence_status="",
        provenance_class=ProvenanceClass.UNCLASSIFIED,
        production_grade="",
        recommended_use="",
        persona_eligible=False,
        claim_rules=frozenset(),
        client_permit=ClientClaimPermit.NONE,
        is_weight=is_weight,
        unclassified_derived=True,
    )


def _refuse(name: str, use: FieldUse, reason: str) -> UsageDecision:
    return UsageDecision(field=name, use=use, allowed=False, reason=reason)


@dataclass(frozen=True, slots=True)
class FieldPolicy:
    """The policy of every field a population version carries."""

    version: str
    dictionary_sha256: str
    entries: Mapping[str, FieldPolicyEntry] = field(repr=False)

    @property
    def unmapped(self) -> tuple[FieldPolicyEntry, ...]:
        """Entries the tables could not map. Empty for an accepted dictionary."""
        return tuple(e for e in self.entries.values() if e.unmapped)

    def entry(self, name: str) -> FieldPolicyEntry | None:
        """The policy entry for ``name``, or ``None`` for a field this version lacks."""
        return self.entries.get(name)

    def decide(self, name: str, use: FieldUse) -> UsageDecision:
        """Decide whether ``name`` may serve ``use``. Never raises; see :meth:`require`."""
        entry = self.entries.get(name)
        if entry is None:
            return _refuse(name, use, "unknown_field")
        if entry.unmapped:
            return _refuse(name, use, "unmapped_policy")

        if use is FieldUse.WEIGHTING:
            if entry.is_weight:
                return UsageDecision(name, use, True, "declared_weight_column")
            return _refuse(name, use, "not_a_weight_column")

        if entry.unclassified_derived:
            return _refuse(name, use, "unclassified_derived_field")
        rules = entry.claim_rules
        if ClaimRule.AUDIT_ONLY in rules:
            return _refuse(name, use, "audit_only")

        obligations: set[Obligation] = set()
        if ClaimRule.REQUIRES_SCOPE in rules:
            obligations.add(Obligation.DISCLOSE_SCOPE)
        if rules & {ClaimRule.AGGREGATE_ONLY, ClaimRule.PERSON_VALUE_MODELED}:
            obligations.add(Obligation.AGGREGATE_ONLY)
        if ClaimRule.SPECIFIED_WEIGHT_REQUIRED in rules:
            obligations.add(Obligation.USE_SPECIFIED_WEIGHT)
        modelled = (
            ClaimRule.REQUIRES_MODELED_DISCLOSURE in rules or not entry.provenance_class.is_measured
        )

        if use in (FieldUse.AUDIENCE_FILTERING, FieldUse.AGGREGATE_ANALYSIS, FieldUse.SIMULATION):
            return UsageDecision(name, use, True, "internal_use", frozenset(obligations))

        if use is FieldUse.PERSONA_CONSTRUCTION:
            if not entry.persona_eligible:
                return _refuse(name, use, "not_persona_eligible")
            if modelled:
                obligations.add(Obligation.DISCLOSE_MODELLED)
            return UsageDecision(name, use, True, "persona_eligible", frozenset(obligations))

        # Client-facing from here on: positive support required.
        if entry.production_grade in _CLIENT_BLOCKING_GRADES:
            return _refuse(name, use, f"grade_{entry.production_grade}_not_client_facing")
        if entry.client_permit is ClientClaimPermit.NONE:
            return _refuse(name, use, "phrase_permits_no_client_claim")

        if use is FieldUse.CLIENT_MEASURED_CLAIM:
            forbidding = rules & {
                ClaimRule.NEVER_MEASURED_FACT,
                ClaimRule.NEVER_DIRECT_SCHWARTZ,
                ClaimRule.PERSON_VALUE_MODELED,
                ClaimRule.REQUIRES_MODELED_DISCLOSURE,
                ClaimRule.HISTORICAL_OR_EXPLORATORY,
            }
            if forbidding:
                return _refuse(name, use, f"rule_{sorted(forbidding)[0].value.lower()}")
            if entry.client_permit is not ClientClaimPermit.MEASURED_OR_MODELLED:
                return _refuse(name, use, "phrase_permits_modelled_claims_only")
            if not entry.provenance_class.is_measured:
                return _refuse(
                    name, use, f"evidence_{entry.provenance_class.value.lower()}_is_not_measured"
                )
            return UsageDecision(name, use, True, "measured_evidence", frozenset(obligations))

        # CLIENT_MODELLED_CLAIM: always disclosed as modelled.
        obligations.add(Obligation.DISCLOSE_MODELLED)
        if entry.client_permit is ClientClaimPermit.MODELLED_AGGREGATE:
            obligations.add(Obligation.AGGREGATE_ONLY)
        return UsageDecision(name, use, True, "disclosed_modelled_claim", frozenset(obligations))

    def require(self, name: str, use: FieldUse) -> frozenset[Obligation]:
        """Return the obligations of a permitted use, or raise :class:`FieldUseRefused`."""
        decision = self.decide(name, use)
        if not decision.allowed:
            raise FieldUseRefused(decision)
        return decision.obligations

    def permitted(self, use: FieldUse, names: Iterable[str] | None = None) -> tuple[str, ...]:
        """Every field (of ``names``, or of this version) that may serve ``use``."""
        candidates = self.entries if names is None else names
        return tuple(n for n in candidates if self.decide(n, use).allowed)


def build_field_policy(
    rows: Sequence[Mapping[str, str | None]],
    *,
    dictionary_sha256: str,
    weight_columns: Iterable[str],
    derived_fields: Iterable[tuple[str, bool]] = (),
) -> FieldPolicy:
    """Build the policy from dictionary rows plus the declared derived fields.

    ``derived_fields`` is ``(name, is_weight)`` for each runtime field that has no
    dictionary entry. A derived name that collides with a dictionary field is a
    contract error, not something to resolve by precedence.
    """
    weights = frozenset(weight_columns)
    entries: dict[str, FieldPolicyEntry] = {}
    for row in rows:
        entry = _entry_from_row(row, weights)
        entries[entry.field] = entry
    for name, is_weight in derived_fields:
        if name in entries:
            raise ValueError(f"derived field {name} collides with a dictionary field")
        entries[name] = _derived_entry(name, is_weight=is_weight)
    return FieldPolicy(
        version=FIELD_POLICY_VERSION, dictionary_sha256=dictionary_sha256, entries=entries
    )
