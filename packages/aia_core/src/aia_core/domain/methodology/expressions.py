"""Formulas the methodologist writes, as expressions the engine evaluates (ADR 0023 decision 4).

A **slot** is a formula with a declared signature: its variables (scalars, or vectors over a
declared index such as the respondents who rated both objects), their meaning, unit and
domain, and the properties any formula in it must keep. A formula is written in a small
language -- Python's expression syntax, restricted:

* numbers; the slot's own variable names; ``+ - * / **``; comparisons; ``and or not``;
  ``a if condition else b``;
* the functions in :data:`FUNCTIONS`: ``exp log sqrt abs floor tanh atanh min max clip``,
  ``phi`` (the standard normal CDF) and ``phi_inv``, and the aggregates ``sum mean count``
  (``min`` / ``max`` of one vector also aggregate);
* arithmetic between a vector and a scalar or another vector of the same length is element by
  element; an aggregate turns a vector into a scalar.

Nothing else parses into a formula: no other name, attribute, subscript, call, string,
comprehension or lambda. :func:`compile_formula` parses with :func:`ast.parse`, checks every
node against that whitelist, and builds a closure over :mod:`math`; no text ever reaches
``eval`` or ``exec``. A formula has no loop, no I/O and no randomness, so it ends and it is
deterministic.

:func:`latex` writes the formula's LaTeX from the same tree, so what the Metodika tab shows is
what runs. :func:`check_properties` evaluates a formula on its slot's grid and reports every
declared property it breaks; a value that is NaN or infinite anywhere on the slot's domain is
refused there, never coerced (``CLAUDE.md`` § 8).

Pure: stdlib only.
"""

from __future__ import annotations

import ast
import itertools
import math
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from statistics import NormalDist
from typing import Final

__all__ = [
    "FUNCTIONS",
    "MAX_FORMULA_LENGTH",
    "CompiledFormula",
    "ExpressionDomainError",
    "ExpressionRefused",
    "Property",
    "PropertyKind",
    "Slot",
    "Value",
    "Variable",
    "check_properties",
    "compile_formula",
    "latex",
]

type Value = float | tuple[float, ...]
type _Env = Mapping[str, Value]
type _Node = Callable[[_Env], Value]

#: Longer than any formula a person writes; a bound, so a pasted blob is refused at once.
MAX_FORMULA_LENGTH: Final = 2000
#: The deepest nesting a formula may have (Python's own parser recurses on it).
_MAX_DEPTH: Final = 60
_NORMAL: Final = NormalDist()


class ExpressionRefused(ValueError):
    """The text is not a formula this slot accepts. ``code`` says why; ``column`` where."""

    def __init__(self, code: str, message: str, column: int | None = None) -> None:
        self.code = code
        self.column = column
        where = "" if column is None else f" (at column {column + 1})"
        super().__init__(f"{message}{where}")


class ExpressionDomainError(ArithmeticError):
    """Evaluated where it has no finite value: a division by zero, a log of a negative, ..."""


# --------------------------------------------------------------------------- slots


@dataclass(frozen=True, slots=True)
class Variable:
    """One name a formula in the slot may use.

    ``samples`` are the points :func:`check_properties` evaluates at (for a vector variable,
    each sample is a whole vector). ``latex`` is how the variable is written on the page.
    """

    name: str
    latex: str
    meaning_cs: str
    samples: tuple[Value, ...]
    unit: str = ""
    vector: bool = False


class PropertyKind(StrEnum):
    """What a formula in a slot must keep, checked on the slot's grid."""

    FINITE = "finite"  # every value is a finite number (always checked)
    SCALAR = "scalar"  # the result is one number, not a vector
    NON_NEGATIVE = "non_negative"
    WITHIN = "within"  # lo <= value <= hi
    EQUALS_AT = "equals_at"  # at the given point, the value is the given number
    NON_INCREASING_IN = "non_increasing_in"  # in one variable, the others fixed
    NON_DECREASING_IN = "non_decreasing_in"
    AT_MOST_VARIABLE = "at_most_variable"  # value <= another variable's value (or its length)
    AT_LEAST_VARIABLE = "at_least_variable"  # value >= another variable's value


