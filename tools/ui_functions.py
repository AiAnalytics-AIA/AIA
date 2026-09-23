#!/usr/bin/env python3
"""Extract the JavaScript functions of the vendored ``ui_app.html``, and index the research ones.

The reference's UI ledger (``AIA-reference/ui-capability-ledger.md``) classifies
the 737 functions of ``ui_app.html``; 88 of them carry methodology or compute
numbers, and those are research logic that moves server-side, ported from the
JavaScript rather than reinvented. This tool is the first step of that port:

* ``extract_functions`` finds every ``function name(...) {`` declaration in the
  file's ``<script>`` blocks and brace-matches its body -- the same algorithm the
  reference used to build its ledger, so the count must agree (a test asserts
  737) and the body of a function is exactly what the browser runs.
* ``function_index`` records, per function, its parameters, size and the SHA256
  of its source. A fixture captured from a function records that hash, so a
  regenerated unit that changes the function makes the fixture *known* stale.
* ``check`` compares the committed UI function ledger
  (``docs/migration/legacy-ui-functions.json``) with the extraction: every row
  found, every hash current, and the count of functions unchanged.

Read-only with respect to ``legacy/``: the unit is regenerated, never edited.
Stdlib only, like the rest of ``tools/``.

    python tools/ui_functions.py list                    # every function, one per line
    python tools/ui_functions.py show normalizer66       # a function's source
    python tools/ui_functions.py index --json out.json   # the full index
    python tools/ui_functions.py check                   # the ledger against the unit
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
UNIT = REPO / "legacy" / "npc-panel-18.6.6"
UI_APP = UNIT / "app" / "ui_app.html"
DEFAULT_LEDGER = REPO / "docs" / "migration" / "legacy-ui-functions.json"

SCRIPT_BLOCK = re.compile(r"<script[^>]*>(.*?)</script>", re.S)
DECLARATION = re.compile(r"\b(?:async\s+)?function\s+([A-Za-z_$][\w$]*)\s*\(([^)]*)\)\s*\{")
# Helpers the sociomapping slices define as arrow functions on one line
# (``const clamp=(v,a,b)=>...``); a function that calls one needs it in scope.
ARROW_HELPER = re.compile(
    r"\b(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*(?:\([^)]*\)|[A-Za-z_$][\w$]*)\s*=>"
)


@dataclass(frozen=True)
class JsFunction:
    """One declared function: where it is in the joined script text, and its source."""

    name: str
    params: tuple[str, ...]
    start: int
    end: int
    body: str

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.body.encode("utf-8")).hexdigest()

    @property
    def chars(self) -> int:
        return len(self.body)


def extract_scripts(html: str) -> str:
    """The file's JavaScript: every ``<script>`` block joined, as the reference joined them."""
    return "".join(SCRIPT_BLOCK.findall(html))


def _match_brace(js: str, open_at: int) -> int:
    """Index just past the ``}`` that closes the ``{`` at ``open_at``.

    Brace matching over raw text, exactly as the reference's ledger builder did
    it -- a brace inside a string or a template literal counts. The file is
    minified hand-written JavaScript, and the reference verified this against an
    independent declaration scan (737 == 737); the same check lives in
    ``check_agreement`` here.
    """
    depth, i, n = 0, open_at, len(js)
    while i < n:
        c = js[i]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return i + 1
        i += 1
    raise ValueError(f"unbalanced braces from offset {open_at}")


def extract_functions(js: str) -> dict[str, JsFunction]:
    """Every ``function name(...) {`` declaration, brace-matched. Later declarations win.

    The file declares a few names twice across its generations (``S``,
    ``esc``); the browser keeps the last declaration, and so does this index.
    """
    out: dict[str, JsFunction] = {}
    for m in DECLARATION.finditer(js):
        open_at = js.index("{", m.end() - 1)
        end = _match_brace(js, open_at)
        params = tuple(p.strip() for p in m.group(2).split(",") if p.strip())
        out[m.group(1)] = JsFunction(m.group(1), params, m.start(), end, js[m.start() : end])
    return out


def declaration_count(js: str) -> int:
    """The independent count the reference used to verify its extraction."""
    return len(re.findall(r"\bfunction\s+[A-Za-z_$][\w$]*\s*\(", js))


def check_agreement(js: str) -> tuple[int, int]:
    """``(declarations found, declarations scanned)`` -- equal when extraction is complete."""
    return len(list(DECLARATION.finditer(js))), declaration_count(js)


def arrow_helpers(js: str) -> dict[str, str]:
    """One-line arrow helpers by name, with their full statement text.

    Used by the Node runner to give a function the helpers it calls (``clamp``,
    ``safeNum``) without evaluating the rest of the file, which needs a DOM. A
    block body (``v=>{...}``) is brace-matched; an expression body runs to the
    first ``;`` outside any bracket. Later declarations win, as in the browser.
    """
    out: dict[str, str] = {}
    for m in ARROW_HELPER.finditer(js):
        i = m.end()
        while i < len(js) and js[i] in " \t":
            i += 1
        block = i < len(js) and js[i] == "{"
        end = _match_brace(js, i) if block else _expression_end(js, i)
        if end < 0:
            continue
        if end < len(js) and js[end] == ";":
            end += 1
        out[m.group(1)] = js[m.start() : end]
    return out


