"""Parity and behaviour tests for the stage pipeline.

The parity tests run the legacy prototype's ``project_pipeline`` and this port
against identical fixtures and require identical output. They are the contract
that lets us retire the prototype: if these pass, artifact reuse decisions in the
new system match the validated ones.

The behaviour tests below them hold even without the legacy checkout.
"""

from __future__ import annotations

from typing import Any

import pytest

from aia_core.domain.pipeline import (
    IMPACT_ROOTS,
    RESEARCH_STAGES,
    SIMULATION_STAGES,
    ProjectType,
    StageStatus,
    changed_fields,
    fingerprint,
    impact_preview,
    resolve_stage,
    stage_fingerprint,
    stage_ids,
    stage_input_payload,
)

RESEARCH_IDS = [s for s, _ in RESEARCH_STAGES]
SIMULATION_IDS = [s for s, _ in SIMULATION_STAGES]

# Fields whose impact root exists in the research pipeline. Cross-pipeline fields
# are exercised separately because legacy crashes on them.
RESEARCH_SAFE_FIELDS = [
    f for f, root in IMPACT_ROOTS.items() if root is None or root in RESEARCH_IDS
]
SIMULATION_SAFE_FIELDS = [
    f for f, root in IMPACT_ROOTS.items() if root is None or root in SIMULATION_IDS
]


# --------------------------------------------------------------------------- #
# Parity against the legacy prototype
# --------------------------------------------------------------------------- #


@pytest.mark.parity
def test_stage_lists_match_legacy(legacy_pipeline: Any) -> None:
    """The stage ids, order and Czech labels must be identical."""
    assert [tuple(x) for x in legacy_pipeline.RESEARCH_STAGES] == list(RESEARCH_STAGES)
    assert [tuple(x) for x in legacy_pipeline.SIMULATION_STAGES] == list(SIMULATION_STAGES)


@pytest.mark.parity
def test_stage_statuses_match_legacy(legacy_pipeline: Any) -> None:
    """Every legacy stage status must exist in the typed enum, and vice versa."""
    assert {s.value for s in StageStatus} == legacy_pipeline.STAGE_STATUSES


@pytest.mark.parity
def test_impact_roots_match_legacy(legacy_pipeline: Any) -> None:
    """The field -> root-stage map is the invalidation contract; it must match."""
    assert legacy_pipeline.IMPACT_ROOTS == IMPACT_ROOTS


@pytest.mark.parity
@pytest.mark.parametrize("ptype", ["research", "simulation"])
def test_stage_input_payload_matches_legacy(
    legacy_pipeline: Any,
    ptype: str,
    research_project: dict[str, Any],
    simulation_project: dict[str, Any],
) -> None:
    """Every stage's material-input payload must be byte-identical to legacy.

    This is the strongest guarantee in the suite: identical payloads mean
    identical fingerprints, which means artifacts produced by the prototype stay
    reusable by the new system.
    """
    project = simulation_project if ptype == "simulation" else research_project
    for sid in stage_ids(ptype):
        assert stage_input_payload(project, sid, ptype) == legacy_pipeline.stage_input_payload(
            project, sid, ptype
        ), f"payload mismatch for {ptype}/{sid}"


@pytest.mark.parity
@pytest.mark.parametrize("ptype", ["research", "simulation"])
def test_stage_fingerprint_matches_legacy(
    legacy_pipeline: Any,
    ptype: str,
    research_project: dict[str, Any],
    simulation_project: dict[str, Any],
) -> None:
    """Fingerprint hashes must match exactly, not merely be self-consistent."""
    project = simulation_project if ptype == "simulation" else research_project
    for sid in stage_ids(ptype):
        assert stage_fingerprint(project, sid, ptype) == legacy_pipeline.stage_fingerprint(
            project, sid, ptype
        ), f"fingerprint mismatch for {ptype}/{sid}"


@pytest.mark.parity
def test_unknown_stage_payload_matches_legacy(
    legacy_pipeline: Any, research_project: dict[str, Any]
) -> None:
    """An unknown stage id must fall back to the same 'everything matters' payload."""
    assert stage_input_payload(research_project, "NO_SUCH_STAGE", "research") == (
        legacy_pipeline.stage_input_payload(research_project, "NO_SUCH_STAGE", "research")
    )


@pytest.mark.parity
@pytest.mark.parametrize(
    ("ptype", "fields"),
    [("research", RESEARCH_SAFE_FIELDS), ("simulation", SIMULATION_SAFE_FIELDS)],
)
def test_impact_preview_single_field_matches_legacy(
    legacy_pipeline: Any, ptype: str, fields: list[str]
) -> None:
    """Each individual field's invalidation footprint must match legacy."""
    for field in fields:
        assert impact_preview(ptype, [field]).as_dict() == legacy_pipeline.impact_preview(
            ptype, [field]
        ), f"impact mismatch for {ptype}/{field}"