@dataclass(frozen=True, slots=True)
class Property:
    kind: PropertyKind
    variable: str | None = None
    lo: float | None = None
    hi: float | None = None
    at: Mapping[str, Value] = field(default_factory=dict)
    value: float | None = None
    description_cs: str = ""


@dataclass(frozen=True, slots=True)
class Slot:
    """A formula with a declared signature (ADR 0023 decision 4)."""

    id: str
    title_cs: str
    variables: tuple[Variable, ...]
    properties: tuple[Property, ...] = ()

    def variable(self, name: str) -> Variable:
        for v in self.variables:
            if v.name == name:
                return v
        raise KeyError(name)


# --------------------------------------------------------------------------- the language


@dataclass(frozen=True, slots=True)
class _Function:
    arity: tuple[int, ...]  # accepted argument counts
    latex: Callable[[list[str]], str]
    aggregate: bool = False  # a vector in, a scalar out


def _f(name: str) -> Callable[[list[str]], str]:
    return lambda a: rf"\operatorname{{{name}}}\left({', '.join(a)}\right)"


FUNCTIONS: Final[Mapping[str, _Function]] = {
    "exp": _Function((1,), lambda a: rf"\exp\left({a[0]}\right)"),
    "log": _Function((1,), lambda a: rf"\ln\left({a[0]}\right)"),
    "sqrt": _Function((1,), lambda a: rf"\sqrt{{{a[0]}}}"),
    "abs": _Function((1,), lambda a: rf"\left|{a[0]}\right|"),
    "floor": _Function((1,), lambda a: rf"\left\lfloor {a[0]} \right\rfloor"),
    "tanh": _Function((1,), lambda a: rf"\tanh\left({a[0]}\right)"),
    "atanh": _Function((1,), lambda a: rf"\operatorname{{atanh}}\left({a[0]}\right)"),
    "phi": _Function((1,), lambda a: rf"\Phi\left({a[0]}\right)"),
    "phi_inv": _Function((1,), lambda a: rf"\Phi^{{-1}}\left({a[0]}\right)"),
    "clip": _Function(
        (3,), lambda a: rf"\operatorname{{clip}}_{{[{a[1]},\,{a[2]}]}}\left({a[0]}\right)"
    ),
    "min": _Function((1, 2), lambda a: rf"\min\left({', '.join(a)}\right)"),
    "max": _Function((1, 2), lambda a: rf"\max\left({', '.join(a)}\right)"),
    "sum": _Function((1,), lambda a: rf"\sum {a[0]}", aggregate=True),
    "mean": _Function((1,), lambda a: rf"\overline{{{a[0]}}}", aggregate=True),
    "count": _Function((1,), lambda a: rf"\#\left({a[0]}\right)", aggregate=True),
}

_BINARY: Final[Mapping[type[ast.operator], Callable[[float, float], float]]] = {
    ast.Add: lambda x, y: x + y,
    ast.Sub: lambda x, y: x - y,
    ast.Mult: lambda x, y: x * y,
    ast.Div: lambda x, y: x / y,
    ast.Pow: lambda x, y: x**y,
}
_COMPARE: Final[Mapping[type[ast.cmpop], Callable[[float, float], bool]]] = {
    ast.Lt: lambda x, y: x < y,
    ast.LtE: lambda x, y: x <= y,
    ast.Gt: lambda x, y: x > y,
    ast.GtE: lambda x, y: x >= y,
    ast.Eq: lambda x, y: x == y,
    ast.NotEq: lambda x, y: x != y,
}


def _finite(value: float) -> float:
    if not math.isfinite(value):
        raise ExpressionDomainError(f"the value is {value!r}, not a finite number")
    return value


def _scalar(fn: Callable[..., float], *args: float) -> float:
    try:
        return _finite(float(fn(*args)))
    except (ValueError, ZeroDivisionError, OverflowError) as exc:
        raise ExpressionDomainError(str(exc)) from exc


