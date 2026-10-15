"""The Metodika catalogue shows AIA's mathematics from the code, and stays true to it.

ADR 0023 decision 1; plan ``methodology-tab.md`` chunk A1. Two halves:

* the framework, on a small specification and real domain functions: values are read from
  the specification and imported from constants, never copied; every gap in a catalogue is
  reported, all at once;
* every registered module (:data:`MODULES`) is complete, each step's source pin matches the
  function it describes, and each test a step names exists. A function that changes fails
  here until its step is re-read against it and the pin updated; the failure prints the new
  hash.
"""

from __future__ import annotations

import ast
import hashlib
import inspect
from pathlib import Path

import pytest
from pydantic import BaseModel, ConfigDict

from aia_core.domain.methodology import (
    ABSENT,
    MODULES,
    ConstantRef,
    Evidence,
    EvidenceKind,
    MethodModule,
    MethodologyReferenceError,
    MethodStep,
    ParameterRef,
    Preset,
    StepGroup,
    ValueOrigin,
    describe,
    feeds_of,
    leaf_paths,
    module,
    module_problems,
    read_constant,
    read_path,
    resolve_callable,
)
from aia_core.domain.sociomap.metrics import ZERO_VARIANCE_EPSILON, tscore

REPO = Path(__file__).resolve().parents[3]


def source_sha256(reference: str) -> str:
    """The pin a step records: SHA256 of the function's source as ``inspect`` reads it."""
    return hashlib.sha256(inspect.getsource(resolve_callable(reference)).encode()).hexdigest()


def test_reference_exists(reference: str) -> bool:
    """``path::name`` (or ``path::Class::name``) names a test function in that file."""
    path, _, qualname = reference.partition("::")
    file = REPO / path
    if not file.is_file() or not qualname:
        return False
    names = qualname.split("::")
    body: list[ast.stmt] = ast.parse(file.read_text(encoding="utf-8")).body
    for name in names[:-1]:
        classes = [n for n in body if isinstance(n, ast.ClassDef) and n.name == name]
        if not classes:
            return False
        body = classes[0].body
    return any(
        isinstance(n, ast.FunctionDef | ast.AsyncFunctionDef) and n.name == names[-1] for n in body
    )


test_reference_exists.__test__ = False  # type: ignore[attr-defined]  # a helper, not a test


# --------------------------------------------------------------------------- a small module


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class _Scale(_Frozen):
    low: float
    high: float


class _Kernel(_Frozen):
    sigma: float


class _Spec(_Frozen):
    scale: _Scale
    kernel: _Kernel | None
    layout: dict[str, int]


def _accept(spec: BaseModel) -> None:
    assert isinstance(spec, _Spec)
    if spec.scale.low >= spec.scale.high:
        raise ValueError("scale.low must lie below scale.high")


WITH_KERNEL = _Spec(scale=_Scale(low=1, high=10), kernel=_Kernel(sigma=0.25), layout={"it": 5})
WITHOUT_KERNEL = _Spec(scale=_Scale(low=1, high=10), kernel=None, layout={"it": 9})

TSCORE = "aia_core.domain.sociomap.metrics:tscore"
EPSILON = "aia_core.domain.sociomap.metrics:ZERO_VARIANCE_EPSILON"


def _step(step_id: str, **kwargs: object) -> MethodStep:
    defaults: dict[str, object] = {
        "title_cs": step_id,
        "formula_latex": r"T = 50 + 10 z",
        "implements": TSCORE,
        "source_sha256": source_sha256(TSCORE),
    }
    defaults.update(kwargs)
    return MethodStep(id=step_id, **defaults)  # type: ignore[arg-type]


def _module(**kwargs: object) -> MethodModule:
    defaults: dict[str, object] = {
        "id": "toy",
        "title_cs": "Toy",
        "steps": (
            _step(
                "scale",
                parameters=(
                    ParameterRef("scale.low", "dolní konec"),
                    ParameterRef("scale.high", "horní konec"),
                ),
            ),
            _step(
                "kernel",
                parameters=(ParameterRef("kernel.sigma", "šířka", "mapové jednotky"),),
                constants=(ConstantRef(EPSILON, "nulový rozptyl"),),
                evidence=(Evidence(EvidenceKind.FIXTURE, "F6"),),
            ),
            _step("layout", parameters=(ParameterRef("layout.it", "iterace"),)),
        ),
        "presets": (
            Preset("with-kernel", WITH_KERNEL, _accept),
            Preset("without-kernel", WITHOUT_KERNEL, _accept),
        ),
        "in_force": "with-kernel",
    }
    defaults.update(kwargs)
    return MethodModule(**defaults)  # type: ignore[arg-type]


# --------------------------------------------------------------------------- paths and values