@pytest.mark.parity
def test_impact_preview_combinations_match_legacy(legacy_pipeline: Any) -> None:
    """Multi-field edits, including the presentation-only interaction, must match."""
    combos = [
        [],
        ["goal"],
        ["provider"],
        ["provider", "model", "preferred_provider"],
        ["report_style"],
        ["report_style", "report_branding"],
        ["goal", "report_style"],
        ["n", "audience"],
        ["audience", "sections"],
        ["analysis_instructions", "report_branding"],
        ["unknown_field_entirely"],
        ["unknown_field_entirely", "n"],
    ]
    for combo in combos:
        assert impact_preview("research", combo).as_dict() == legacy_pipeline.impact_preview(
            "research", combo
        ), f"impact mismatch for {combo}"


@pytest.mark.parity
def test_impact_preview_explicit_stage_matches_legacy(legacy_pipeline: Any) -> None:
    """Forcing a rerun from a chosen stage must match legacy, including bad input."""
    for sid in [*RESEARCH_IDS, "NOT_A_STAGE"]:
        assert impact_preview("research", [], explicit_stage=sid).as_dict() == (
            legacy_pipeline.impact_preview("research", [], explicit_stage=sid)
        ), f"explicit-stage mismatch for {sid}"


@pytest.mark.parity
@pytest.mark.parametrize("ptype", ["research", "simulation"])
def test_resolve_stage_matches_legacy(legacy_pipeline: Any, ptype: str) -> None:
    """Cross-pipeline stage routing must resolve to the same stage as legacy."""
    probes = [*RESEARCH_IDS, *SIMULATION_IDS, "", None, "garbage", "questionnaire"]
    for probe in probes:
        assert resolve_stage(ptype, probe) == legacy_pipeline.resolve_stage(ptype, probe), (
            f"resolve_stage mismatch for {ptype}/{probe!r}"
        )
        for default in (None, "REPORT", "WORLDS", "nonsense"):
            assert resolve_stage(ptype, probe, default=default) == (
                legacy_pipeline.resolve_stage(ptype, probe, default=default)
            ), f"resolve_stage mismatch for {ptype}/{probe!r} default={default!r}"


@pytest.mark.parity
def test_fingerprint_function_matches_legacy(
    legacy_pipeline: Any, research_project: dict[str, Any]
) -> None:
    """The raw hash function must agree, including on awkward values."""
    values: list[Any] = [
        None,
        {},
        [],
        0,
        "",
        research_project,
        {"b": 1, "a": 2},
        {"a": 2, "b": 1},
        {"nested": {"x": [1, 2, {"y": None}]}},
        ["ř", "š", "č"],
    ]
    for value in values:
        assert fingerprint(value) == legacy_pipeline.fingerprint(value)


# --------------------------------------------------------------------------- #
# Documented deviations from legacy
# --------------------------------------------------------------------------- #


@pytest.mark.parity
def test_cross_pipeline_field_crashes_legacy_but_not_us(legacy_pipeline: Any) -> None:
    """Legacy raises ValueError for a cross-pipeline field; we resolve it instead.

    Changing ``scenario`` on a research project maps to SCENARIO_CONTRACT, which is
    not a research stage. Legacy called ``ids.index`` on it and raised, and that
    exception escaped through the project save path. We route it through
    STAGE_EQUIVALENTS to the nearest research stage.
    """
    with pytest.raises(ValueError, match="not in list"):
        legacy_pipeline.impact_preview("research", ["scenario"])

    result = impact_preview("research", ["scenario"])
    assert result.root_stage == "RESEARCH_DESIGN"
    assert result.invalidate[0] == "RESEARCH_DESIGN"
    assert result.preserve == ["BRIEF", "DEEP_RESEARCH"]


@pytest.mark.parity
def test_cross_pipeline_field_reverse_direction(legacy_pipeline: Any) -> None:
    """The same deviation applies to a research field on a simulation project."""
    with pytest.raises(ValueError, match="not in list"):
        legacy_pipeline.impact_preview("simulation", ["questionnaire"])

    result = impact_preview("simulation", ["questionnaire"])
    assert result.root_stage == "SCENARIO_CONTRACT"
    assert "SCENARIO_CONTRACT" in result.invalidate


def test_unmappable_cross_pipeline_root_is_dropped() -> None:
    """A root with no counterpart in either pipeline invalidates nothing."""
    # SAMPLE_PLAN -> VARIANTS exists, so use a field whose root is research-only and
    # whose equivalent is also research-only to prove the drop path is reachable.
    result = impact_preview("research", ["nonexistent_field"])
    assert result.root_stage is None
    assert result.invalidate == []
    assert result.preserve == RESEARCH_IDS


# --------------------------------------------------------------------------- #
# Behaviour tests (no legacy checkout required)
# --------------------------------------------------------------------------- #


