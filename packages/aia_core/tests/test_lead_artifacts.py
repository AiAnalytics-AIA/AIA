"""The Lead's per-artifact contract (research-lead-workbench 14-16): one row per stage.

The rows (``domain/lead_artifacts.py`` ``ARTIFACTS``) are held to the fixture
``tests/fixtures/lead_artifacts/contract.json``, which the web's ``lib/workbench-artifacts.ts`` is
held to as well, so the two sides cannot drift apart. What is marked live must be what the Lead's
output and focus rules accept today.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from aia_core.domain.lead_artifacts import (
    ARTIFACTS,
    FIELDS,
    LIVE_TARGETS,
    LIVE_VIEW_OPS,
    REPORT_SECTIONS,
    ArtifactContract,
    ReportSection,
    SectionState,
    TargetKind,
    ViewOpKind,
    allows_view,
    contract_for,
)
from aia_core.domain.research_lead import (
    FOCUS_ID,
    FOCUS_KINDS,
    ID_PATTERN,
    STAGES,
    FocusItem,
    LeadOutput,
)

FIXTURE = json.loads(
    (Path(__file__).parent / "fixtures/lead_artifacts/contract.json").read_text(encoding="utf-8")
)


def test_the_rows_are_the_fixture_s() -> None:
    assert FIXTURE["fields"] == list(FIELDS)
    assert [c.fixture_row() for c in ARTIFACTS.values()] == FIXTURE["artifacts"]
    assert tuple(ARTIFACTS) == STAGES


def test_the_vocabularies_are_the_fixture_s() -> None:
    assert [v["op"] for v in FIXTURE["view_ops"]] == [v.value for v in ViewOpKind]
    assert {v["op"] for v in FIXTURE["view_ops"] if v["live"]} == {v.value for v in LIVE_VIEW_OPS}
    assert [t["kind"] for t in FIXTURE["targets"]] == [t.value for t in TargetKind]
    assert {t["kind"] for t in FIXTURE["targets"] if t["live"]} == {t.value for t in LIVE_TARGETS}
    assert [s["id"] for s in FIXTURE["report_sections"]] == [s.value for s in ReportSection]
    assert {s["id"]: s["state"] for s in FIXTURE["report_sections"]} == {
        k.value: v.value for k, v in REPORT_SECTIONS.items()
    }


def test_live_view_ops_are_what_the_lead_s_output_carries() -> None:
    ops = LeadOutput.model_json_schema()["$defs"]
    carried = {
        d["properties"]["op"]["const"]
        for d in ops.values()
        if "op" in d.get("properties", {}) and "const" in d["properties"]["op"]
    }
    assert {v.value for v in LIVE_VIEW_OPS} <= carried


@pytest.mark.parametrize("kind", sorted(TargetKind))
def test_live_targets_are_what_focus_accepts(kind: TargetKind) -> None:
    assert bool(FOCUS_ID.match(f"{kind.value}:x1")) == (kind in LIVE_TARGETS)


def test_the_server_focuses_exactly_the_registry_s_kinds() -> None:
    assert set(FOCUS_KINDS) == {k.value for k in TargetKind}
    for target in ("finding:executive:2", "pair:set1/fio~air", "audience:filter:kraj"):
        assert FOCUS_ID.fullmatch(target)
    for target in ("nonsense:x", "question:", "question:a b", "question:" + "x" * 81):
        assert not FOCUS_ID.fullmatch(target)


def test_one_id_grammar_holds_on_both_sides_and_every_example_passes_the_server() -> None:
    """The grammar is the fixture's; the server's FOCUS_ID and the Lead's own focus (FocusItem)
    take it, so an id the web builds is one the server accepts (the PM's review of #563)."""
    assert FIXTURE["id_pattern"] == ID_PATTERN
    examples = (
        "brief:goal", "objective:obj_1", "plan:narrative", "rq:rq_1", "question:q3",
        "audience:filter:kraj", "audience:subpanel:young_18_29", "dimension:eko",
        "own_dimension:REQ-1", "sample:quota:muz.18-29", "sample:ready:sample_size",
        "step:analysis/executive", "measure:napoje/caj", "object:napoje/caj",
        "pair:napoje/caj~kava", "module:executive", "finding:executive:2",
        "claim:executive:c1", "report:ch-native-map-1",
    )  # fmt: skip
    for target in examples:
        assert FOCUS_ID.fullmatch(target), target
        assert FocusItem(op="focus", target=target).target == target


def test_each_target_kind_belongs_to_the_stage_the_fixture_names() -> None:
    owner = {t["kind"]: t["stage"] for t in FIXTURE["targets"]}
    for stage, row in ARTIFACTS.items():
        assert all(owner[t.value] == stage for t in row.targets), stage
    assert sorted(owner) == sorted(t.value for r in ARTIFACTS.values() for t in r.targets)


def test_the_chain_is_connected() -> None:
    order = {s: i for i, s in enumerate(STAGES)}
    for stage, row in ARTIFACTS.items():
        # An artifact is made from earlier stages and hands on to later ones.
        assert all(order[i] < order[stage] for i in row.inputs), stage
        assert all(h.to is None or order[h.to] > order[stage] for h in row.hands_off), stage
    # Every section of the report is fed by some artifact but the methodology, which is fixed
    # text today; only the report hands on to nothing.
    fed = {s for r in ARTIFACTS.values() for s in r.report_sections}
    assert set(ReportSection) - fed == {ReportSection.METHODOLOGY}
    assert REPORT_SECTIONS[ReportSection.METHODOLOGY] is SectionState.FIXED_TEXT
    assert [s for s, r in ARTIFACTS.items() if any(h.to is None for h in r.hands_off)] == ["report"]


def test_frozen_artifacts_take_no_edits() -> None:
    row = {**contract_for("results").fixture_row(), "edits": True}
    with pytest.raises(ValidationError, match="working copy"):
        ArtifactContract.model_validate(row)


def test_an_unknown_start_is_refused_by_name() -> None:
    row = {**contract_for("brief").fixture_row(), "starts": ["agent_job:write_everything"]}
    with pytest.raises(ValidationError, match="write_everything"):
        ArtifactContract.model_validate(row)


def test_allows_view() -> None:
    assert allows_view("sociomap", "filter")
    assert not allows_view("questionnaire", "filter")
    assert allows_view("brief", "focus")
    assert not allows_view("nowhere", "focus")
    with pytest.raises(KeyError):
        contract_for("nowhere")