def _broadcast(fn: Callable[..., float], *args: Value) -> Value:
    """Apply ``fn`` element by element where an argument is a vector."""
    lengths = {len(a) for a in args if isinstance(a, tuple)}
    if not lengths:
        return _scalar(fn, *(float(a) for a in args if not isinstance(a, tuple)))
    if len(lengths) > 1:
        raise ExpressionDomainError(f"vectors of different lengths: {sorted(lengths)}")
    (n,) = lengths
    return tuple(
        _scalar(fn, *(a[i] if isinstance(a, tuple) else a for a in args)) for i in range(n)
    )


def _aggregate(name: str, value: Value) -> float:
    if not isinstance(value, tuple):
        raise ExpressionDomainError(f"{name} reads a vector; it was given one number")
    if name == "count":
        return float(len(value))
    if not value:
        raise ExpressionDomainError(f"{name} of an empty vector has no value")
    if name == "sum":
        return _finite(math.fsum(value))
    if name == "mean":
        return _finite(math.fsum(value) / len(value))
    return _finite(min(value) if name == "min" else max(value))


_ELEMENTWISE: Final[Mapping[str, Callable[..., float]]] = {
    "exp": math.exp,
    "log": math.log,
    "sqrt": math.sqrt,
    "abs": abs,
    "floor": lambda x: float(math.floor(x)),
    "tanh": math.tanh,
    "atanh": math.atanh,
    "phi": _NORMAL.cdf,
    "phi_inv": _NORMAL.inv_cdf,
    "clip": lambda x, lo, hi: min(max(x, lo), hi),
    "min": min,
    "max": max,
}


class _Compiler:
    def __init__(self, slot: Slot) -> None:
        self.names = {v.name for v in slot.variables}

    def build(self, node: ast.AST, depth: int = 0) -> _Node:
        if depth > _MAX_DEPTH:
            raise ExpressionRefused("too_deep", "the formula nests too deeply")
        column = getattr(node, "col_offset", None)
        d = depth + 1
        if isinstance(node, ast.Constant):
            if isinstance(node.value, bool) or not isinstance(node.value, int | float):
                raise ExpressionRefused("not_a_number", f"{node.value!r} is not a number", column)
            number = _finite(float(node.value))
            return lambda env: number
        if isinstance(node, ast.Name):
            if node.id not in self.names:
                raise ExpressionRefused(
                    "unknown_name",
                    f"{node.id!r} is not a variable of this slot ({', '.join(sorted(self.names))})",
                    column,
                )
            name = node.id
            return lambda env: env[name]
        if isinstance(node, ast.BinOp):
            op = _BINARY.get(type(node.op))
            if op is None:
                raise ExpressionRefused("operator", "only + - * / ** are allowed", column)
            left, right = self.build(node.left, d), self.build(node.right, d)
            return lambda env: _broadcast(op, left(env), right(env))
        if isinstance(node, ast.UnaryOp):
            operand = self.build(node.operand, d)
            if isinstance(node.op, ast.USub):
                return lambda env: _broadcast(lambda x: -x, operand(env))
            if isinstance(node.op, ast.UAdd):
                return operand
            if isinstance(node.op, ast.Not):
                return lambda env: _broadcast(lambda x: 0.0 if x else 1.0, operand(env))
            raise ExpressionRefused("operator", "only - + not apply to one value", column)
        if isinstance(node, ast.Compare):
            if len(node.ops) != 1:
                raise ExpressionRefused("comparison", "compare two values at a time", column)
            cmp = _COMPARE.get(type(node.ops[0]))
            if cmp is None:
                raise ExpressionRefused("comparison", "only < <= > >= == != compare", column)
            left, right = self.build(node.left, d), self.build(node.comparators[0], d)
            return lambda env: _broadcast(
                lambda x, y: 1.0 if cmp(x, y) else 0.0, left(env), right(env)
            )
        if isinstance(node, ast.BoolOp):
            parts = [self.build(v, d) for v in node.values]
            if isinstance(node.op, ast.And):
                return lambda env: _broadcast(
                    lambda *xs: 1.0 if all(xs) else 0.0, *(p(env) for p in parts)
                )
            return lambda env: _broadcast(
                lambda *xs: 1.0 if any(xs) else 0.0, *(p(env) for p in parts)
            )
        if isinstance(node, ast.IfExp):
            test, body, orelse = (self.build(n, d) for n in (node.test, node.body, node.orelse))
            return lambda env: _choose(test(env), body, orelse, env)
        if isinstance(node, ast.Call):
            return self._call(node, d)
        raise ExpressionRefused(
            "construct", f"{type(node).__name__} is not part of the formula language", column
        )

    def _call(self, node: ast.Call, depth: int) -> _Node:
        column = node.col_offset
        if not isinstance(node.func, ast.Name) or node.func.id not in FUNCTIONS:
            name = node.func.id if isinstance(node.func, ast.Name) else "this"
            raise ExpressionRefused(
                "unknown_function",
                f"{name!r} is not a function of the formula language ({', '.join(FUNCTIONS)})",
                column,
            )
        if node.keywords:
            raise ExpressionRefused("keyword", "functions take positional values only", column)
        name = node.func.id
        spec = FUNCTIONS[name]
        if len(node.args) not in spec.arity:
            raise ExpressionRefused(
                "arity", f"{name} takes {' or '.join(map(str, spec.arity))} value(s)", column
            )
        args = [self.build(a, depth) for a in node.args]
        if spec.aggregate or (name in ("min", "max") and len(args) == 1):
            (arg,) = args
            return lambda env: _aggregate(name, arg(env))
        fn = _ELEMENTWISE[name]
        return lambda env: _broadcast(fn, *(a(env) for a in args))


