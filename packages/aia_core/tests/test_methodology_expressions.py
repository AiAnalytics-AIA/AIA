"""The formula language: what parses, what it computes, what it refuses, how it is written.

ADR 0023 decision 4; plan ``methodology-tab.md`` chunk A2. A formula is the methodologist's
code, so the refusals are the point: nothing but arithmetic over the slot's own variables and
the listed functions may run, with no ``eval``. A formula written the way the engine computes
gives the engine's bits exactly (the terrain kernel, the Fisher bound, Kish's n), which is
what lets a built-in formula become an expression without moving a result (chunk S3).
"""

from __future__ import annotations

import inspect
import math
import random
import time
from statistics import NormalDist

import pytest

from aia_core.domain.methodology import expressions
from aia_core.domain.methodology.expressions import (
    MAX_FORMULA_LENGTH,
    ExpressionDomainError,
    ExpressionRefused,
    Property,
    PropertyKind,
    Slot,
    Variable,
    check_properties,
    compile_formula,
    latex,
)
from aia_core.domain.sociomap.relations import fisher_interval, kish_effective_n
from aia_core.domain.sociomap.terrain import EnvelopeHill, envelope_at

# --------------------------------------------------------------------------- slots used here

KERNEL = Slot(
    id="terrain.kernel",
    title_cs="Jádro kopce",
    variables=(
        Variable("h", "h_j", "výška objektu", (0.0, 0.3, 1.0)),
        Variable(
            "d2", r"\lVert q - y_j\rVert^2", "čtverec vzdálenosti", (0.0, 0.01, 0.25, 1.0, 4.0)
        ),
        Variable("sigma", r"\sigma", "šířka", (0.1, 0.25, 1.0)),
    ),
    properties=(
        Property(PropertyKind.NON_NEGATIVE),
        Property(PropertyKind.EQUALS_AT, at={"h": 1.0, "d2": 0.0, "sigma": 0.25}, value=1.0),
        Property(PropertyKind.NON_INCREASING_IN, variable="d2"),
    ),
)
KISH = Slot(
    id="relation.effective_n",
    title_cs="Efektivní n",
    variables=(
        Variable(
            "w",
            "w",
            "váhy respondentů páru",
            ((1.0, 1.0, 1.0), (0.5, 2.0, 1.0, 3.0), (1e-3, 5.0)),
            vector=True,
        ),
    ),
    properties=(
        Property(PropertyKind.NON_NEGATIVE),
        Property(PropertyKind.AT_MOST_VARIABLE, variable="w"),
    ),
)
FISHER = Slot(
    id="relation.interval_low",
    title_cs="Dolní mez",
    variables=(
        Variable("r", "r", "korelace", (-0.9, -0.2, 0.0, 0.4, 0.95)),
        Variable("n", "n", "vzorek páru", (4.0, 30.0, 512.5)),
        Variable("z", "z_c", "kvantil", (1.959963984540054,)),
    ),
)


# --------------------------------------------------------------------------- the engine's bits


def test_the_kernel_written_as_the_engine_computes_it_gives_the_engines_bits() -> None:
    kernel = compile_formula(KERNEL, "h * exp(-d2 / (2 * sigma * sigma))")
    rng = random.Random(20261011)
    for _ in range(500):
        hx, hy, x, y = (rng.uniform(-2, 2) for _ in range(4))
        h, sigma = rng.uniform(0, 1), rng.uniform(0.05, 1)
        hit = envelope_at(x, y, [EnvelopeHill(entity_id="o", x=hx, y=hy, height=h)], sigma, 0.0)
        assert hit is not None
        assert kernel(h=h, d2=(x - hx) ** 2 + (y - hy) ** 2, sigma=sigma) == hit[0]


