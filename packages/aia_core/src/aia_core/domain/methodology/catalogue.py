"""What a method module is made of: steps, the values they read, and the evidence behind them.

ADR 0023 decision 1. The Metodika tab shows AIA's mathematics *from the code*: every step of
every method module, in computation order, with its formula, its symbols, the values it reads
and where each comes from. This module defines the shapes; the modules themselves are
declared beside the code they describe (plan ``methodology-tab.md`` S1, G1, ...).

A value a step reads is one of two kinds, and the page labels them:

* a :class:`ParameterRef` -- a field of the module's declared specification, read from the
  specification in force (today: the code preset; chunk A3 adds stored versions);
* a :class:`ConstantRef` -- a module constant in ``aia_core.domain``, read by import, so the
  value shown is the value that runs. A constant that shapes a result is due to move into the
  specification (ADR 0023 decision 2); until it has, the page says it is code.

Nothing here copies a value. A step names *where* a value lives; :mod:`.resolution` reads it.

Pure: stdlib and Pydantic only.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum

from pydantic import BaseModel

from .expressions import Slot

__all__ = [
    "BuiltinFormula",
    "ConstantRef",
    "Evidence",
    "EvidenceKind",
    "MethodModule",
    "MethodStep",
    "ParameterRef",
    "Preset",
    "StepGroup",
    "Symbol",
]


class EvidenceKind(StrEnum):
    """Why a step computes what it computes."""

    #: A rule of ``docs/migration/sociomapping-evidence-register.json``, by id.
    REGISTER_RULE = "register_rule"
    #: A vendored fixture the step reproduces (``F7``, ``A01``, a capture file), by name.
    FIXTURE = "fixture"
    #: An EXACT port of an 18.6.6 function, by the unit's ``module:function``.
    LEGACY_PORT = "legacy_port"
    #: A decision AIA made, by the document that records it (an ADR, a plan section).
    AIA_DECISION = "aia_decision"


@dataclass(frozen=True, slots=True)
class Evidence:
    kind: EvidenceKind
    ref: str
    note_cs: str = ""


@dataclass(frozen=True, slots=True)
class Symbol:
    """One symbol of a step's formula: how it is written, what it means, its unit."""

    latex: str
    meaning_cs: str
    unit: str = ""


@dataclass(frozen=True, slots=True)
class ParameterRef:
    """A field of the module's specification, by dotted path (``relation.n_min``).

    A path through a mapping field names its key (``layout.parameters.max_iterations``).
    """

    path: str
    label_cs: str
    unit: str = ""


@dataclass(frozen=True, slots=True)
class ConstantRef:
    """A constant that shapes the step but is not (yet) in the specification.

    ``symbol`` is ``"aia_core.domain.<module>:<NAME>"``. Only ``aia_core.domain`` is
    readable: the domain shows the domain, and importing outward would break its purity.
    """

    symbol: str
    label_cs: str
    unit: str = ""


@dataclass(frozen=True, slots=True)
class MethodStep:
    """One computation, as the methodologist reads it.

    ``implements`` is the ``module:qualname`` of the function the step describes;
    ``source_sha256`` pins that function's source, so a function that changes fails a test
    until the step is re-read against it and its pin updated (plan chunk A1). ``tests`` are
    ``path::name`` references to the tests that pin the behaviour.
    """

    id: str
    title_cs: str
    formula_latex: str
    implements: str
    source_sha256: str
    symbols: tuple[Symbol, ...] = ()
    parameters: tuple[ParameterRef, ...] = ()
    constants: tuple[ConstantRef, ...] = ()
    evidence: tuple[Evidence, ...] = ()
    tests: tuple[str, ...] = ()
    note_cs: str = ""


@dataclass(frozen=True, slots=True)
class Preset:
    """A named specification the code ships, and the validator that accepts it.

    ``validate`` raises on a specification the engine cannot compute and returns ``None``
    otherwise (for the Sociomap: ``require_supported``).
    """

    name: str
    spec: BaseModel
    validate: Callable[[BaseModel], None]


@dataclass(frozen=True, slots=True)
class BuiltinFormula:
    """A step's formula as an editable slot, with the expression the engine computes today.

    ADR 0023 decision 4. ``expression`` is written in the formula language
    (:mod:`.expressions`) so that it gives the engine's exact bits on every input (the
    test suite proves it per slot against the engine's own function); a stored edit replaces
    it. A step whose computation is an algorithm, not a formula (a fit, a ranking, a graph
    test), has none.
    """

    step_id: str
    slot: Slot
    expression: str
    note_cs: str = ""


@dataclass(frozen=True, slots=True)
class StepGroup:
    """Steps shown together under one heading (for the Sociomap: one of the audit's F1-F16)."""

    id: str
    title_cs: str
    step_ids: tuple[str, ...]
    note_cs: str = ""


@dataclass(frozen=True, slots=True)
class MethodModule:
    """One area of AIA's mathematics (ADR 0023 decision 1), its steps in computation order.

    ``presets`` are the specifications the code ships; ``in_force`` names the one a run
    uses today when nothing is stored. A module whose values are not declared yet has no
    presets, and its steps read constants only (ADR 0023 decision 2 declares them).
    ``groups`` order the steps on the page (for the Sociomap: the audit's F1-F16); when there
    are groups, every step belongs to exactly one. ``formulas`` are the steps' editable
    slots, each with the built-in expression the engine computes.
    """

    id: str
    title_cs: str
    steps: tuple[MethodStep, ...]
    presets: tuple[Preset, ...] = ()
    in_force: str | None = None
    groups: tuple[StepGroup, ...] = ()
    formulas: tuple[BuiltinFormula, ...] = ()
    #: Whether a methodology version may be stored for it (ADR 0023 decision 4).
    editable: bool = False
    note_cs: str = ""
