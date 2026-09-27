#!/usr/bin/env python3
"""Capture fixtures from the vendored ``ui_app.html`` functions by executing them under Node.

The function-level half of the parity harness (``.planning/plans/legacy-strangler.md``).
A *case file* under ``packages/aia_core/tests/fixtures/legacy_ui/cases/`` names one
function, the helpers it needs from the same file, the parity type and the
inputs; this tool extracts those sources verbatim with ``tools/ui_functions.py``,
runs every case through ``tools/ui_function_runner.mjs`` (a ``vm`` sandbox with no
DOM), and writes one fixture in the shape of the reference's golden fixtures:
``input``, ``expected_output``, ``parity_type``, ``tolerance``, plus the SHA256 of
the function source and of every helper it was captured from. ``index.json``
pins each fixture file's SHA256 and its source hash, so a regenerated unit that
changes a function makes its fixture *known* stale rather than quietly wrong.

Floats are rounded to ten decimals, as the reference's fixture builder rounds
them, and compared at the fixture's tolerance (``AGENTS.md`` § pytest).

    python tools/ui_function_capture.py capture            # every case file -> fixtures + index
    python tools/ui_function_capture.py capture --only U01_normalizer66
    python tools/ui_function_capture.py verify             # re-run and compare, write nothing

Exit status: 1 when Node is missing, a case fails to execute, or ``verify`` finds
a difference; else 0. Stdlib only.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import re
import shutil
import subprocess
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
TOOLS = REPO / "tools"
RUNNER = TOOLS / "ui_function_runner.mjs"
FIXTURES = REPO / "packages" / "aia_core" / "tests" / "fixtures" / "legacy_ui"
CASES = FIXTURES / "cases"
INDEX = FIXTURES / "index.json"
UNIT = REPO / "legacy" / "npc-panel-18.6.6"

FIXTURE_SCHEMA = "aia-legacy-ui-fixture-1"
DECIMALS = 10
FIXTURE_ID = re.compile(r"^U\d{2}_[A-Za-z0-9_]+$")


def _load_ui_functions() -> Any:
    spec = importlib.util.spec_from_file_location("ui_functions", TOOLS / "ui_functions.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["ui_functions"] = module
    spec.loader.exec_module(module)
    return module


def round_floats(value: Any) -> Any:
    """Round every float to ten decimals, recursively; integers and everything else pass."""
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            return str(value)
        rounded = round(value, DECIMALS)
        return int(rounded) if rounded == int(rounded) and abs(rounded) < 1e15 else rounded
    if isinstance(value, list):
        return [round_floats(v) for v in value]
    if isinstance(value, dict):
        return {k: round_floats(v) for k, v in value.items()}
    return value


def unit_archive_sha256() -> str:
    extraction = json.loads((UNIT / "EXTRACTION.json").read_text(encoding="utf-8"))
    sha: str = extraction["source"]["sha256"]
    return sha


def load_case_file(path: Path) -> dict[str, Any]:
    document: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    for key in ("fixture_id", "function", "capability_id", "parity_type", "helpers", "cases"):
        if key not in document:
            raise ValueError(f"{path}: missing {key!r}")
    if not FIXTURE_ID.match(document["fixture_id"]):
        raise ValueError(f"{path}: fixture_id must match U<nn>_<name>")
    if document["parity_type"] not in {"EXACT", "NUMERICAL"}:
        raise ValueError(f"{path}: a function fixture is EXACT or NUMERICAL")
    if document["parity_type"] == "NUMERICAL" and not document.get("tolerance"):
        raise ValueError(f"{path}: NUMERICAL needs a tolerance")
    ids = [c["id"] for c in document["cases"]]
    if len(ids) != len(set(ids)) or not ids:
        raise ValueError(f"{path}: case ids must be unique and non-empty")
    return document


def resolve_sources(
    ui: Any, functions: Mapping[str, Any], arrows: Mapping[str, str], case: Mapping[str, Any]
) -> tuple[list[str], dict[str, str]]:
    """The exact sources a case file asks for, arrow helpers first, plus their hashes.

    ``helpers`` entries are names; ``arrow:name`` forces the one-line arrow form
    where the file declares both (``S`` is declared three times across the
    file's generations; the sociomapping slice under test uses the arrow one).
    """
    sources: list[str] = []
    hashes: dict[str, str] = {}
    for entry in case["helpers"]:
        forced_arrow = str(entry).startswith("arrow:")
        name = str(entry).split(":", 1)[-1]
        if forced_arrow or (name in arrows and name not in functions):
            if name not in arrows:
                raise KeyError(f"{case['fixture_id']}: no arrow helper named {name!r}")
            text = arrows[name]
        else:
            if name not in functions:
                raise KeyError(f"{case['fixture_id']}: no function named {name!r}")
            text = functions[name].body
        sources.append(text)
        hashes[str(entry)] = hashlib.sha256(text.encode("utf-8")).hexdigest()
    fn = functions.get(case["function"])
    if fn is None:
        raise KeyError(f"{case['fixture_id']}: no function named {case['function']!r}")
    sources.append(fn.body)
    return sources, hashes


def run_node(sources: Sequence[str], cases: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    node = shutil.which("node")
    if node is None:
        raise RuntimeError("node is not installed; the capture needs Node.js")
    request = json.dumps({"sources": list(sources), "cases": list(cases)}, ensure_ascii=False)
    completed = subprocess.run(
        [node, str(RUNNER)], input=request, capture_output=True, text=True, check=False
    )
    if completed.returncode != 0:
        raise RuntimeError(f"runner failed: {completed.stderr.strip()}")
    result: dict[str, Any] = json.loads(completed.stdout)
    return result


def capture_one(
    ui: Any, functions: Mapping[str, Any], arrows: Mapping[str, str], case: Mapping[str, Any]
) -> dict[str, Any]:
    """Run every case of one case file and build its fixture document."""
    sources, helper_hashes = resolve_sources(ui, functions, arrows, case)
    fn = functions[case["function"]]
    runner_cases = [
        {
            "id": c["id"],
            "call": case["function"],
            "args": c.get("args", []),
            "globals": c.get("globals", {}),
            "probe": c.get("probe"),
            "extra": c.get("extra", {}),
        }
        for c in case["cases"]
    ]
    outcome = run_node(sources, runner_cases)
    failures = [r for r in outcome["results"] if not r["ok"]]
    if failures:
        detail = "; ".join(f"{r['id']}: {r['error']}" for r in failures)
        raise RuntimeError(f"{case['fixture_id']}: {detail}")
    expected = {r["id"]: round_floats(r["value"]) for r in outcome["results"]}
    inputs = {
        c["id"]: {k: round_floats(c[k]) for k in ("args", "globals", "extra", "probe") if k in c}
        for c in case["cases"]
    }
    return {
        "schema": FIXTURE_SCHEMA,
        "fixture_id": case["fixture_id"],
        "capability_id": case["capability_id"],
        "reference_zip_sha256": unit_archive_sha256(),
        "reference_function": f"ui_app.html::{case['function']}",
        "source_sha256": fn.sha256,
        "helpers": helper_hashes,
        "ui_app_sha256": ui.ui_app_sha256(),
        "runtime_environment": {
            "node": outcome["node"],
            "note": "Frontend function executed in a Node vm sandbox (no DOM) from source "
            "extracted verbatim from the vendored legacy/npc-panel-18.6.6/app/ui_app.html",
        },
        "parity_type": case["parity_type"],
        "tolerance": case.get("tolerance"),
        "input": inputs,
        "expected_output": expected,
        "notes": case.get("notes", ""),
    }


def fixture_path(fixture_id: str) -> Path:
    return FIXTURES / f"{fixture_id}.json"


def write_fixture(document: Mapping[str, Any]) -> Path:
    path = fixture_path(str(document["fixture_id"]))
    path.write_text(json.dumps(document, ensure_ascii=False, indent=1) + "\n", "utf-8")
    return path


def rebuild_index(ui: Any) -> dict[str, Any]:
    """The index over every fixture file present: file hash, source hash, parity, capability."""
    entries: dict[str, Any] = {}
    for path in sorted(FIXTURES.glob("U*.json")):
        document = json.loads(path.read_text(encoding="utf-8"))
        entries[document["fixture_id"]] = {
            "file": path.name,
            "function": document["reference_function"].split("::", 1)[1],
            "source_sha256": document["source_sha256"],
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "parity_type": document["parity_type"],
            "tolerance": document["tolerance"],
            "capability": document["capability_id"],
        }
    index = {
        "description": "Fixtures captured from the vendored ui_app.html functions by "
        "tools/ui_function_capture.py. Each entry pins the fixture file and the SHA256 of "
        "the function source it was captured from. Never edited by hand: re-run the capture.",
        "unit": {
            "path": "legacy/npc-panel-18.6.6/app/ui_app.html",
            "ui_app_sha256": ui.ui_app_sha256(),
            "archive_sha256": unit_archive_sha256(),
        },
        "fixtures": entries,
    }
    INDEX.write_text(json.dumps(index, ensure_ascii=False, indent=1) + "\n", "utf-8")
    return index


def _differences(expected: Any, actual: Any, tolerance: float | None, path: str = "") -> list[str]:
    if isinstance(expected, dict) and isinstance(actual, dict):
        out: list[str] = []
        if set(expected) != set(actual):
            out.append(f"{path}: keys {sorted(expected)} != {sorted(actual)}")
        for key in sorted(set(expected) & set(actual)):
            out.extend(_differences(expected[key], actual[key], tolerance, f"{path}.{key}"))
        return out
    if isinstance(expected, list) and isinstance(actual, list):
        if len(expected) != len(actual):
            return [f"{path}: length {len(expected)} != {len(actual)}"]
        out = []
        for i, (e, a) in enumerate(zip(expected, actual, strict=True)):
            out.extend(_differences(e, a, tolerance, f"{path}[{i}]"))
        return out
    numbers = (int, float)
    if (
        isinstance(expected, numbers)
        and isinstance(actual, numbers)
        and not isinstance(expected, bool)
        and not isinstance(actual, bool)
    ):
        if tolerance is not None and abs(float(expected) - float(actual)) <= tolerance:
            return []
        if tolerance is None and expected == actual:
            return []
        return [f"{path}: {expected!r} != {actual!r}"]
    return [] if expected == actual else [f"{path}: {expected!r} != {actual!r}"]


def verify_one(
    ui: Any, functions: Mapping[str, Any], arrows: Mapping[str, str], case: Mapping[str, Any]
) -> list[str]:
    """Re-run a case file and compare with its committed fixture at the fixture's tolerance."""
    path = fixture_path(str(case["fixture_id"]))
    if not path.is_file():
        return [f"{case['fixture_id']}: no fixture captured yet"]
    committed = json.loads(path.read_text(encoding="utf-8"))
    fresh = capture_one(ui, functions, arrows, case)
    problems = []
    if committed["source_sha256"] != fresh["source_sha256"]:
        problems.append(f"{case['fixture_id']}: function source changed in the unit")
    problems.extend(
        _differences(committed["expected_output"], fresh["expected_output"], committed["tolerance"])
    )
    return problems


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    parser.add_argument("command", choices=["capture", "verify"])
    parser.add_argument("--only", nargs="*", help="fixture ids to process (default: all)")
    args = parser.parse_args(argv)

    ui = _load_ui_functions()
    js = ui.extract_scripts(ui.load_ui_app())
    functions = ui.extract_functions(js)
    arrows = ui.arrow_helpers(js)
    case_files = sorted(CASES.glob("*.json"))
    cases = [load_case_file(p) for p in case_files]
    if args.only:
        cases = [c for c in cases if c["fixture_id"] in set(args.only)]
        if not cases:
            print("no case file matches --only", file=sys.stderr)
            return 1

    try:
        if args.command == "capture":
            for case in cases:
                path = write_fixture(capture_one(ui, functions, arrows, case))
                print(f"captured {path.relative_to(REPO)}")
            index = rebuild_index(ui)
            print(f"indexed {len(index['fixtures'])} fixtures in {INDEX.relative_to(REPO)}")
            return 0
        failed = 0
        for case in cases:
            problems = verify_one(ui, functions, arrows, case)
            if problems:
                failed += 1
                print(f"DIFF  {case['fixture_id']}")
                for p in problems:
                    print(f"      {p}")
            else:
                print(f"ok    {case['fixture_id']}")
        return 1 if failed else 0
    except (RuntimeError, KeyError) as exc:
        print(f"capture failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