def _choose(test: Value, body: _Node, orelse: _Node, env: _Env) -> Value:
    if not isinstance(test, tuple):
        return body(env) if test else orelse(env)
    yes, no = body(env), orelse(env)
    return tuple(
        (yes[i] if isinstance(yes, tuple) else yes)
        if t
        else (no[i] if isinstance(no, tuple) else no)
        for i, t in enumerate(test)
    )


# --------------------------------------------------------------------------- compile


@dataclass(frozen=True, slots=True)
class CompiledFormula:
    """A formula accepted for its slot: its text, its tree, and the closure that evaluates it."""

    slot: Slot
    text: str
    tree: ast.Expression
    _run: _Node

    def __call__(self, **values: Value) -> Value:
        missing = {v.name for v in self.slot.variables} - values.keys()
        if missing:
            raise ExpressionRefused("missing_value", f"no value for {', '.join(sorted(missing))}")
        env = {
            k: (tuple(float(x) for x in v) if isinstance(v, tuple | list) else float(v))
            for k, v in values.items()
        }
        return self._run(env)


def compile_formula(slot: Slot, text: str) -> CompiledFormula:
    """``text`` as a formula of ``slot``, or :class:`ExpressionRefused` saying why not."""
    if not isinstance(text, str) or not text.strip():
        raise ExpressionRefused("empty", "a formula is written, not left blank")
    if len(text) > MAX_FORMULA_LENGTH:
        raise ExpressionRefused("too_long", f"a formula is at most {MAX_FORMULA_LENGTH} characters")
    try:
        tree = ast.parse(text.strip(), mode="eval")
    except SyntaxError as exc:
        raise ExpressionRefused(
            "syntax", f"not a formula: {exc.msg}", (exc.offset or 1) - 1
        ) from exc
    except (RecursionError, MemoryError) as exc:  # a pathological input never gets further
        raise ExpressionRefused("too_deep", "the formula nests too deeply") from exc
    run = _Compiler(slot).build(tree.body)
    return CompiledFormula(slot=slot, text=text.strip(), tree=tree, _run=run)


# --------------------------------------------------------------------------- LaTeX

