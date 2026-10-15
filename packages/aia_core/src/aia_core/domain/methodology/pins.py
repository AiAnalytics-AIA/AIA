"""What a research run pins from the methodology in force (ADR 0023 decision 6, plan A4).

A run pins its Sociomap methods when it starts (``research_sociomap.SociomapMethod``), each
with its whole specification, and computes exactly those whatever is put in force later. With
nothing stored the pins are the code's (:func:`~aia_core.domain.research_sociomap.default_methods`);
with an edited object map in force, the reference map is pinned as always beside the edited
specification, under the version's own name. That is all the engine needs for an edited
parameter: it already computes whatever specification a run pinned.

A version's replaced formulas are pinned with its specification
(``SociomapMethod.formulas``), and the engine computes each from its expression where the
code's formula would run (``sociomap.slots``, S4c). A slot the engine does not read is
refused (:data:`COMPUTED_SLOTS`): a run must never quietly compute the built-in formula
while its methodology says another.

Pure: stdlib and Pydantic only.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Final

from ..evidence.support import AIA_SUPPORT_V1, SupportSpec
from ..research_aggregate import AGGREGATE_SLOTS, AIA_AGGREGATE_V1, AggregationSpec
from ..research_design import AIA_READINESS_V1, ReadinessSpec, readiness_problems
from ..research_sociomap import SociomapMethod, default_methods
from ..respondent_behavior import AIA_RESPONSE_V1, ResponseProcessSpec
from ..sociomap.slots import ENGINE_SLOTS, NO_SLOTS, Slots
from ..sociomap.specification import AIA_SOCIOMAP_V1, SociomapSpecV3
from .aggregation_formulas import AGGREGATION_FORMULAS
from .expressions import compile_formula

__all__ = [
    "COMPUTED_SLOTS",
    "UNIT_AGGREGATION_PIN",
    "FormulaNotComputed",
    "RunMethod",
    "aggregation_pin_for",
    "is_units_process",
    "read_aggregation_pin",
    "read_readiness_pin",
    "read_response_pin",
    "read_support_pin",
    "readiness_spec_for",
    "response_deviates",
    "response_spec_for",
    "run_methods",
    "sociomap_methods_for",
    "support_spec_for",
    "uncomputed_formulas",
]

#: The slots whose stored expression the engine evaluates in place of its own function:
#: every slot the object map's engine reads, and every estimator the aggregate reads (plan
#: G3a). A version replacing any other slot is stored and shown, but not put in force.
COMPUTED_SLOTS: Final[frozenset[str]] = ENGINE_SLOTS | AGGREGATE_SLOTS

#: A run's aggregation pin when nothing is stored: 18.6.6's values, no formula replaced.
UNIT_AGGREGATION_PIN: Final[Mapping[str, Any]] = {
    "spec": AIA_AGGREGATE_V1.model_dump(mode="json"),
    "formulas": {},
}
_AGGREGATION_SLOTS: Final = {f.slot.id: f.slot for f in AGGREGATION_FORMULAS}


class FormulaNotComputed(ValueError):
    """A version replaces a formula the engine does not yet evaluate from its expression."""

    def __init__(self, slots: list[str]) -> None:
        self.slots = slots
        super().__init__(
            "the engine does not yet compute these formulas from a stored expression, so a "
            f"version replacing them cannot be put in force: {', '.join(slots)}"
        )


def uncomputed_formulas(payload: Mapping[str, Any]) -> list[str]:
    """The slots a version payload replaces that the engine does not evaluate yet."""
    return sorted(set(payload.get("formulas", {})) - COMPUTED_SLOTS)


def sociomap_methods_for(payload: Mapping[str, Any] | None) -> tuple[SociomapMethod, ...]:
    """The Sociomap pins of a run started under ``payload`` (``None``: the code's preset)."""
    if payload is None:
        return default_methods()
    missing = uncomputed_formulas(payload)
    if missing:
        raise FormulaNotComputed(missing)
    edited = SociomapSpecV3.model_validate(payload["spec"])
    return (
        SociomapMethod.of(AIA_SOCIOMAP_V1),
        SociomapMethod.of(edited, payload.get("formulas") or {}),
    )


def support_spec_for(payload: Mapping[str, Any] | None) -> SupportSpec:
    """The support rules a run started under ``payload`` pins (plan ``methodology-tab`` G1c).

    ``None`` -- nothing stored -- is the code's preset, ``aia-support-1``: both rules as they
    were before any version (owner, 2026-10-12), the unit's donor rule for Results and AIA's
    gate for analysis."""
    if payload is None:
        return AIA_SUPPORT_V1
    return SupportSpec.model_validate(payload["spec"])


def read_support_pin(value: Any) -> SupportSpec:
    """A run's pinned support rules from their stored form. A run started before support was
    pinned (``None``) was computed under ``aia-support-1``, so that is what it reads."""
    if value is None:
        return AIA_SUPPORT_V1
    return SupportSpec.model_validate(value)


def readiness_spec_for(payload: Mapping[str, Any] | None) -> ReadinessSpec:
    """The readiness limits a run started under ``payload`` pins (plan ``methodology-tab``
    V1a). ``None`` -- nothing stored -- is the code's preset, ``aia-readiness-1``: 18.6.6's
    product policy."""
    if payload is None:
        return AIA_READINESS_V1
    return read_readiness_pin(payload["spec"])


def read_readiness_pin(value: Any) -> ReadinessSpec:
    """A run's pinned readiness limits from their stored form. A run started before the
    limits were pinned (``None``) was compiled and checked under ``aia-readiness-1``, so that
    is what it reads. A pin that does not validate, or breaks a rule every version keeps,
    raises ``ValueError``; nothing falls back to the code's limits."""
    if value is None:
        return AIA_READINESS_V1
    spec = ReadinessSpec.model_validate(value)
    problems = readiness_problems(spec)
    if problems:
        raise ValueError(
            "the readiness pin breaks its rules: "
            + "; ".join(f"{k}: {v}" for k, v in sorted(problems.items()))
        )
    return spec


def aggregation_pin_for(payload: Mapping[str, Any] | None) -> dict[str, Any]:
    """What a run started under ``payload`` pins for its aggregation (plan G3a): the whole
    specification and the formulas the version replaces. ``None`` -- nothing stored -- is
    ``aia-aggregate-1`` with none replaced, 18.6.6's port. A version replacing a formula the
    aggregate does not read is refused (:class:`FormulaNotComputed`), never pinned."""
    if payload is None:
        return {"spec": dict(UNIT_AGGREGATION_PIN["spec"]), "formulas": {}}
    missing = uncomputed_formulas(payload)
    if missing:
        raise FormulaNotComputed(missing)
    spec = AggregationSpec.model_validate(payload["spec"])
    return {"spec": spec.model_dump(mode="json"), "formulas": dict(payload.get("formulas") or {})}


def read_aggregation_pin(value: Any) -> tuple[AggregationSpec, Slots]:
    """A run's pinned aggregation from its stored form: the specification, and each replaced
    formula compiled into the slot the aggregate reads. A run started before aggregation was
    pinned (``None``) was computed as 18.6.6's port, so that is what it reads. A pin that does
    not validate or compile raises ``ValueError``; nothing falls back to the code's formula."""
    if value is None:
        return AIA_AGGREGATE_V1, NO_SLOTS
    if not isinstance(value, Mapping):
        raise ValueError("an aggregation pin is a mapping of spec and formulas")
    spec = AggregationSpec.model_validate(value.get("spec"))
    formulas = value.get("formulas") or {}
    unknown = sorted(set(formulas) - set(_AGGREGATION_SLOTS))
    if unknown:
        raise ValueError(f"the aggregate reads no formula {', '.join(unknown)}")
    slots = {sid: compile_formula(_AGGREGATION_SLOTS[sid], text) for sid, text in formulas.items()}
    return spec, slots


def response_spec_for(payload: Mapping[str, Any] | None) -> ResponseProcessSpec:
    """The response process a run started under ``payload`` pins (plan ``methodology-tab``
    R1b). ``None`` -- nothing stored -- is the code's preset, ``aia-response-1``: 18.6.6's
    coefficients."""
    if payload is None:
        return AIA_RESPONSE_V1
    return ResponseProcessSpec.model_validate(payload["spec"])


def read_response_pin(value: Any) -> ResponseProcessSpec:
    """A run's pinned response process from its stored form. A run started before the process
    was pinned (``None``) was answered under ``aia-response-1``, so that is what it reads. A pin
    that does not validate raises ``ValueError``; nothing falls back to the code's values."""
    if value is None:
        return AIA_RESPONSE_V1
    return ResponseProcessSpec.model_validate(value)


@dataclass(frozen=True)
class RunMethod:
    """One method a run computed under, by name (plan ``methodology-tab`` Z1a)."""

    #: ``None``: the run recorded a pin that cannot be read as a name. Never guessed.
    name: str | None
    #: ``True``: a version stored on the Metodika tab; ``False``: the pin or the code's preset.
    stored: bool


def _stored_name(meta: Mapping[str, Any], key: str) -> str | None:
    record = meta.get(key)
    return str(record["name"]) if isinstance(record, Mapping) and record.get("name") else None


def _version(spec: Any) -> str | None:
    if isinstance(spec, Mapping) and spec.get("methodology_version"):
        return str(spec["methodology_version"])
    return None


def _sociomap_name(value: Any) -> str | None:
    reference = AIA_SOCIOMAP_V1.methodology_version
    if value is None:
        return reference  # before the pins: the legacy method (``LEGACY_METHODS``)
    if not isinstance(value, list) or not value:
        return None
    ids = [m.get("method_id") if isinstance(m, Mapping) else None for m in value]
    if not all(isinstance(i, str) and i for i in ids):
        return None
    edited = [i for i in ids if i != reference]
    return str(edited[-1]) if edited else reference


def run_methods(meta: Mapping[str, Any]) -> dict[str, RunMethod]:
    """The Sociomap, support, aggregation and response methods a run's metadata records, by
    name.

    A stored version is named as stored. Otherwise the name is the pin's own: the last pinned
    Sociomap method beside the reference map, the support and aggregation specifications'
    ``methodology_version``. A run started before a module was pinned (no pin) was computed
    under that module's code preset, which is what the pins' own readers read it as
    (``read_methods``, :func:`read_support_pin`, :func:`read_aggregation_pin`). A pin that is
    there but cannot be read gives ``None``, never a preset's name: the engine would refuse
    it, and a guess here would say the run was computed under something it was not. Reading
    only: nothing is validated or computed, so a list of runs never fails on one run's pin."""
    support_pin = meta.get("support")
    aggregation_pin = meta.get("aggregation")
    response_pin = meta.get("response")
    pinned = {
        "sociomap": _sociomap_name(meta.get("sociomap_methods")),
        "support": (
            AIA_SUPPORT_V1.methodology_version if support_pin is None else _version(support_pin)
        ),
        "aggregation": (
            AIA_AGGREGATE_V1.methodology_version
            if aggregation_pin is None
            else _version(aggregation_pin.get("spec"))
            if isinstance(aggregation_pin, Mapping)
            else None
        ),
        "response": (
            AIA_RESPONSE_V1.methodology_version if response_pin is None else _version(response_pin)
        ),
    }
    keys = {
        "sociomap": "methodology",
        "support": "support_methodology",
        "aggregation": "aggregation_methodology",
        "response": "response_methodology",
    }
    methods = {}
    for module, key in keys.items():
        stored = _stored_name(meta, key)
        methods[module] = RunMethod(name=stored or pinned[module], stored=stored is not None)
    return methods


def response_deviates(meta: Mapping[str, Any]) -> bool | None:
    """Whether the response process a run's answers came from is not 18.6.6's (plan
    ``methodology-tab`` R1d). A run started before the process was pinned was answered under
    ``aia-response-1``: ``False``. A pin that cannot be read gives ``None``: the run's answers
    came from some process, and saying which would be a guess. The coefficients decide, not
    the version's name."""
    try:
        pinned = read_response_pin(meta.get("response"))
    except ValueError:
        return None
    return not is_units_process(pinned)


def is_units_process(spec: ResponseProcessSpec) -> bool:
    """Whether ``spec`` computes with 18.6.6's coefficients. The numbers decide, not the
    name: a stored version holding the unit's values is the unit's process."""
    unit = AIA_RESPONSE_V1.model_dump(exclude={"methodology_version"})
    return bool(spec.model_dump(exclude={"methodology_version"}) == unit)