def _expression_end(js: str, start: int) -> int:
    """Index of the ``;`` that ends the expression at ``start``, outside any bracket."""
    depth, i, n = 0, start, len(js)
    while i < n:
        c = js[i]
        if c in "([{":
            depth += 1
        elif c in ")]}":
            depth -= 1
            if depth < 0:
                return i
        elif c == ";" and depth == 0:
            return i
        i += 1
    return -1


def calls_of(fn: JsFunction, names: Mapping[str, Any]) -> set[str]:
    """Names among ``names`` that ``fn``'s body calls (excluding itself)."""
    return {
        other
        for other in re.findall(r"\b([A-Za-z_$][\w$]*)\s*\(", fn.body)
        if other in names and other != fn.name
    }


def load_ui_app(path: Path = UI_APP) -> str:
    return path.read_text(encoding="utf-8")


def function_index(functions: Mapping[str, JsFunction]) -> dict[str, dict[str, Any]]:
    """The serialisable index: name -> params, chars, sha256."""
    return {
        name: {"params": list(fn.params), "chars": fn.chars, "sha256": fn.sha256}
        for name, fn in sorted(functions.items())
    }


def ui_app_sha256(path: Path = UI_APP) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


# --------------------------------------------------------------------------- #
# The ledger check
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class LedgerProblem:
    function: str
    problem: str


def check_ledger(
    ledger: Mapping[str, Any], functions: Mapping[str, JsFunction]
) -> list[LedgerProblem]:
    """Every ledger row names a function that exists and hashes as recorded."""
    problems: list[LedgerProblem] = []
    for row in ledger["functions"]:
        name = str(row["name"])
        fn = functions.get(name)
        if fn is None:
            problems.append(LedgerProblem(name, "not declared in ui_app.html"))
            continue
        if fn.sha256 != row["source_sha256"]:
            problems.append(
                LedgerProblem(name, f"source changed: {fn.sha256} != {row['source_sha256']}")
            )
        if list(fn.params) != list(row["params"]):
            problems.append(LedgerProblem(name, f"parameters changed: {list(fn.params)}"))
    return problems


def load_ledger(path: Path = DEFAULT_LEDGER) -> dict[str, Any]:
    data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return data


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    parser.add_argument("--ui-app", type=Path, default=UI_APP)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("list", help="every declared function: name, parameter count, chars")
    show = sub.add_parser("show", help="print a function's source")
    show.add_argument("name")
    index = sub.add_parser("index", help="the full index as JSON")
    index.add_argument("--json", type=Path, help="write here instead of stdout")
    check = sub.add_parser("check", help="the committed UI function ledger against the unit")
    check.add_argument("--ledger", type=Path, default=DEFAULT_LEDGER)
    args = parser.parse_args(argv)

    js = extract_scripts(load_ui_app(args.ui_app))
    functions = extract_functions(js)
    found, scanned = check_agreement(js)

    if args.command == "list":
        for name, fn in sorted(functions.items()):
            print(f"{name}\t{len(fn.params)}\t{fn.chars}")
        print(
            f"# {len(functions)} functions ({found} declarations, {scanned} scanned)",
            file=sys.stderr,
        )
        return 0
    if args.command == "show":
        wanted = functions.get(args.name)
        if wanted is None:
            print(f"no function named {args.name!r}", file=sys.stderr)
            return 1
        print(wanted.body)
        return 0
    if args.command == "index":
        document = {
            "ui_app_sha256": ui_app_sha256(args.ui_app),
            "declarations_found": found,
            "declarations_scanned": scanned,
            "functions": function_index(functions),
        }
        text = json.dumps(document, ensure_ascii=False, indent=1) + "\n"
        if args.json:
            args.json.write_text(text, "utf-8")
            print(f"wrote {len(functions)} functions to {args.json}")
        else:
            print(text, end="")
        return 0
    ledger = load_ledger(args.ledger)
    problems = check_ledger(ledger, functions)
    if found != scanned:
        problems.append(
            LedgerProblem("*", f"extraction disagrees: {found} found, {scanned} scanned")
        )
    if ledger["extraction"]["functions"] != len(functions):
        problems.append(
            LedgerProblem(
                "*",
                f"function count changed: {len(functions)} != {ledger['extraction']['functions']}",
            )
        )
    for p in problems:
        print(f"FAIL  {p.function}: {p.problem}")
    if problems:
        return 1
    print(
        f"ok    {len(ledger['functions'])} ledger rows current against {len(functions)} functions"
    )
    return 0


def as_dict(fn: JsFunction) -> dict[str, Any]:
    return asdict(fn)


if __name__ == "__main__":
    sys.exit(main())
