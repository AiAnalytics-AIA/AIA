#!/usr/bin/env python3
"""Fail when the web client's domain vocabulary drifts from the Python domain.

Two directions, both fatal:

* every value of a bound Python ``StrEnum`` must appear in its TypeScript array in
  ``apps/web/src/design/enums.ts`` (or, for the lifecycles, ``lifecycle.ts``), and
  the TypeScript array must contain nothing the domain does not;
* every ``Enum`` defined in ``aia_core.domain`` must be either bound or listed in
  ``UNBOUND`` with a reason — so a brand-new domain enum forces a decision.

The TypeScript side is read as text: an ``export const NAME = [ ... ] as const``
array of string literals. No Node toolchain is needed, so this runs in the backend
CI job next to the other repository guards.

Usage: ``python tools/enum_parity_check.py`` (exit 0 = in parity).
"""

from __future__ import annotations

import enum
import inspect
import re
import sys
from pathlib import Path
from types import ModuleType

REPO = Path(__file__).resolve().parents[1]
ENUMS_TS = REPO / "apps/web/src/design/enums.ts"
LIFECYCLE_TS = REPO / "apps/web/src/design/lifecycle.ts"

# Python enum name -> TypeScript const in enums.ts.
BOUND: dict[str, str] = {
    "StageStatus": "STAGE_STATUS",
    "ProjectStatus": "PROJECT_STATUS",
    "WorkflowRunStatus": "WORKFLOW_RUN_STATUS",
    "StepRunStatus": "STEP_RUN_STATUS",
    "AttemptStatus": "ATTEMPT_STATUS",
    "ReservationStatus": "RESERVATION_STATUS",
    "FailureClass": "FAILURE_CLASS",
    "StudyStatus": "STUDY_STATUS",
    "ClientStatus": "CLIENT_STATUS",
    "ScopeRole": "SCOPE_ROLE",
    "OrganizationRole": "ORGANIZATION_ROLE",
    "Permission": "PERMISSION",
    "SelfApprovalSource": "SELF_APPROVAL_SOURCE",
    "Provider": "PROVIDER",
    "ProviderPolicy": "PROVIDER_POLICY",
    "ModelRole": "MODEL_ROLE",
}
# Bound to lifecycle.ts rather than enums.ts.
BOUND_LIFECYCLE: dict[str, str] = {"ProjectType": "PROJECT_TYPES"}

# Domain enums the web client deliberately does not render, and why.
UNBOUND: dict[str, str] = {
    "InteractionMode": "worker-side review policy; not shown to researchers yet",
    "RecoveryAction": "internal retry/park decision; the UI renders the resulting status",
    "DataClass": "egress classification inside the residency boundary",
    "ResidencyZone": "egress routing inside the residency boundary",
}

_CONST = re.compile(r"export const (?P<name>[A-Z_]+)\s*=\s*\[(?P<body>.*?)\]\s*as const", re.S)
_STR = re.compile(r'"([^"\\]*)"')
_STAGE_ROW = re.compile(r'\[\s*"([A-Z_]+)"\s*,\s*"([^"]*)"\s*\]')


def ts_arrays(path: Path) -> dict[str, list[str]]:
    """Every ``export const NAME = [...] as const`` of plain string literals."""
    text = path.read_text(encoding="utf-8")
    return {m["name"]: _STR.findall(m["body"]) for m in _CONST.finditer(text)}


def ts_stage_lists(path: Path) -> dict[str, list[tuple[str, str]]]:
    """``RESEARCH_STAGES`` / ``SIMULATION_STAGES`` as (id, label) rows."""
    text = path.read_text(encoding="utf-8")
    out: dict[str, list[tuple[str, str]]] = {}
    for name in ("RESEARCH_STAGES", "SIMULATION_STAGES"):
        m = re.search(rf"export const {name}\s*=\s*\[(.*?)\]\s*as const", text, re.S)
        out[name] = _STAGE_ROW.findall(m.group(1)) if m else []
    return out


def domain_enums() -> dict[str, list[str]]:
    """Every Enum class defined (not merely imported) in an ``aia_core.domain`` module."""
    import importlib
    import pkgutil

    import aia_core.domain as pkg

    found: dict[str, list[str]] = {}
    for info in pkgutil.iter_modules(pkg.__path__):
        mod: ModuleType = importlib.import_module(f"{pkg.__name__}.{info.name}")
        for name, obj in vars(mod).items():
            if (
                inspect.isclass(obj)
                and issubclass(obj, enum.Enum)
                and obj.__module__ == mod.__name__
            ):
                found[name] = [str(m.value) for m in obj]  # type: ignore[attr-defined]
    return found


def compare(
    domain: dict[str, list[str]],
    ts: dict[str, list[str]],
    lifecycle_ts: dict[str, list[str]],
    stages_py: dict[str, list[tuple[str, str]]],
    stages_ts: dict[str, list[tuple[str, str]]],
) -> list[str]:
    """All parity problems, as human-readable lines. Empty means in parity."""
    problems: list[str] = []
    for name in sorted(set(domain) - set(BOUND) - set(BOUND_LIFECYCLE) - set(UNBOUND)):
        problems.append(
            f"{name}: new domain enum is neither bound nor listed in UNBOUND "
            "(tools/enum_parity_check.py)"
        )
    for name in sorted(set(UNBOUND) - set(domain)):
        problems.append(f"{name}: listed in UNBOUND but no longer exists in the domain")
    for py_name, (ts_name, source) in {
        **{k: (v, ts) for k, v in BOUND.items()},
        **{k: (v, lifecycle_ts) for k, v in BOUND_LIFECYCLE.items()},
    }.items():
        if py_name not in domain:
            problems.append(f"{py_name}: bound, but no longer defined in aia_core.domain")
            continue
        if ts_name not in source:
            problems.append(
                f"{py_name}: no `export const {ts_name} = [...] as const` in the web client"
            )
            continue
        py, web = domain[py_name], source[ts_name]
        missing = [v for v in py if v not in web]
        extra = [v for v in web if v not in py]
        if missing:
            problems.append(f"{py_name}: in the domain but not in {ts_name}: {missing}")
        if extra:
            problems.append(f"{py_name}: in {ts_name} but not in the domain: {extra}")
        if not missing and not extra and py != web:
            problems.append(
                f"{py_name}: same values, different order in {ts_name} (keep domain order)"
            )
    for name, rows in stages_py.items():
        if rows != stages_ts.get(name):
            problems.append(
                f"{name}: lifecycle.ts differs from pipeline.py: {stages_ts.get(name)} != {rows}"
            )
    return problems


def main() -> int:
    from aia_core.domain import pipeline

    stages_py = {
        "RESEARCH_STAGES": list(pipeline.RESEARCH_STAGES),
        "SIMULATION_STAGES": list(pipeline.SIMULATION_STAGES),
    }
    problems = compare(
        domain_enums(),
        ts_arrays(ENUMS_TS),
        ts_arrays(LIFECYCLE_TS),
        stages_py,
        ts_stage_lists(LIFECYCLE_TS),
    )
    if problems:
        print(
            "enum_parity_check: the web client's vocabulary has drifted from aia_core.domain",
            file=sys.stderr,
        )
        for p in problems:
            print(f"  FAIL  {p}", file=sys.stderr)
        return 1
    print(
        f"enum_parity_check: {len(BOUND) + len(BOUND_LIFECYCLE)} enums and 2 lifecycles in "
        f"parity; {len(UNBOUND)} domain enums deliberately unbound."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
