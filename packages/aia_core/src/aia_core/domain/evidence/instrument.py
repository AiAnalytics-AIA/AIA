"""A Study's own questionnaire items as evidence fields, declared from what the run records.

The field dictionary declares the 400 population fields. A research Study's own
questions are not among them: the share answering *"Kávu"* to *"Co si ráno koupíte?"*
is a runtime column with no dictionary entry, and the claim gate refuses an
undeclared field (:func:`.claims.evaluate_claim`). Until this module no number from a
native research run could be admitted on any surface, internal included.

An item is declared here only from facts the run itself recorded, never from a
dictionary and never by a caller's choice of status:

* the item is one the Design Revision compiled to (the caller passes the compiled
  items; nothing here invents one);
* its answers came from **simulated** respondents -- an origin in
  :data:`~aia_core.domain.fieldwork.NON_EVIDENCE_ORIGINS`: the fictional fixture, or
  AI respondents on the fictional roster. Any other origin -- including none -- has
  no policy here and is refused (:class:`InstrumentPolicyRefused`): what observed
  fieldwork may support is a decision nobody has made yet.

There is one policy, fixed and versioned (:data:`INSTRUMENT_POLICY_VERSION`), and it
is the most restrictive the gate can express short of refusing the item outright:

* a simulated answer is a **modelled** value, never a measured fact
  (``NEVER_MEASURED_FACT``; provenance ``MODELLED``; no measured-claim eligibility);
* it is meaningful only **in aggregate** (``AGGREGATE_ONLY``, ``PERSON_VALUE_MODELED``);
* it backs **nothing client-facing** (``INTERNAL_ONLY``, refused by the claim gate
  whatever the certificate or the data origin says);
* it may be used for internal analysis and for nothing else -- not filtering,
  simulation, persona construction or weighting.

The first three rules are exactly what the reference derivation
(:func:`.field_policy.claim_rules_for`) extracts from :data:`INSTRUMENT_RECOMMENDED_USE`,
so the stated phrase and the enforced rules cannot drift apart; ``INTERNAL_ONLY`` is
added because no dictionary phrase says it.

Two refusals already stand between these items and a client before this one: the
data-origin gate refuses every simulated origin client-facing (``admission``), and a
run with no population panel has no ``CORE_JOINT_STATUS`` certificate, on which no
client claim is admitted. Approving this policy for internal use, and any client use
of instrument evidence from any origin, is a methodology decision
(``.planning/plans/evidence-backed-analysis.md``, ANL-1).

Pure: no I/O.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final

from ..fieldwork import NON_EVIDENCE_ORIGINS, DataOrigin
from ..pipeline import fingerprint
from .field_policy import (
    ClaimRule,
    FieldEligibility,
    FieldPolicy,
    FieldPolicyBook,
    FieldPolicyError,
    InstrumentStatus,
    ProvenanceClass,
    claim_rules_for,
)

__all__ = [
    "INSTRUMENT_BLOCK",
    "INSTRUMENT_FIELD_PREFIX",
    "INSTRUMENT_POLICY_VERSION",
    "INSTRUMENT_RECOMMENDED_USE",
    "InstrumentItem",
    "InstrumentPolicyRefused",
    "instrument_declaration_sha256",
    "instrument_field",
    "instrument_policy",
    "instrument_policy_book",
]

#: Identifies the policy below. Part of every fingerprint computed on it, so a
#: change to what an instrument item may support reruns what the old one allowed.
INSTRUMENT_POLICY_VERSION: Final = "aia-instrument-evidence-1"

#: The joint unit every instrument item belongs to: one simulated respondent answered
#: all of them, so a relation among them is within one unit, never cross-block.
INSTRUMENT_BLOCK: Final = "study_instrument"

#: Instrument fields are namespaced so that no item id can collide with, or pose as,
#: a population field of the same name.
INSTRUMENT_FIELD_PREFIX: Final = "instrument:"

#: The declared use, in the dictionary's own vocabulary. The claim rules are
#: extracted from it by the reference derivation, never listed separately.
INSTRUMENT_RECOMMENDED_USE: Final = (
    "study instrument item answered by simulated respondents; aggregate internal "
    "analysis only; individual value modeled; never measured fact"
)

_ELIGIBILITY: Final = FieldEligibility(
    analysis=True,
    client_facing_measured_claim=False,
    filtering=False,
    simulation=False,
    persona_construction=False,
    weighting=False,
)


class InstrumentPolicyRefused(FieldPolicyError):
    """An instrument item cannot be declared: its answers' origin has no policy."""


