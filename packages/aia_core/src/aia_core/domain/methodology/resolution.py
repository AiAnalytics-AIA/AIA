"""Read a method module's values from the code, and say what its catalogue is missing.

ADR 0023 decision 1. :func:`describe` turns a :class:`~.catalogue.MethodModule` into what the
Metodika tab shows: every step with each value it reads, the value read from the
specification in force or imported from its constant, never copied. :func:`module_problems`
is the completeness rule, reported all at once the way ``require_supported`` reports a
specification's problems:

* every leaf of every preset's specification is read by exactly one step, so no value that
  shapes a result is missing from the page and none is shown twice;
* every parameter path resolves in some preset, and every constant imports;
* every step's ``implements`` names a callable; step ids are unique; groups, when declared,
  hold every step exactly once;
* every preset passes its own validator, and ``in_force`` names one of them.

What needs files -- that a step's source pin still matches its function, that its tests
exist -- is checked by the test suite, not here: the domain reads no files.

Pure: stdlib and Pydantic only.
"""

from __future__ import annotations

import importlib
import math
from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum, StrEnum
from typing import Any, Final

from pydantic import BaseModel

from .catalogue import BuiltinFormula, MethodModule, MethodStep, Preset
from .expressions import ExpressionRefused, check_properties, compile_formula

__all__ = [
    "ABSENT",
    "Absent",
    "MethodologyReferenceError",
    "ModuleView",
    "StepView",
    "ValueOrigin",
    "ValueView",
    "describe",
    "leaf_paths",
    "module_problems",
    "read_constant",
    "read_path",
    "resolve_callable",
]

#: The only package a catalogue may read from (see :class:`~.catalogue.ConstantRef`).
READABLE_PREFIX: Final = "aia_core.domain."


class MethodologyReferenceError(LookupError):
    """A catalogue names a path, constant or function that does not exist."""


class Absent:
    """A path that passes through a declared ``None`` (an optional part the preset omits).

    Not an error and never a zero: the page says the part is not used by this preset.
    Compare with ``is ABSENT``; there is one.
    """

    def __repr__(self) -> str:
        return "ABSENT"


ABSENT: Final = Absent()


# --------------------------------------------------------------------------- paths


def leaf_paths(spec: BaseModel) -> tuple[str, ...]:
    """Every value-carrying path of ``spec``, in declaration order.

    A nested model and a mapping are descended into; anything else is a leaf, ``None``
    included (an optional part the preset omits is itself the leaf).
    """
    out: list[str] = []
    _walk(spec, "", out)
    return tuple(out)


def _walk(value: Any, prefix: str, out: list[str]) -> None:
    if isinstance(value, BaseModel):
        for name in type(value).model_fields:
            _walk(getattr(value, name), f"{prefix}{name}.", out)
        return
    if isinstance(value, Mapping) and value:
        for key in value:
            _walk(value[key], f"{prefix}{key}.", out)
        return
    out.append(prefix[:-1])


def read_path(spec: BaseModel, path: str) -> Any:
    """The value at dotted ``path`` in ``spec``; :data:`ABSENT` through a declared ``None``.

    Raises :class:`MethodologyReferenceError` for a path the specification does not have.
    """
    current: Any = spec
    for part in path.split("."):
        if current is None:
            return ABSENT
        if isinstance(current, BaseModel):
            if part not in type(current).model_fields:
                raise MethodologyReferenceError(f"{path}: no field {part!r}")
            current = getattr(current, part)
        elif isinstance(current, Mapping):
            if part not in current:
                raise MethodologyReferenceError(f"{path}: no key {part!r}")
            current = current[part]
        else:
            raise MethodologyReferenceError(f"{path}: {part!r} is below a leaf")
    return current


def _covers(parameter: str, leaf: str) -> bool:
    """A parameter covers a leaf at, above or below it (an optional part omitted or present)."""
    return parameter == leaf or leaf.startswith(parameter + ".") or parameter.startswith(leaf + ".")


# --------------------------------------------------------------------------- code


def _split(reference: str) -> tuple[str, str]:
    module, sep, name = reference.partition(":")
    if not sep or not module or not name:
        raise MethodologyReferenceError(f"{reference!r} is not 'module:name'")
    if not module.startswith(READABLE_PREFIX):
        raise MethodologyReferenceError(
            f"{reference!r}: a catalogue reads only {READABLE_PREFIX}*, the domain shows the domain"
        )
    return module, name