def test_the_fisher_bound_written_as_the_engine_computes_it_gives_the_engines_bits() -> None:
    low = compile_formula(FISHER, "tanh(atanh(r) - z / sqrt(n - 3))")
    z = NormalDist().inv_cdf(0.5 + 0.95 / 2)  # the engine's own z_c
    for r in (-0.93, -0.31, 0.0, 0.12, 0.77):
        for n in (4, 9, 30, 731.25):
            interval = fisher_interval(r, n, 0.95)
            assert interval is not None
            assert low(r=r, n=n, z=z) == interval[0]


def test_kish_written_as_the_engine_computes_it_gives_the_engines_bits() -> None:
    kish = compile_formula(KISH, "sum(w) ** 2 / sum(w * w)")
    rng = random.Random(7)
    for _ in range(200):
        w = tuple(rng.uniform(0.01, 5) for _ in range(rng.randint(1, 40)))
        assert kish(w=w) == kish_effective_n(w)


# --------------------------------------------------------------------------- the language


def test_vectors_broadcast_and_aggregates_reduce() -> None:
    f = compile_formula(KISH, "mean(w * 2 + 1) - count(w) + max(w) - min(w)")
    assert f(w=(1.0, 3.0)) == (3.0 + 7.0) / 2 - 2 + 3 - 1
    assert compile_formula(KISH, "w * 2")(w=(1.0, 2.0)) == (2.0, 4.0)


def test_conditions_and_comparisons() -> None:
    f = compile_formula(FISHER, "1 if r > 0 and n >= 30 else (0.5 if not r < 0 else 0)")
    assert f(r=0.2, n=30, z=1.0) == 1.0
    assert f(r=0.0, n=4, z=1.0) == 0.5
    assert f(r=-0.1, n=4, z=1.0) == 0.0
    assert compile_formula(FISHER, "clip(r * 3, -1, 1)")(r=0.5, n=4, z=1) == 1.0
    assert compile_formula(FISHER, "phi(phi_inv(0.975))")(r=0, n=4, z=1) == pytest.approx(0.975)


@pytest.mark.parametrize(
    ("text", "code"),
    [
        ("__import__('os').system('true')", "unknown_function"),
        ("r.__class__", "construct"),
        ("open('x')", "unknown_function"),
        ("eval('1')", "unknown_function"),
        ("(lambda: 1)()", "unknown_function"),
        ("[x for x in w]", "construct"),
        ("{'a': 1}", "construct"),
        ("w[0]", "construct"),
        ("'text'", "not_a_number"),
        ("True", "not_a_number"),
        ("q + 1", "unknown_name"),
        ("exp(x=1)", "keyword"),
        ("exp(1, 2)", "arity"),
        ("0 < r < 1", "comparison"),
        ("r // 2", "operator"),
        ("r @ r", "operator"),
        ("~r", "operator"),
        ("r if", "syntax"),
        ("", "empty"),
        ("r = 1", "syntax"),
        ("*w", "syntax"),
        ("exp(*w)", "construct"),
    ],
)
def test_anything_but_arithmetic_over_the_slots_variables_is_refused(text: str, code: str) -> None:
    with pytest.raises(ExpressionRefused) as refused:
        compile_formula(FISHER, text)
    assert refused.value.code == code


def test_a_huge_or_deep_formula_is_refused_before_it_runs() -> None:
    with pytest.raises(ExpressionRefused) as long:
        compile_formula(FISHER, "r + " * MAX_FORMULA_LENGTH + "r")
    assert long.value.code == "too_long"
    with pytest.raises(ExpressionRefused) as deep:
        compile_formula(FISHER, "(" * 200 + "r" + ")" * 200 + " + " + "-" * 150 + "r")
    assert deep.value.code == "too_deep"


def test_no_value_where_there_is_none_is_a_domain_error_never_a_number() -> None:
    for text, values in (
        ("1 / (r - r)", {"r": 0.3}),
        ("log(r)", {"r": -1.0}),
        ("atanh(r)", {"r": 1.0}),
        ("exp(n)", {"n": 1000.0}),
        ("n ** 1000", {"n": 1e10}),
    ):
        f = compile_formula(FISHER, text)
        with pytest.raises(ExpressionDomainError):
            f(**{"r": 0.1, "n": 5.0, "z": 1.0, **values})
    with pytest.raises(ExpressionDomainError):
        compile_formula(KISH, "mean(w)")(w=())


