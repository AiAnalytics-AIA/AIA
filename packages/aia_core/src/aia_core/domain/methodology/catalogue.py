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
    "ParameterEffect",
    "ParameterRef",
    "Preset",
    "PreviewLine",
    "StepGroup",
    "Symbol",
    "feeds_of",
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


class ParameterEffect(StrEnum):
    """What crossing a limit does, where a value is a limit a design is held to (V1a2)."""

    #: No limit: a value the computation reads.
    NONE = ""
    #: A design outside it may not start a run.
    BLOCKS_RUN = "blocks_run"
    #: A design outside it does not compile.
    BLOCKS_DESIGN = "blocks_design"
    #: A design outside it is only warned about.
    WARNS = "warns"


@dataclass(frozen=True, slots=True)
class ParameterRef:
    """A field of the module's specification, by dotted path (``relation.n_min``).

    A path through a mapping field names its key (``layout.parameters.max_iterations``).
    """

    path: str
    label_cs: str
    unit: str = ""
    effect: ParameterEffect = ParameterEffect.NONE


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
    #: Where the step sits in the computation, as a reader needs it (product owner,
    #: 2026-10-14): what it is for, the steps whose results it reads (``inputs``, step ids of
    #: the same module), what it reads from outside the module when it reads none of them
    #: (``source_cs``), and the audit's point it implements (``audit``, e.g. "F3"). The steps
    #: that read this one are derived from the others' ``inputs`` (:func:`feeds_of`); where
    #: its result goes outside the module when no step reads it is ``effect_cs``.
    role_cs: str = ""
    inputs: tuple[str, ...] = ()
    source_cs: str = ""
    audit: str = ""
    effect_cs: str = ""
    #: The rule in words, its values as ``{dotted.path}`` placeholders the page fills from the
    #: draft (``"{sample_size.min} ≤ n ≤ {sample_size.max}"``), and what every version of it
    #: keeps whatever the values (V1a2).
    reading_cs: str = ""
    keeps_cs: tuple[str, ...] = ()


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
    #: What the engine keeps around the expression, whatever replaces it: the refusals, the
    #: sets its variables are read over, the branch it does not cover (product owner,
    #: 2026-10-14: a reader took the step's whole formula for the editable part).
    kept_cs: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class PreviewLine:
    """One line a person would meet under a specification, as the code itself writes it: the
    step it belongs to, its status (``PASS`` / ``WARN`` / ``FAIL``) and its words."""

    step_id: str
    status: str
    message_cs: str


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
    #: What a person would meet under a specification, computed by the code on fixed
    #: fictional inputs (V1a2); ``None`` where the module shows none.
    preview: Callable[[BaseModel], tuple[PreviewLine, ...]] | None = None


def feeds_of(module: MethodModule, step_id: str) -> tuple[str, ...]:
    """The steps of ``module`` that read ``step_id``'s result, in the module's step order."""
    return tuple(s.id for s in module.steps if step_id in s.inputs)
