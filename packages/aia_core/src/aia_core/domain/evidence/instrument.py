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
* its answers' origin has a policy. There are two, each fixed and versioned, chosen by the
  origin and never by a caller:

  - **simulated** respondents (:data:`~aia_core.domain.fieldwork.NON_EVIDENCE_ORIGINS`: the
    fictional fixture, or AI respondents on the fictional roster) -> ``-1``
    (:data:`INSTRUMENT_POLICY_VERSION`), below;
  - **modelled** respondents (``MODELLED_AI_PANEL``: AI respondents built from the run's own
    population, ADR 0024) -> ``-2`` (:data:`MODELLED_INSTRUMENT_POLICY_VERSION`), after it.

  Any other origin -- including none -- has no policy here and is refused
  (:class:`InstrumentPolicyRefused`): what observed fieldwork may support is a decision
  nobody has made yet.

``-1`` is the most restrictive the gate can express short of refusing the item outright:

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

``-2`` (ADR 0024 §3) keeps every rule of ``-1`` that is about the number -- never a measured
fact, aggregate only, never one person's -- and adds what a client-facing modelled claim must
carry: a scope disclosure (``REQUIRES_SCOPE``) and the modelled-value disclosure on every claim,
not only a measured one (``MODELED_DISCLOSURE_ALWAYS``). It is internal only (``INTERNAL_ONLY``)
until a ``HOLDOUT_VALIDATED`` validation earned on the current respondent system lifts that
(ADR 0024 §4, :func:`.validation.lifts_internal_only`); nothing records one yet.

Two refusals already stand between these items and a client before this one: the
data-origin gate refuses every simulated origin client-facing (``admission``), and a
run with no population panel has no ``CORE_JOINT_STATUS`` certificate, on which no
client claim is admitted. Approving this policy for internal use, and any client use
of instrument evidence from any origin, is a methodology decision
(``.planning/plans/evidence-backed-analysis.md``, ANL-1).

Pure: no I/O.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final

from ..fieldwork import NON_EVIDENCE_ORIGINS, DataOrigin, OriginKind, origin_kind
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
from .validation import ValidationState, lifts_internal_only