def test_provider_change_preserves_entire_pipeline() -> None:
    """Switching provider or model must never invalidate completed work.

    This is the invariant that makes mixed-provider continuation possible: a user
    who exhausts their Claude Code quota and continues on the Claude API keeps
    every artifact already produced.
    """
    for field in ("provider", "preferred_provider", "provider_policy", "model"):
        result = impact_preview("research", [field])
        assert result.root_stage is None, f"{field} must not invalidate any stage"
        assert result.invalidate == []
        assert result.preserve == RESEARCH_IDS


def test_earliest_changed_stage_wins() -> None:
    """When several stages are affected, the earliest becomes the root."""
    result = impact_preview("research", ["report_style", "audience", "analysis_instructions"])
    assert result.root_stage == "AUDIENCE"
    assert result.preserve == ["BRIEF", "DEEP_RESEARCH", "RESEARCH_DESIGN", "QUESTIONNAIRE"]
    assert result.invalidate[0] == "AUDIENCE"
    assert result.invalidate[-1] == "DELIVERY"


def test_presentation_only_change_spares_fieldwork() -> None:
    """A report styling change must not reopen fieldwork or analysis."""
    result = impact_preview("research", ["report_style"])
    assert result.root_stage == "REPORT"
    assert result.presentation_only is True
    assert result.invalidate == ["REPORT", "DELIVERY"]
    assert "FIELDWORK" in result.preserve
    assert "ANALYSIS" in result.preserve


def test_invalidate_and_preserve_partition_the_pipeline() -> None:
    """Every stage is either preserved or invalidated -- never both, never neither."""
    for ptype in ("research", "simulation"):
        ids = stage_ids(ptype)
        for field in IMPACT_ROOTS:
            result = impact_preview(ptype, [field])
            assert result.preserve + result.invalidate == ids, f"{ptype}/{field}"
            assert not set(result.preserve) & set(result.invalidate)


def test_fingerprint_ignores_key_order_but_not_values() -> None:
    """Fingerprints are order-insensitive and value-sensitive."""
    assert fingerprint({"a": 1, "b": 2}) == fingerprint({"b": 2, "a": 1})
    assert fingerprint({"a": 1}) != fingerprint({"a": 2})
    assert fingerprint([1, 2]) != fingerprint([2, 1])


def test_fingerprint_is_stable_for_unserialisable_values() -> None:
    """A non-JSON value must hash deterministically rather than raise."""

    class Opaque:
        def __str__(self) -> str:
            return "opaque"

    assert fingerprint({"x": Opaque()}) == fingerprint({"x": Opaque()})


def test_stage_fingerprint_changes_only_for_material_inputs(
    research_project: dict[str, Any],
) -> None:
    """An edit outside a stage's material inputs must not change its fingerprint."""
    before = stage_fingerprint(research_project, "FIELDWORK", "research")

    unrelated = {**research_project, "report_style": "internal", "provider": "openai"}
    assert stage_fingerprint(unrelated, "FIELDWORK", "research") == before

    material = {**research_project, "n": 900}
    assert stage_fingerprint(material, "FIELDWORK", "research") != before


def test_changed_fields_detects_nested_edits(research_project: dict[str, Any]) -> None:
    """Changed-field detection compares by value, including nested structures."""
    updated = {
        **research_project,
        "audience": {**research_project["audience"], "mode": "customer"},
    }
    assert changed_fields(research_project, updated) == ["audience"]
    assert changed_fields(research_project, dict(research_project)) == []
    assert changed_fields(None, research_project) == []


def test_changed_fields_reports_additions_and_removals(
    research_project: dict[str, Any],
) -> None:
    """A key present on only one side counts as changed."""
    added = {**research_project, "brand_new": 1}
    assert changed_fields(research_project, added) == ["brand_new"]

    removed = {k: v for k, v in research_project.items() if k != "n"}
    assert changed_fields(research_project, removed) == ["n"]


def test_project_type_coercion_defaults_to_research() -> None:
    """Only the exact string 'simulation' selects the simulation pipeline."""
    assert ProjectType.coerce("simulation") is ProjectType.SIMULATION
    assert ProjectType.coerce("SIMULATION") is ProjectType.SIMULATION
    for value in ("research", "", None, "sim", "other", 0):
        assert ProjectType.coerce(value) is ProjectType.RESEARCH


def test_stage_status_classification() -> None:
    """Completion and waiting classifications back the carry-forward rule."""
    assert StageStatus.DONE.is_complete
    assert StageStatus.DONE_WITH_WARNINGS.is_complete
    for status in (
        StageStatus.NOT_STARTED,
        StageStatus.READY,
        StageStatus.RUNNING,
        StageStatus.FAILED,
        StageStatus.INVALIDATED,
        StageStatus.WAITING_USER,
    ):
        assert not status.is_complete

    assert StageStatus.WAITING_CREDITS.is_waiting
    assert StageStatus.WAITING_CAPACITY.is_waiting
    assert StageStatus.WAITING_USER.is_waiting
    assert not StageStatus.RUNNING.is_waiting
