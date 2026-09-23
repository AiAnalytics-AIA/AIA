"""The factual layer: a fact already in the panel is read, never re-invented by a model.

Reference ``factual_layer.py`` (``respondents.factual_layer``, parity EXACT):
"Facts already present in the panel must never be re-invented by an LLM. This
module classifies common factual survey questions and maps them to
authoritative panel fields." Its contract for explicit metadata: "Explicit
metadata wins: ``metadata.fact_source_field`` = exact panel column;
``metadata.fact_kind = "attitude"`` disables auto factual detection;
``metadata.fact_kind = "fact"`` wi[...]" -- the excerpt is truncated there.

Ported here:

* explicit ``fact_source_field`` resolves to that exact field, which must be
  declared in the field dictionary and usable for analysis;
* ``fact_kind = "attitude"`` is never factual;
* ``fact_kind = "fact"`` with no source field is **refused**: a fact with no
  authoritative field cannot be answered deterministically, and the only other
  thing that could answer it is a model (this port's fail-closed reading of the
  truncated rule);
* the answer to a factual question is the respondent's panel value, and a
  missing value stays missing -- it is never filled in.

Not ported: the reference's *automatic* classification of common factual
questions. Its keyword rules are in the withheld source; without them a question
with no metadata resolves to ``UNDECLARED``, and the respondent engine must treat
that as "not proven factual", never as permission to invent. Recorded in
``.planning/open-items.md``.

Whether a factual answer may then be *claimed* as a measurement is not this
layer's decision: :attr:`FactualContract.basis` reports what the field policy
allows, and the claim gate decides.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum

from .claims import ClaimBasis
from .field_policy import FieldPolicyBook, UndeclaredField

__all__ = [
    "FactKind",
    "FactualContract",
    "FactualContractRefused",
    "FactualResolution",
    "QuestionFactMetadata",
    "factual_answer",
    "resolve_factual_contract",
]


class FactKind(StrEnum):
    FACT = "fact"
    ATTITUDE = "attitude"


class FactualResolution(StrEnum):
    FACTUAL = "FACTUAL"
    NOT_FACTUAL = "NOT_FACTUAL"
    UNDECLARED = "UNDECLARED"


class FactualContractRefused(ValueError):
    """Question metadata that cannot be honoured without inventing a fact."""


@dataclass(frozen=True, slots=True)
class QuestionFactMetadata:
    fact_source_field: str | None = None
    fact_kind: str | None = None


@dataclass(frozen=True, slots=True)
class FactualContract:
    resolution: FactualResolution
    source_field: str | None = None
    basis: ClaimBasis | None = None


def resolve_factual_contract(
    metadata: QuestionFactMetadata, book: FieldPolicyBook
) -> FactualContract:
    """Resolve a question's factual contract from explicit metadata only."""
    kind: FactKind | None = None
    if metadata.fact_kind is not None:
        try:
            kind = FactKind(metadata.fact_kind)
        except ValueError:
            raise FactualContractRefused(f"unknown fact_kind {metadata.fact_kind!r}") from None
    source = metadata.fact_source_field

    if kind is FactKind.ATTITUDE:
        if source:
            raise FactualContractRefused(
                f"an attitude question cannot also name a fact source ({source!r})"
            )
        return FactualContract(FactualResolution.NOT_FACTUAL)

    if source:
        try:
            policy = book.get(source)
        except UndeclaredField as exc:
            raise FactualContractRefused(str(exc)) from None
        if not policy.eligibility.analysis:
            raise FactualContractRefused(f"{source!r} is audit-only and cannot answer a question")
        basis = (
            ClaimBasis.MEASURED
            if policy.eligibility.client_facing_measured_claim
            else ClaimBasis.MODELED
        )
        return FactualContract(FactualResolution.FACTUAL, source, basis)

    if kind is FactKind.FACT:
        raise FactualContractRefused(
            "fact_kind 'fact' needs fact_source_field: a fact with no authoritative "
            "panel field would have to be invented"
        )
    return FactualContract(FactualResolution.UNDECLARED)


def factual_answer(contract: FactualContract, respondent: Mapping[str, object]) -> object | None:
    """The respondent's panel value for a factual question. Missing stays None."""
    if contract.resolution is not FactualResolution.FACTUAL or contract.source_field is None:
        raise ValueError(f"not a factual contract: {contract.resolution}")
    return respondent.get(contract.source_field)