__all__ = [
    "INSTRUMENT_BLOCK",
    "INSTRUMENT_FIELD_PREFIX",
    "INSTRUMENT_POLICY_VERSION",
    "INSTRUMENT_RECOMMENDED_USE",
    "MODELLED_INSTRUMENT_POLICY_VERSION",
    "MODELLED_INSTRUMENT_RECOMMENDED_USE",
    "InstrumentItem",
    "InstrumentPolicyRefused",
    "instrument_declaration_sha256",
    "instrument_field",
    "instrument_policy",
    "instrument_policy_book",
    "instrument_policy_version",
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

#: ``-2``: the policy of answers from AI respondents built from the run's population.
MODELLED_INSTRUMENT_POLICY_VERSION: Final = "aia-instrument-evidence-2"

#: ``-2``'s declared use; its claim rules are extracted from it as ``-1``'s are.
MODELLED_INSTRUMENT_RECOMMENDED_USE: Final = (
    "study instrument item answered by AI respondents built from the population; aggregate "
    "or segmentation analysis WITH_SCOPE; individual value modeled; never measured fact; "
    "modeled value disclosure"
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


@dataclass(frozen=True, slots=True)
class _Declared:
    version: str
    recommended_use: str
    status: InstrumentStatus
    #: AIA's own rules, after the ones the declared use extracts.
    aia_rules: tuple[ClaimRule, ...]


_SIMULATED: Final = _Declared(
    INSTRUMENT_POLICY_VERSION,
    INSTRUMENT_RECOMMENDED_USE,
    InstrumentStatus.SIMULATED_RESPONSE,
    (ClaimRule.INTERNAL_ONLY,),
)
_MODELLED: Final = _Declared(
    MODELLED_INSTRUMENT_POLICY_VERSION,
    MODELLED_INSTRUMENT_RECOMMENDED_USE,
    InstrumentStatus.MODELLED_PANEL_RESPONSE,
    (ClaimRule.MODELED_DISCLOSURE_ALWAYS, ClaimRule.INTERNAL_ONLY),
)


def _declared(origin: DataOrigin | None) -> tuple[DataOrigin, _Declared]:
    """The policy ``origin``'s answers are declared under, by the origin's kind; else refused."""
    kind = origin_kind(origin)
    if origin is not None and kind is OriginKind.SIMULATED:
        return origin, _SIMULATED
    if origin is not None and kind is OriginKind.MODELLED:
        return origin, _MODELLED
    raise InstrumentPolicyRefused(
        f"no instrument evidence policy covers answers of origin "
        f"{origin.value if origin else 'unknown'!r}; only simulated respondents "
        f"({', '.join(sorted(o.value for o in NON_EVIDENCE_ORIGINS))}) and modelled "
        f"respondents ({DataOrigin.MODELLED_AI_PANEL.value}) are declared"
    )


def instrument_policy_version(origin: DataOrigin | None) -> str:
    """The version of the policy ``origin``'s answers are declared under; else refused."""
    return _declared(origin)[1].version


_SHA256: Final = re.compile(r"[0-9a-f]{64}")


@dataclass(frozen=True, slots=True)
class _Judged:
    origin: DataOrigin
    declared: _Declared
    #: ``-2`` only: the respondent system the answers came from, and whether a current holdout
    #: validation on it lifts ``INTERNAL_ONLY``.
    respondent_system: str | None
    lifted: bool

    @property
    def rules(self) -> tuple[ClaimRule, ...]:
        aia = self.declared.aia_rules
        if self.lifted:
            aia = tuple(r for r in aia if r is not ClaimRule.INTERNAL_ONLY)
        return (*claim_rules_for(self.declared.recommended_use), *aia)


def _judge(
    origin: DataOrigin | None,
    respondent_system: str | None,
    validation: ValidationState | None,
) -> _Judged:
    """The policy ``origin``'s answers are declared under, and what a validation does to it.

    A simulated origin is never validated: passing a system or a validation for it is refused.
    A modelled origin leaves ``INTERNAL_ONLY`` only under :func:`.validation.lifts_internal_only`.
    """
    declared_origin, declared = _declared(origin)
    if respondent_system is not None and not _SHA256.fullmatch(respondent_system):
        raise ValueError("a respondent system is named by its fingerprint (a SHA-256)")
    if declared is _SIMULATED:
        if respondent_system is not None or validation is not None:
            raise InstrumentPolicyRefused(
                "simulated answers are never validated: no respondent system or validation "
                "applies to them"
            )
        return _Judged(declared_origin, declared, None, False)
    if validation is not None and respondent_system is None:
        raise ValueError("a validation is judged against the current respondent system; none given")
    lifted = lifts_internal_only(validation, respondent_system)
    return _Judged(declared_origin, declared, respondent_system, lifted)


def instrument_policy(
    item: InstrumentItem,
    *,
    origin: DataOrigin | None,
    source: str,
    respondent_system: str | None = None,
    validation: ValidationState | None = None,
) -> FieldPolicy:
    """The fixed policy of one instrument item whose answers came from ``origin``.

    ``respondent_system`` and ``validation`` apply to a modelled origin only (ADR 0024 §4).
    """
    judged = _judge(origin, respondent_system, validation)
    if not source.strip():
        raise ValueError("an instrument policy names the source of its answers")
    return FieldPolicy(
        field=instrument_field(item.question_id),
        block=INSTRUMENT_BLOCK,
        source=source.strip(),
        evidence_status=judged.declared.status,
        provenance_class=ProvenanceClass.MODELLED,
        production_grade=None,
        recommended_use_verbatim=judged.declared.recommended_use,
        description=item.text.strip(),
        persona_eligible=False,
        claim_rules=judged.rules,
        eligibility=_ELIGIBILITY,
        mandated_weight_scheme=None,
    )


def instrument_declaration_sha256(
    items: Sequence[InstrumentItem],
    *,
    origin: DataOrigin | None,
    source: str,
    respondent_system: str | None = None,
    validation: ValidationState | None = None,
) -> str:
    """Identity of a declaration: the policy version, the origin, the source, the items.

    A modelled declaration also binds the respondent system and whether a validation lifted
    ``INTERNAL_ONLY``, so a module judged under one validation is never reused under another.
    A simulated declaration's identity is ``-1``'s, unchanged.
    """
    judged = _judge(origin, respondent_system, validation)
    material: dict[str, object] = {
        "policy": judged.declared.version,
        "origin": judged.origin.value,
        "source": source.strip(),
        "items": [[i.question_id, i.text.strip()] for i in items],
    }
    if judged.declared is _MODELLED:
        material["respondent_system"] = judged.respondent_system
        material["internal_only_lifted"] = judged.lifted
    return fingerprint(material)


def instrument_policy_book(
    items: Sequence[InstrumentItem],
    *,
    origin: DataOrigin | None,
    source: str,
    respondent_system: str | None = None,
    validation: ValidationState | None = None,
) -> FieldPolicyBook:
    """The policy book of one run's instrument: every item it asked, and nothing else.

    Bound to its declaration's SHA-256 (the book's ``source_sha256``), which is what a
    module fingerprint records as the field dictionary it was judged under.
    """
    fields: dict[str, FieldPolicy] = {}
    for item in items:
        policy = instrument_policy(
            item,
            origin=origin,
            source=source,
            respondent_system=respondent_system,
            validation=validation,
        )
        if policy.field in fields:
            raise FieldPolicyError(f"instrument item {item.question_id!r} is declared twice")
        fields[policy.field] = policy
    if not fields:
        raise InstrumentPolicyRefused("the instrument declares no item")
    return FieldPolicyBook(
        source_sha256=instrument_declaration_sha256(
            items,
            origin=origin,
            source=source,
            respondent_system=respondent_system,
            validation=validation,
        ),
        fields=fields,
    )