_PRECEDENCE: Final = {
    ast.BoolOp: 1,
    ast.Compare: 3,
    ast.Add: 4,
    ast.Sub: 4,
    ast.Mult: 5,
    ast.Div: 5,
    ast.UnaryOp: 6,
    ast.Pow: 7,
}
_CMP_LATEX: Final = {
    ast.Lt: "<",
    ast.LtE: r"\le",
    ast.Gt: ">",
    ast.GtE: r"\ge",
    ast.Eq: "=",
    ast.NotEq: r"\ne",
}


def latex(formula: CompiledFormula) -> str:
    """The formula's LaTeX, written from its own tree: what the page shows is what runs."""
    names = {v.name: v.latex for v in formula.slot.variables}
    return _tex(formula.tree.body, names)


def _number(value: float) -> str:
    text = repr(int(value)) if float(value).is_integer() and abs(value) < 1e15 else repr(value)
    if "e" in text:
        mantissa, exponent = text.split("e")
        power = rf"10^{{{int(exponent)}}}"
        return power if float(mantissa) == 1.0 else rf"{mantissa} \cdot {power}"
    return text


def _prec(node: ast.AST) -> int:
    if isinstance(node, ast.BinOp):
        return _PRECEDENCE[type(node.op)]
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
        # An aggregate binds like a sum: (sum w)^2 is not sum (w^2).
        return 4 if FUNCTIONS[node.func.id].aggregate else 9
    return _PRECEDENCE.get(type(node), 9)


def _wrap(node: ast.AST, names: Mapping[str, str], below: int) -> str:
    inner = _tex(node, names)
    return rf"\left({inner}\right)" if _prec(node) < below else inner


def _tex(node: ast.AST, names: Mapping[str, str]) -> str:
    if isinstance(node, ast.Constant):
        assert isinstance(node.value, int | float)  # compile_formula admitted only numbers
        return _number(float(node.value))
    if isinstance(node, ast.Name):
        return names[node.id]
    if isinstance(node, ast.BinOp):
        p = _prec(node)
        if isinstance(node.op, ast.Div):
            return rf"\frac{{{_tex(node.left, names)}}}{{{_tex(node.right, names)}}}"
        if isinstance(node.op, ast.Pow):
            return rf"{{{_wrap(node.left, names, p + 1)}}}^{{{_tex(node.right, names)}}}"
        symbol = {ast.Add: "+", ast.Sub: "-", ast.Mult: r"\cdot"}[type(node.op)]
        right_below = p + 1 if isinstance(node.op, ast.Sub) else p
        return f"{_wrap(node.left, names, p)} {symbol} {_wrap(node.right, names, right_below)}"
    if isinstance(node, ast.UnaryOp):
        operand = _wrap(node.operand, names, _PRECEDENCE[ast.UnaryOp])
        return {ast.USub: f"-{operand}", ast.UAdd: operand, ast.Not: rf"\lnot {operand}"}[
            type(node.op)
        ]
    if isinstance(node, ast.Compare):
        return (
            f"{_tex(node.left, names)} {_CMP_LATEX[type(node.ops[0])]} "
            f"{_tex(node.comparators[0], names)}"
        )
    if isinstance(node, ast.BoolOp):
        joiner = r" \wedge " if isinstance(node.op, ast.And) else r" \vee "
        return joiner.join(_wrap(v, names, 2) for v in node.values)
    if isinstance(node, ast.IfExp):
        return (
            rf"\begin{{cases}} {_tex(node.body, names)} & {_tex(node.test, names)} \\ "
            rf"{_tex(node.orelse, names)} & \text{{jinak}} \end{{cases}}"
        )
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
        return FUNCTIONS[node.func.id].latex([_tex(a, names) for a in node.args])
    raise ExpressionRefused("construct", f"{type(node).__name__} has no LaTeX")  # unreachable


# --------------------------------------------------------------------------- properties