def _lookup(reference: str) -> Any:
    module_name, qualname = _split(reference)
    try:
        current: Any = importlib.import_module(module_name)
    except ImportError as exc:
        raise MethodologyReferenceError(f"{reference!r}: {exc}") from exc
    for part in qualname.split("."):
        if not hasattr(current, part):
            raise MethodologyReferenceError(f"{reference!r}: no attribute {part!r}")
        current = getattr(current, part)
    return current


def read_constant(symbol: str) -> Any:
    """The value of ``module:NAME``, imported; it must be plain data (shown as it is)."""
    value = _lookup(symbol)
    if not _is_plain(value):
        raise MethodologyReferenceError(
            f"{symbol!r} is {type(value).__name__}, not a number, text or a tuple of them"
        )
    return value


def resolve_callable(reference: str) -> Any:
    """The function or class ``module:qualname`` names."""
    value = _lookup(reference)
    if not callable(value):
        raise MethodologyReferenceError(f"{reference!r} is not callable")
    return value


def _is_plain(value: Any) -> bool:
    if value is None or isinstance(value, bool | int | str | Enum):
        return True
    if isinstance(value, float):
        return math.isfinite(value)
    if isinstance(value, tuple | list):
        return all(_is_plain(v) for v in value)
    if isinstance(value, Mapping):
        return all(isinstance(k, str) and _is_plain(v) for k, v in value.items())
    return False


# --------------------------------------------------------------------------- completeness


def module_problems(module: MethodModule) -> dict[str, str]:
    """Everything the module's catalogue gets wrong, keyed by where; empty when complete."""
    problems: dict[str, str] = {}
    steps = module.steps
    ids = [s.id for s in steps]
    for duplicate in sorted({i for i in ids if ids.count(i) > 1}):
        problems[f"step:{duplicate}"] = "step id is used more than once"

    presets = {p.name: p for p in module.presets}
    if len(presets) != len(module.presets):
        problems["presets"] = "preset names are not unique"
    if module.presets and module.in_force not in presets:
        problems["in_force"] = f"{module.in_force!r} is not one of the module's presets"
    if not module.presets and module.in_force is not None:
        problems["in_force"] = "a module without presets has nothing in force"
    for preset in module.presets:
        problems.update(_preset_problems(preset))

    for step in steps:
        problems.update(_step_problems(step, module.presets))

    problems.update(_coverage_problems(module))
    problems.update(_group_problems(module))
    problems.update(_formula_problems(module))
    return problems


def _formula_problems(module: MethodModule) -> dict[str, str]:
    """Each built-in formula belongs to a step, compiles in its slot and keeps its properties."""
    problems: dict[str, str] = {}
    ids = {s.id for s in module.steps}
    slots = [f.slot.id for f in module.formulas]
    for duplicate in sorted({i for i in slots if slots.count(i) > 1}):
        problems[f"slot:{duplicate}"] = "slot id is used more than once"
    for formula in module.formulas:
        where = f"slot:{formula.slot.id}"
        if formula.step_id not in ids:
            problems[f"{where}:step"] = f"no step {formula.step_id!r}"
        try:
            compiled = compile_formula(formula.slot, formula.expression)
        except ExpressionRefused as exc:
            problems[f"{where}:expression"] = str(exc)
            continue
        for prop, why in check_properties(compiled).items():
            problems[f"{where}:{prop}"] = why
    return problems


def _preset_problems(preset: Preset) -> dict[str, str]:
    try:
        preset.validate(preset.spec)
    except Exception as exc:  # the validator's own refusal, reported as it says it
        return {f"preset:{preset.name}": f"its own validator refuses it: {exc}"}
    return {}


def _step_problems(step: MethodStep, presets: tuple[Preset, ...]) -> dict[str, str]:
    problems: dict[str, str] = {}
    where = f"step:{step.id}"
    if not step.formula_latex.strip():
        problems[f"{where}:formula"] = "a step states its formula"
    if len(step.source_sha256) != 64:
        problems[f"{where}:source_sha256"] = "a step pins its function's source by SHA256"
    try:
        resolve_callable(step.implements)
    except MethodologyReferenceError as exc:
        problems[f"{where}:implements"] = str(exc)
    for parameter in step.parameters:
        if not presets:
            problems[f"{where}:{parameter.path}"] = "the module declares no specification"
            continue
        if not any(_resolves(p.spec, parameter.path) for p in presets):
            problems[f"{where}:{parameter.path}"] = "no preset has this path"
    for constant in step.constants:
        try:
            read_constant(constant.symbol)
        except MethodologyReferenceError as exc:
            problems[f"{where}:{constant.symbol}"] = str(exc)
    return problems


