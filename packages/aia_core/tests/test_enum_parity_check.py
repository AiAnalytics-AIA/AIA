"""The web client's vocabulary must stay in parity with the domain enums.

`tools/enum_parity_check.py` is the Python half of the binding described in
`.planning/plans/design-system.md` (chunk 2); the TypeScript half is the
`satisfies Record<Enum, …>` maps in `apps/web/src/design/status.ts`.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
TOOL_PATH = REPO_ROOT / "tools" / "enum_parity_check.py"


@pytest.fixture(scope="module")
def tool() -> ModuleType:
    """Import the tool by path -- `tools/` is a script directory, not a package."""
    spec = importlib.util.spec_from_file_location("enum_parity_check", TOOL_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _inputs(
    tool: ModuleType,
) -> tuple[
    dict[str, list[str]],
    dict[str, list[str]],
    dict[str, list[str]],
    dict[str, list[tuple[str, str]]],
    dict[str, list[tuple[str, str]]],
]:
    from aia_core.domain import pipeline

    stages_py = {
        "RESEARCH_STAGES": list(pipeline.RESEARCH_STAGES),
        "SIMULATION_STAGES": list(pipeline.SIMULATION_STAGES),
    }
    return (
        tool.domain_enums(),
        tool.ts_arrays(tool.ENUMS_TS),
        tool.ts_arrays(tool.LIFECYCLE_TS),
        stages_py,
        tool.ts_stage_lists(tool.LIFECYCLE_TS),
    )


def test_the_committed_web_vocabulary_is_in_parity(tool: ModuleType) -> None:
    assert tool.compare(*_inputs(tool)) == []


def test_a_value_added_to_the_domain_only_fails(tool: ModuleType) -> None:
    domain, ts, lifecycle, sp, st = _inputs(tool)
    domain["StageStatus"] = [*domain["StageStatus"], "PAUSED_BY_ADMIN"]
    problems = tool.compare(domain, ts, lifecycle, sp, st)
    assert any(
        "StageStatus" in p and "PAUSED_BY_ADMIN" in p and "not in STAGE_STATUS" in p
        for p in problems
    )


def test_a_value_invented_in_the_web_client_fails(tool: ModuleType) -> None:
    domain, ts, lifecycle, sp, st = _inputs(tool)
    ts["WORKFLOW_RUN_STATUS"] = [*ts["WORKFLOW_RUN_STATUS"], "ALMOST_DONE"]
    problems = tool.compare(domain, ts, lifecycle, sp, st)
    assert any("ALMOST_DONE" in p and "not in the domain" in p for p in problems)


def test_a_new_domain_enum_forces_a_decision(tool: ModuleType) -> None:
    domain, ts, lifecycle, sp, st = _inputs(tool)
    domain["EvidenceRole"] = ["MEASURED_JOINT"]
    problems = tool.compare(domain, ts, lifecycle, sp, st)
    assert any(
        p.startswith("EvidenceRole: new domain enum is neither bound nor listed in UNBOUND")
        for p in problems
    )


def test_a_stage_label_change_in_the_domain_fails(tool: ModuleType) -> None:
    domain, ts, lifecycle, sp, st = _inputs(tool)
    sp["RESEARCH_STAGES"] = [("BRIEF", "Brief"), *sp["RESEARCH_STAGES"][1:]]
    problems = tool.compare(domain, ts, lifecycle, sp, st)
    assert any(p.startswith("RESEARCH_STAGES:") for p in problems)


def test_reordering_is_reported(tool: ModuleType) -> None:
    domain, ts, lifecycle, sp, st = _inputs(tool)
    ts["STUDY_STATUS"] = list(reversed(ts["STUDY_STATUS"]))
    problems = tool.compare(domain, ts, lifecycle, sp, st)
    assert any("different order in STUDY_STATUS" in p for p in problems)


def _keys() -> dict[str, list[str]]:
    from aia_core.domain import pipeline

    return {"IMPACT_ROOTS": list(pipeline.IMPACT_ROOTS)}


def test_the_committed_impact_fields_are_in_parity(tool: ModuleType) -> None:
    assert tool.compare(*_inputs(tool), _keys()) == []


def test_an_impact_field_added_to_the_domain_only_fails(tool: ModuleType) -> None:
    keys = _keys()
    keys["IMPACT_ROOTS"] = [*keys["IMPACT_ROOTS"], "new_field"]
    problems = tool.compare(*_inputs(tool), keys)
    assert any("IMPACT_ROOTS" in p and "IMPACT_FIELDS" in p for p in problems)


def test_a_missing_impact_field_list_fails(tool: ModuleType) -> None:
    domain, ts, lifecycle, sp, st = _inputs(tool)
    lifecycle = {k: v for k, v in lifecycle.items() if k != "IMPACT_FIELDS"}
    problems = tool.compare(domain, ts, lifecycle, sp, st, _keys())
    assert any("no `export const IMPACT_FIELDS" in p for p in problems)