def test_leaf_paths_descend_models_and_mappings_and_stop_at_a_declared_none() -> None:
    assert leaf_paths(WITH_KERNEL) == ("scale.low", "scale.high", "kernel.sigma", "layout.it")
    assert leaf_paths(WITHOUT_KERNEL) == ("scale.low", "scale.high", "kernel", "layout.it")


def test_a_path_reads_the_value_and_a_declared_none_reads_absent_not_zero() -> None:
    assert read_path(WITH_KERNEL, "kernel.sigma") == 0.25
    assert read_path(WITH_KERNEL, "layout.it") == 5
    assert read_path(WITHOUT_KERNEL, "kernel.sigma") is ABSENT
    with pytest.raises(MethodologyReferenceError, match="no field 'width'"):
        read_path(WITH_KERNEL, "kernel.width")
    with pytest.raises(MethodologyReferenceError, match="no key 'steps'"):
        read_path(WITH_KERNEL, "layout.steps")
    with pytest.raises(MethodologyReferenceError, match="below a leaf"):
        read_path(WITH_KERNEL, "scale.low.more")


def test_a_constant_is_imported_not_copied() -> None:
    assert read_constant(EPSILON) == ZERO_VARIANCE_EPSILON


def test_only_the_domain_is_readable() -> None:
    with pytest.raises(MethodologyReferenceError, match=r"reads only aia_core\.domain"):
        read_constant("aia_core.application.research:ResearchRuns")
    with pytest.raises(MethodologyReferenceError, match=r"reads only aia_core\.domain"):
        read_constant("os:sep")


def test_a_constant_must_be_plain_data_and_a_function_callable() -> None:
    with pytest.raises(MethodologyReferenceError, match="not a number, text or a tuple"):
        read_constant(TSCORE)
    with pytest.raises(MethodologyReferenceError, match="is not callable"):
        resolve_callable(EPSILON)
    with pytest.raises(MethodologyReferenceError, match="no attribute"):
        resolve_callable("aia_core.domain.sociomap.metrics:no_such_function")
    with pytest.raises(MethodologyReferenceError, match="not 'module:name'"):
        resolve_callable("aia_core.domain.sociomap.metrics.tscore")


# --------------------------------------------------------------------------- completeness


def test_a_complete_module_has_no_problems() -> None:
    assert module_problems(_module()) == {}


def test_a_value_no_step_shows_is_named_per_preset() -> None:
    toy = _module(steps=_module().steps[:2])  # drop the layout step
    assert module_problems(toy) == {
        "preset:with-kernel:layout.it": "no step shows this value",
        "preset:without-kernel:layout.it": "no step shows this value",
    }


def test_a_value_two_steps_show_is_named() -> None:
    steps = (*_module().steps, _step("again", parameters=(ParameterRef("scale.low", "x"),)))
    problems = module_problems(_module(steps=steps))
    assert problems == {
        "preset:with-kernel:scale.low": "shown by more than one step: again, scale",
        "preset:without-kernel:scale.low": "shown by more than one step: again, scale",
    }


def test_an_omitted_optional_part_is_covered_by_the_step_that_reads_inside_it() -> None:
    # without-kernel's leaf is "kernel" (None); the kernel step reads "kernel.sigma"
    assert "preset:without-kernel:kernel" not in module_problems(_module())


def test_every_reference_problem_is_reported_at_once() -> None:
    broken = _step(
        "broken",
        formula_latex=" ",
        implements="aia_core.domain.sociomap.metrics:gone",
        source_sha256="abc",
        parameters=(ParameterRef("scale.middle", "x"),),
        constants=(ConstantRef("aia_core.domain.sociomap.metrics:GONE", "y"),),
    )
    problems = module_problems(_module(steps=(*_module().steps, broken, broken)))
    assert problems.keys() == {
        "step:broken",
        "step:broken:formula",
        "step:broken:source_sha256",
        "step:broken:implements",
        "step:broken:scale.middle",
        "step:broken:aia_core.domain.sociomap.metrics:GONE",
    }
    assert problems["step:broken"] == "step id is used more than once"
    assert problems["step:broken:scale.middle"] == "no preset has this path"


def test_a_preset_its_own_validator_refuses_is_a_problem() -> None:
    bad = _Spec(scale=_Scale(low=10, high=1), kernel=None, layout={"it": 1})
    toy = _module(presets=(*_module().presets, Preset("bad", bad, _accept)))
    assert module_problems(toy) == {
        "preset:bad": "its own validator refuses it: scale.low must lie below scale.high"
    }


def test_in_force_must_name_a_preset() -> None:
    assert module_problems(_module(in_force="other")) == {
        "in_force": "'other' is not one of the module's presets"
    }