def _resolves(spec: BaseModel, path: str) -> bool:
    try:
        read_path(spec, path)
    except MethodologyReferenceError:
        return False
    return True


def _coverage_problems(module: MethodModule) -> dict[str, str]:
    problems: dict[str, str] = {}
    declared = [(s.id, p.path) for s in module.steps for p in s.parameters]
    for preset in module.presets:
        for leaf in leaf_paths(preset.spec):
            readers = sorted({sid for sid, path in declared if _covers(path, leaf)})
            if not readers:
                problems[f"preset:{preset.name}:{leaf}"] = "no step shows this value"
            elif len(readers) > 1:
                problems[f"preset:{preset.name}:{leaf}"] = (
                    f"shown by more than one step: {', '.join(readers)}"
                )
    return problems


def _group_problems(module: MethodModule) -> dict[str, str]:
    if not module.groups:
        return {}
    problems: dict[str, str] = {}
    ids = {s.id for s in module.steps}
    placed: dict[str, str] = {}
    for group in module.groups:
        for sid in group.step_ids:
            if sid not in ids:
                problems[f"group:{group.id}:{sid}"] = "no such step"
            elif sid in placed:
                problems[f"group:{group.id}:{sid}"] = f"already in group {placed[sid]}"
            else:
                placed[sid] = group.id
    for sid in sorted(ids - placed.keys()):
        problems[f"step:{sid}:group"] = "the module groups its steps; this one is in none"
    return problems


# --------------------------------------------------------------------------- the page


class ValueOrigin(StrEnum):
    """Where a shown value comes from (the page labels it)."""

    SPECIFICATION = "specification"  # a field of the module's specification in force
    CODE_CONSTANT = "code_constant"  # a module constant; changed only by a code change


@dataclass(frozen=True, slots=True)
class ValueView:
    reference: str  # a spec path, or module:NAME
    label_cs: str
    unit: str
    origin: ValueOrigin
    value: Any  # ABSENT where the preset omits the part


@dataclass(frozen=True, slots=True)
class StepView:
    step: MethodStep
    values: tuple[ValueView, ...]
    formulas: tuple[BuiltinFormula, ...] = ()


@dataclass(frozen=True, slots=True)
class ModuleView:
    module: MethodModule
    preset: str | None  # the preset whose values are shown; None when nothing is declared
    steps: tuple[StepView, ...]


def describe(module: MethodModule, preset: str | None = None) -> ModuleView:
    """What the tab shows for ``module``: each step with every value read from the code.

    ``preset`` defaults to the one in force. A complete module never raises here; call
    :func:`module_problems` first (the test suite does, for every registered module).
    """
    chosen = preset if preset is not None else module.in_force
    spec: BaseModel | None = None
    if chosen is not None:
        matching = [p for p in module.presets if p.name == chosen]
        if not matching:
            raise MethodologyReferenceError(f"module {module.id!r} has no preset {chosen!r}")
        spec = matching[0].spec
    views: list[StepView] = []
    for step in module.steps:
        values: list[ValueView] = []
        for parameter in step.parameters:
            value = _read_or_absent(spec, parameter.path)
            values.append(
                ValueView(
                    parameter.path,
                    parameter.label_cs,
                    parameter.unit,
                    ValueOrigin.SPECIFICATION,
                    value,
                )
            )
        for constant in step.constants:
            values.append(
                ValueView(
                    constant.symbol,
                    constant.label_cs,
                    constant.unit,
                    ValueOrigin.CODE_CONSTANT,
                    read_constant(constant.symbol),
                )
            )
        formulas = tuple(f for f in module.formulas if f.step_id == step.id)
        views.append(StepView(step, tuple(values), formulas))
    return ModuleView(module, chosen, tuple(views))


def _read_or_absent(spec: BaseModel | None, path: str) -> Any:
    if spec is None:
        raise MethodologyReferenceError(f"{path}: the module declares no specification")
    try:
        value = read_path(spec, path)
    except MethodologyReferenceError:
        # The path exists in another preset (module_problems guarantees one has it) but not
        # in this one: the part is not used by this preset.
        return ABSENT
    # An optional part the preset does not declare is left out of its stored form (an
    # edit starts from that form and cannot set it): absent, not a value of None.
    stored: Any = spec.model_dump(mode="json")
    for part in path.split("."):
        if not isinstance(stored, Mapping) or part not in stored:
            return ABSENT
        stored = stored[part]
    return value