@dataclass(frozen=True, slots=True)
class InstrumentItem:
    """One question the Study asked, as its compiled specification names it."""

    question_id: str
    text: str

    def __post_init__(self) -> None:
        if not self.question_id or self.question_id != self.question_id.strip():
            raise ValueError(f"an instrument item needs a clean question id: {self.question_id!r}")
        if not self.text.strip():
            raise ValueError(f"instrument item {self.question_id!r} has no question text")


def instrument_field(question_id: str) -> str:
    """The evidence field name of an instrument item: ``instrument:<question id>``."""
    if not question_id or question_id != question_id.strip():
        raise ValueError(f"an instrument field needs a clean question id: {question_id!r}")
    return f"{INSTRUMENT_FIELD_PREFIX}{question_id}"


def _require_simulated(origin: DataOrigin | None) -> DataOrigin:
    if origin is None or origin not in NON_EVIDENCE_ORIGINS:
        raise InstrumentPolicyRefused(
            f"no instrument evidence policy covers answers of origin "
            f"{origin.value if origin else 'unknown'!r}; only simulated respondents "
            f"({', '.join(sorted(o.value for o in NON_EVIDENCE_ORIGINS))}) are declared"
        )
    return origin


def instrument_policy(
    item: InstrumentItem, *, origin: DataOrigin | None, source: str
) -> FieldPolicy:
    """The fixed policy of one instrument item whose answers came from ``origin``."""
    _require_simulated(origin)
    if not source.strip():
        raise ValueError("an instrument policy names the source of its answers")
    rules = (*claim_rules_for(INSTRUMENT_RECOMMENDED_USE), ClaimRule.INTERNAL_ONLY)
    return FieldPolicy(
        field=instrument_field(item.question_id),
        block=INSTRUMENT_BLOCK,
        source=source.strip(),
        evidence_status=InstrumentStatus.SIMULATED_RESPONSE,
        provenance_class=ProvenanceClass.MODELLED,
        production_grade=None,
        recommended_use_verbatim=INSTRUMENT_RECOMMENDED_USE,
        description=item.text.strip(),
        persona_eligible=False,
        claim_rules=rules,
        eligibility=_ELIGIBILITY,
        mandated_weight_scheme=None,
    )


def instrument_declaration_sha256(
    items: Sequence[InstrumentItem], *, origin: DataOrigin | None, source: str
) -> str:
    """Identity of a declaration: the policy version, the origin, the source, the items."""
    declared = _require_simulated(origin)
    return fingerprint(
        {
            "policy": INSTRUMENT_POLICY_VERSION,
            "origin": declared.value,
            "source": source.strip(),
            "items": [[i.question_id, i.text.strip()] for i in items],
        }
    )


def instrument_policy_book(
    items: Sequence[InstrumentItem], *, origin: DataOrigin | None, source: str
) -> FieldPolicyBook:
    """The policy book of one run's instrument: every item it asked, and nothing else.

    Bound to its declaration's SHA-256 (the book's ``source_sha256``), which is what a
    module fingerprint records as the field dictionary it was judged under.
    """
    fields: dict[str, FieldPolicy] = {}
    for item in items:
        policy = instrument_policy(item, origin=origin, source=source)
        if policy.field in fields:
            raise FieldPolicyError(f"instrument item {item.question_id!r} is declared twice")
        fields[policy.field] = policy
    if not fields:
        raise InstrumentPolicyRefused("the instrument declares no item")
    return FieldPolicyBook(
        source_sha256=instrument_declaration_sha256(items, origin=origin, source=source),
        fields=fields,
    )