def test_a_module_without_a_specification_reads_constants_only() -> None:
    constants_only = _step("eps", constants=(ConstantRef(EPSILON, "nulový rozptyl"),))
    assert module_problems(_module(steps=(constants_only,), presets=(), in_force=None)) == {}
    reads_a_field = _step("x", parameters=(ParameterRef("scale.low", "x"),))
    assert module_problems(_module(steps=(reads_a_field,), presets=(), in_force=None)) == {
        "step:x:scale.low": "the module declares no specification"
    }


def test_groups_hold_every_step_exactly_once() -> None:
    groups = (
        StepGroup("F1", "Vstupy", ("scale", "kernel")),
        StepGroup("F2", "Rozložení", ("kernel", "nothing")),
    )
    assert module_problems(_module(groups=groups)) == {
        "group:F2:kernel": "already in group F1",
        "group:F2:nothing": "no such step",
        "step:layout:group": "the module groups its steps; this one is in none",
    }


def test_a_steps_inputs_name_other_steps_of_its_module_once() -> None:
    steps = (
        _step("scale", inputs=("kernel", "kernel")),
        _step("kernel", inputs=("kernel",)),
        _step("layout", inputs=("nothing",)),
    )
    assert module_problems(_module(steps=steps, presets=(), in_force=None)) == {
        "step:scale:inputs": "an input is named twice",
        "step:kernel:inputs:kernel": "a step cannot read itself",
        "step:layout:inputs:nothing": "no such step",
    }


def test_the_steps_that_read_a_step_are_derived_from_their_inputs() -> None:
    steps = (
        _step("scale"),
        _step("kernel", inputs=("scale",)),
        _step("layout", inputs=("scale", "kernel")),
    )
    toy = _module(steps=steps, presets=(), in_force=None)
    assert feeds_of(toy, "scale") == ("kernel", "layout")
    assert feeds_of(toy, "layout") == ()


# --------------------------------------------------------------------------- the page


def test_describe_reads_every_value_from_the_preset_in_force_and_the_code() -> None:
    view = describe(_module())
    assert view.preset == "with-kernel"
    kernel = next(s for s in view.steps if s.step.id == "kernel")
    assert [(v.reference, v.origin, v.value) for v in kernel.values] == [
        ("kernel.sigma", ValueOrigin.SPECIFICATION, 0.25),
        (EPSILON, ValueOrigin.CODE_CONSTANT, ZERO_VARIANCE_EPSILON),
    ]


def test_describe_another_preset_shows_an_omitted_part_as_absent() -> None:
    view = describe(_module(), "without-kernel")
    kernel = next(s for s in view.steps if s.step.id == "kernel")
    assert kernel.values[0].value is ABSENT
    layout = next(s for s in view.steps if s.step.id == "layout")
    assert layout.values[0].value == 9


def test_describe_refuses_a_preset_the_module_does_not_have() -> None:
    with pytest.raises(MethodologyReferenceError, match="no preset 'gone'"):
        describe(_module(), "gone")


# --------------------------------------------------------------------------- the pins


def test_a_source_pin_moves_when_the_function_changes() -> None:
    assert source_sha256(TSCORE) == hashlib.sha256(inspect.getsource(tscore).encode()).hexdigest()


def test_a_test_reference_is_found_only_where_it_is() -> None:
    here = "packages/aia_core/tests/test_methodology.py"
    assert test_reference_exists(f"{here}::test_a_complete_module_has_no_problems")
    assert not test_reference_exists(f"{here}::test_that_was_never_written")
    assert not test_reference_exists("packages/aia_core/tests/no_such_file.py::test_x")
    assert not test_reference_exists(here)


# --------------------------------------------------------------------------- registered modules


def test_every_registered_module_is_complete() -> None:
    problems = {m.id: module_problems(m) for m in MODULES}
    assert {k: v for k, v in problems.items() if v} == {}


def test_every_step_pin_matches_the_function_it_describes() -> None:
    stale = {
        f"{m.id}/{s.id}": f"{s.implements} is now {source_sha256(s.implements)}; "
        "re-read the step against it, then update its pin"
        for m in MODULES
        for s in m.steps
        if source_sha256(s.implements) != s.source_sha256
    }
    assert stale == {}


def test_every_test_a_step_names_exists() -> None:
    missing = sorted(
        f"{m.id}/{s.id}: {t}"
        for m in MODULES
        for s in m.steps
        for t in s.tests
        if not test_reference_exists(t)
    )
    assert missing == []


def test_module_ids_are_unique_and_found_by_id() -> None:
    ids = [m.id for m in MODULES]
    assert len(ids) == len(set(ids))
    for registered in MODULES:
        assert module(registered.id) is registered
    with pytest.raises(KeyError):
        module("no-such-module")
