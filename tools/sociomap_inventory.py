#!/usr/bin/env python3
"""Generate a function-level inventory of the legacy Sociomapping modules.

The production Sociomapa engine must be ported from the NPC Panel reference, not
invented. The first step of that port is a table of what the reference actually
does, function by function: inputs, outputs, module constants that act as hidden
methodology defaults, sources of randomness, and mutable module state. This tool
produces that table from the real source with the ``ast`` module -- it never
imports or executes the reference.

Usage::

    python tools/sociomap_inventory.py                      # markdown to stdout
    python tools/sociomap_inventory.py --format json
    python tools/sociomap_inventory.py --module sociomap.py --module visualization_lab.py
    python tools/sociomap_inventory.py --reference /path/to/npc-panel-reference

The reference path comes from ``AIA_LEGACY_REFERENCE``, defaulting to
``../npc-panel-reference``. When it is absent the tool exits with status 2 and
says so plainly, so a missing checkout can never be mistaken for an empty module.

The output columns *Responsibility*, *Classification*, *Production destination*
and *Parity requirement* are left for a person to fill in after reading the code:
the tool reports facts, it does not classify methodology.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path

# Modules the migration documents name as the legacy Sociomapa subsystem
# (docs/architecture/domain-map.md, docs/migration/parity-matrix.md).
DEFAULT_MODULES: tuple[str, ...] = (
    "sociomap.py",
    "visualization_lab.py",
    "segment_orchestration.py",
    "respondent_dialogue.py",
)

REFERENCE_UNAVAILABLE = "parity suite not run because the reference checkout is unavailable"

# Attribute roots whose use marks a function as (potentially) non-deterministic.
RANDOM_ROOTS: frozenset[str] = frozenset({"random", "np.random", "numpy.random", "secrets", "uuid"})
RANDOM_NAMES: frozenset[str] = frozenset(
    {"seed", "shuffle", "choice", "rand", "randn", "randint", "normal", "uniform"}
)


@dataclass
class FunctionFacts:
    """Everything the AST can say about one function."""

    qualname: str
    lineno: int
    end_lineno: int
    parameters: list[str]
    numeric_defaults: dict[str, str]
    returns: str
    docstring: str
    calls: list[str]
    uses_randomness: bool
    random_calls: list[str]
    reads_globals: list[str]
    writes_globals: list[str]
    numeric_literals: list[str]

    @property
    def loc(self) -> int:
        return self.end_lineno - self.lineno + 1


@dataclass
class ModuleFacts:
    """Inventory of one legacy module."""

    path: str
    sha256: str
    loc: int
    imports: list[str]
    constants: dict[str, str]
    mutable_globals: list[str]
    functions: list[FunctionFacts] = field(default_factory=list)


def reference_root(explicit: str | None = None) -> Path | None:
    """Resolve the reference checkout, or None when it is unavailable."""
    configured = explicit or os.environ.get("AIA_LEGACY_REFERENCE")
    candidates = (
        [Path(configured)]
        if configured
        else [Path(__file__).resolve().parents[2] / "npc-panel-reference"]
    )
    for candidate in candidates:
        if (candidate / "project_pipeline.py").is_file():
            return candidate
    return None


def _unparse(node: ast.AST | None) -> str:
    return "" if node is None else ast.unparse(node)


def _call_name(node: ast.Call) -> str:
    return _unparse(node.func)


def _is_numeric_literal(node: ast.AST) -> bool:
    if isinstance(node, ast.Constant):
        return isinstance(node.value, int | float) and not isinstance(node.value, bool)
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub | ast.UAdd):
        return _is_numeric_literal(node.operand)
    return False


def _literalish(node: ast.AST) -> bool:
    """True for a literal or a literal container, i.e. a candidate hidden default."""
    try:
        ast.literal_eval(node)
    except (ValueError, TypeError, SyntaxError, MemoryError, RecursionError):
        return False
    return True


def _function_facts(
    node: ast.FunctionDef | ast.AsyncFunctionDef, qualname: str, module_globals: set[str]
) -> FunctionFacts:
    params: list[str] = []
    numeric_defaults: dict[str, str] = {}
    args = node.args
    positional = [*args.posonlyargs, *args.args]
    defaults: list[ast.AST | None] = [None] * (len(positional) - len(args.defaults)) + list(
        args.defaults
    )
    for arg, default in zip(positional, defaults, strict=True):
        text = arg.arg + (f": {_unparse(arg.annotation)}" if arg.annotation else "")
        if default is not None:
            text += f" = {_unparse(default)}"
            if _is_numeric_literal(default):
                numeric_defaults[arg.arg] = _unparse(default)
        params.append(text)
    if args.vararg:
        params.append("*" + args.vararg.arg)
    for arg, kw_default in zip(args.kwonlyargs, args.kw_defaults, strict=True):
        text = arg.arg + (f": {_unparse(arg.annotation)}" if arg.annotation else "")
        if kw_default is not None:
            text += f" = {_unparse(kw_default)}"
            if _is_numeric_literal(kw_default):
                numeric_defaults[arg.arg] = _unparse(kw_default)
        params.append(text)
    if args.kwarg:
        params.append("**" + args.kwarg.arg)

    calls: list[str] = []
    random_calls: list[str] = []
    reads: set[str] = set()
    writes: set[str] = set()
    literals: list[str] = []
    local_names: set[str] = {a.arg for a in [*positional, *args.kwonlyargs]}

    for child in ast.walk(node):
        if isinstance(child, ast.Global):
            writes.update(child.names)
        elif isinstance(child, ast.Call):
            name = _call_name(child)
            calls.append(name)
            root = name.rsplit(".", 1)[0] if "." in name else name
            leaf = name.rsplit(".", 1)[-1]
            if root in RANDOM_ROOTS or leaf in RANDOM_NAMES:
                random_calls.append(name)
        elif isinstance(child, ast.Name):
            if isinstance(child.ctx, ast.Store):
                local_names.add(child.id)
            elif child.id in module_globals and child.id not in local_names:
                reads.add(child.id)
        elif _is_numeric_literal(child) and not isinstance(child, ast.UnaryOp):
            value = child.value if isinstance(child, ast.Constant) else None
            if value not in (0, 1, -1, 2):
                literals.append(_unparse(child))

    return FunctionFacts(
        qualname=qualname,
        lineno=node.lineno,
        end_lineno=node.end_lineno or node.lineno,
        parameters=params,
        numeric_defaults=numeric_defaults,
        returns=_unparse(node.returns),
        docstring=(ast.get_docstring(node) or "").strip().splitlines()[0]
        if ast.get_docstring(node)
        else "",
        calls=sorted(set(calls)),
        uses_randomness=bool(random_calls),
        random_calls=sorted(set(random_calls)),
        reads_globals=sorted(reads),
        writes_globals=sorted(writes),
        numeric_literals=sorted(set(literals), key=lambda s: (len(s), s)),
    )


def inventory_module(path: Path) -> ModuleFacts:
    """Build the inventory of one Python file without importing it."""
    source = path.read_bytes()
    tree = ast.parse(source, filename=str(path))
    lines = source.count(b"\n") + (0 if source.endswith(b"\n") else 1)

    imports: list[str] = []
    constants: dict[str, str] = {}
    mutable_globals: list[str] = []
    module_globals: set[str] = set()

    for node in tree.body:
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.append(f"{node.module or ''}:{','.join(a.name for a in node.names)}")
        elif isinstance(node, ast.Assign | ast.AnnAssign):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            value = node.value
            for target in targets:
                if not isinstance(target, ast.Name):
                    continue
                module_globals.add(target.id)
                if value is None:
                    continue
                if isinstance(value, ast.List | ast.Dict | ast.Set) or (
                    isinstance(value, ast.Call)
                    and _call_name(value) in {"list", "dict", "set", "defaultdict", "OrderedDict"}
                ):
                    mutable_globals.append(target.id)
                if _literalish(value):
                    constants[target.id] = _unparse(value)
        elif isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            module_globals.add(node.name)

    functions: list[FunctionFacts] = []
    for node in tree.body:
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            functions.append(_function_facts(node, node.name, module_globals))
        elif isinstance(node, ast.ClassDef):
            for item in node.body:
                if isinstance(item, ast.FunctionDef | ast.AsyncFunctionDef):
                    functions.append(
                        _function_facts(item, f"{node.name}.{item.name}", module_globals)
                    )

    return ModuleFacts(
        path=path.name,
        sha256=hashlib.sha256(source).hexdigest(),
        loc=lines,
        imports=sorted(set(imports)),
        constants=constants,
        mutable_globals=sorted(set(mutable_globals)),
        functions=functions,
    )


def render_markdown(modules: list[ModuleFacts]) -> str:
    """Render the inventory as the audit table plus per-module facts."""
    out: list[str] = []
    out.append("# Legacy Sociomapping inventory (generated)\n")
    out.append(
        "Generated by `tools/sociomap_inventory.py` from the reference source. Columns marked"
    )
    out.append(
        "_fill in_ are for the engineer reading the code; the tool does not classify methodology.\n"
    )
    out.append(
        "| Legacy function/module | Responsibility | Inputs | Outputs | "
        "Deterministic / semantic / presentation | Production destination | Parity requirement | "
        "Randomness | Globals read/written | Numeric defaults | LOC |"
    )
    out.append("| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |")
    for module in modules:
        for fn in module.functions:
            inputs = ", ".join(fn.parameters) or "—"
            outputs = fn.returns or "_fill in_"
            randomness = ", ".join(fn.random_calls) if fn.uses_randomness else "none detected"
            globals_ = (
                ", ".join(sorted({*fn.reads_globals, *(f"{g} (w)" for g in fn.writes_globals)}))
                or "—"
            )
            defaults = ", ".join(f"{k}={v}" for k, v in fn.numeric_defaults.items()) or "—"
            doc = fn.docstring.replace("|", "\\|") if fn.docstring else "_fill in_"
            cells = (
                f"`{module.path}:{fn.qualname}` (L{fn.lineno})",
                doc,
                f"`{inputs}`",
                f"`{outputs}`",
                "_fill in_",
                "_fill in_",
                "_fill in_",
                randomness,
                globals_,
                defaults,
                str(fn.loc),
            )
            out.append("| " + " | ".join(cells) + " |")
    for module in modules:
        out.append(f"\n## `{module.path}`\n")
        out.append(f"- SHA256: `{module.sha256}`")
        out.append(f"- LOC: {module.loc}; functions/methods: {len(module.functions)}")
        out.append(f"- Imports: {', '.join(f'`{i}`' for i in module.imports) or 'none'}")
        if module.constants:
            out.append("- Module constants (candidate hidden methodology defaults):")
            out.extend(f"  - `{name} = {value}`" for name, value in module.constants.items())
        if module.mutable_globals:
            out.append(
                f"- Mutable module globals: {', '.join(f'`{g}`' for g in module.mutable_globals)}"
            )
        random_fns = ", ".join(f"`{fn.qualname}`" for fn in module.functions if fn.uses_randomness)
        out.append(f"- Functions touching randomness: {random_fns or 'none detected'}")
        literal_fns = [
            (fn.qualname, fn.numeric_literals) for fn in module.functions if fn.numeric_literals
        ]
        if literal_fns:
            out.append("- Inline numeric literals (candidate thresholds / tolerances):")
            out.extend(f"  - `{name}`: {', '.join(lits)}" for name, lits in literal_fns)
    return "\n".join(out) + "\n"


def render_json(modules: list[ModuleFacts]) -> str:
    return json.dumps([asdict(m) for m in modules], indent=2, ensure_ascii=False)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--reference", help="path to the npc-panel-reference checkout")
    parser.add_argument(
        "--module", action="append", help="module file relative to the reference (repeatable)"
    )
    parser.add_argument("--format", choices=("md", "json"), default="md")
    parser.add_argument("--output", help="write to this file instead of stdout")
    args = parser.parse_args(argv)

    root = reference_root(args.reference)
    if root is None:
        print(REFERENCE_UNAVAILABLE, file=sys.stderr)
        print("set AIA_LEGACY_REFERENCE to the npc-panel-reference checkout", file=sys.stderr)
        return 2

    modules: list[ModuleFacts] = []
    for name in args.module or DEFAULT_MODULES:
        path = root / name
        if not path.is_file():
            print(f"missing in reference: {name}", file=sys.stderr)
            return 2
        modules.append(inventory_module(path))

    text = render_json(modules) if args.format == "json" else render_markdown(modules)
    if args.output:
        Path(args.output).write_text(text, encoding="utf-8")
        print(f"wrote {args.output}")
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