def _grid(slot: Slot) -> list[dict[str, Value]]:
    names = [v.name for v in slot.variables]
    return [
        dict(zip(names, point, strict=True))
        for point in itertools.product(*(v.samples for v in slot.variables))
    ]


def _number_at(formula: CompiledFormula, point: Mapping[str, Value]) -> float | str:
    try:
        value = formula(**point)
    except ExpressionDomainError as exc:
        return f"no finite value: {exc}"
    if isinstance(value, tuple):
        return "a vector, not one number"
    return value


def check_properties(formula: CompiledFormula) -> dict[str, str]:
    """Every property of the slot ``formula`` breaks on the slot's grid; empty when none.

    A formula must give one finite number at every grid point (``FINITE``, always checked),
    then keep each declared property. The first counter-example of each is reported.
    """
    problems: dict[str, str] = {}
    grid = _grid(formula.slot)
    values: list[tuple[dict[str, Value], float]] = []
    for point in grid:
        got = _number_at(formula, point)
        if isinstance(got, str):
            problems.setdefault("finite", f"at {_show(point)}: {got}")
        else:
            values.append((point, got))
    if "finite" in problems:
        return problems
    for prop in formula.slot.properties:
        found = _counterexample(formula, prop, values)
        if found is not None:
            problems[prop.kind.value + (f":{prop.variable}" if prop.variable else "")] = found
    return problems


def _counterexample(
    formula: CompiledFormula, prop: Property, values: Sequence[tuple[dict[str, Value], float]]
) -> str | None:
    kind = prop.kind
    if kind in (PropertyKind.FINITE, PropertyKind.SCALAR):
        return None  # checked for every point above
    if kind is PropertyKind.NON_NEGATIVE:
        for point, v in values:
            if v < 0:
                return f"at {_show(point)} the value is {v!r} < 0"
        return None
    if kind is PropertyKind.WITHIN:
        lo = -math.inf if prop.lo is None else prop.lo
        hi = math.inf if prop.hi is None else prop.hi
        for point, v in values:
            if not lo <= v <= hi:
                return f"at {_show(point)} the value is {v!r}, outside [{prop.lo}, {prop.hi}]"
        return None
    if kind is PropertyKind.EQUALS_AT:
        got = _number_at(formula, prop.at)
        if got != prop.value:
            return f"at {_show(prop.at)} the value must be {prop.value!r}; it is {got!r}"
        return None
    if kind in (PropertyKind.AT_MOST_VARIABLE, PropertyKind.AT_LEAST_VARIABLE):
        assert prop.variable is not None
        at_most = kind is PropertyKind.AT_MOST_VARIABLE
        for point, v in values:
            bound = point[prop.variable]
            limit = float(len(bound)) if isinstance(bound, tuple) else bound
            slack = 1e-12 * max(1.0, abs(limit))
            if (v > limit + slack) if at_most else (v < limit - slack):
                way = "exceeds" if at_most else "falls below"
                return f"at {_show(point)} the value {v!r} {way} {prop.variable} = {limit!r}"
        return None
    assert prop.variable is not None
    rising = kind is PropertyKind.NON_DECREASING_IN
    others = [v.name for v in formula.slot.variables if v.name != prop.variable]
    series: dict[tuple[object, ...], list[tuple[object, float]]] = {}
    order = list(formula.slot.variable(prop.variable).samples)
    for point, v in values:
        key = tuple(_key(point[n]) for n in others)
        series.setdefault(key, []).append((point[prop.variable], v))
    for line in series.values():
        line.sort(key=lambda item: order.index(item[0]))  # type: ignore[arg-type]
        for (x0, v0), (x1, v1) in itertools.pairwise(line):
            if (v1 < v0) if rising else (v1 > v0):
                way = "falls" if rising else "rises"
                return f"it {way} from {v0!r} to {v1!r} as {prop.variable} goes {x0!r} -> {x1!r}"
    return None


def _key(value: Value) -> object:
    return value


def _show(point: Mapping[str, Value]) -> str:
    return ", ".join(f"{k}={v!r}" for k, v in point.items())