def test_the_language_never_evaluates_text() -> None:
    source = inspect.getsource(expressions)
    assert "eval(" not in source.replace('mode="eval"', "").replace("``eval``", "")
    assert "exec(" not in source.replace("``exec``", "")


# --------------------------------------------------------------------------- LaTeX


def test_latex_is_written_from_the_formula_itself() -> None:
    assert latex(compile_formula(KISH, "sum(w) ** 2 / sum(w * w)")) == (
        r"\frac{{\left(\sum w\right)}^{2}}{\sum w \cdot w}"
    )
    kernel = latex(compile_formula(KERNEL, "h * exp(-d2 / (2 * sigma * sigma))"))
    assert kernel == (
        r"h_j \cdot \exp\left(\frac{-\lVert q - y_j\rVert^2}{2 \cdot \sigma \cdot \sigma}\right)"
    )
    assert latex(compile_formula(FISHER, "r - (n - z)")) == r"r - \left(n - z_c\right)"
    assert latex(compile_formula(FISHER, "(r + n) * z")) == r"\left(r + n\right) \cdot z_c"
    assert latex(compile_formula(FISHER, "1e-12 * r")) == r"10^{-12} \cdot r"
    assert latex(compile_formula(FISHER, "2.5e-7 * r")) == r"2.5 \cdot 10^{-7} \cdot r"
    cases = latex(compile_formula(FISHER, "1 if r > 0 else 0"))
    assert cases == r"\begin{cases} 1 & r > 0 \\ 0 & \text{jinak} \end{cases}"


# --------------------------------------------------------------------------- properties


def test_the_engines_kernel_keeps_every_property_of_its_slot() -> None:
    assert check_properties(compile_formula(KERNEL, "h * exp(-d2 / (2 * sigma * sigma))")) == {}


def test_a_formula_that_breaks_a_property_is_named_with_a_counterexample() -> None:
    rising = check_properties(compile_formula(KERNEL, "h * exp(d2 / (2 * sigma * sigma))"))
    assert set(rising) == {"non_increasing_in:d2"}
    assert "rises" in rising["non_increasing_in:d2"]
    shifted = check_properties(compile_formula(KERNEL, "h * exp(-d2 / sigma) - 0.5"))
    assert set(shifted) == {"non_negative", "equals_at"}
    assert check_properties(compile_formula(KISH, "count(w) + 1")).keys() == {"at_most_variable:w"}


def test_no_finite_value_on_the_grid_is_refused_there() -> None:
    problems = check_properties(compile_formula(KERNEL, "h * log(d2)"))
    assert problems.keys() == {"finite"}
    assert "d2=0.0" in problems["finite"]
    vector = check_properties(compile_formula(KISH, "w * 1"))
    assert vector == {"finite": "at w=(1.0, 1.0, 1.0): a vector, not one number"}


def test_a_missing_value_is_refused_not_defaulted() -> None:
    with pytest.raises(ExpressionRefused) as refused:
        compile_formula(KERNEL, "h")(h=1.0)
    assert refused.value.code == "missing_value"


# --------------------------------------------------------------------------- cost


def test_a_terrain_of_formula_kernels_costs_what_the_plan_records() -> None:
    """65 x 65 cells x 30 hills, the object map's envelope at its declared grid: measured,
    and bounded generously (CLAUDE.md § 7) -- the number is recorded in the plan."""
    kernel = compile_formula(KERNEL, "h * exp(-d2 / (2 * sigma * sigma))")
    started = time.perf_counter()
    for i in range(65 * 65 * 30):
        kernel(h=0.5, d2=(i % 97) / 50.0, sigma=0.25)
    elapsed = time.perf_counter() - started
    assert elapsed < 60.0
    assert math.isfinite(elapsed)
