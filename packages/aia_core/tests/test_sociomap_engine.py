"""``compute_sociomap`` end to end, the view layer (F9) and the scenario layer.

The golden fixture ``fixtures/sociomap/aia/AIA1_*`` pins the engine's own output
on F4's ratings; regenerate it only with ``tools/sociomap_golden.py`` and an
``ENGINE_IMPLEMENTATION_VERSION`` bump.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import pytest

from aia_core.domain.sociomap import (
    AIA_SOCIOMAP_V1,
    ENGINE_IMPLEMENTATION_VERSION,
    ArtifactIntegrityError,
    LayoutSpec,
    MetricsSpec,
    RatingsMatrix,
    RelationEdit,
    RelationMatrix,
    RelationSpec,
    ScenarioLayer,
    SociomapArtifact,
    SociomapInputError,
    SociomapInputs,
    SociomapSpec,
    UnsupportedMethodology,
    ViewOverrideMismatch,
    ViewOverrides,
    apply_scenario,
    apply_view_overrides,
    compute_sociomap,
    view_terrain,
)

GOLDEN = (
    Path(__file__).resolve().parent
    / "fixtures/sociomap/aia/AIA1_rowcond_unfolding_on_f4_ratings.json"
)
RATINGS_ONLY = AIA_SOCIOMAP_V1.model_copy(
    update={
        "relation": None,
        "metrics": MetricsSpec(
            object_height_metric="mean_rating", object_colour_metric="mean_rating"
        ),
    }
)
OBJECTS = ("A", "B", "C", "D")
# F6's relation matrix: directed, off-diagonal already on the 1-10 scale.
F6_RELATION = ((0, 4, 9, 2), (6, 0, 3, 8), (7, 5, 0, 1), (3, 9, 2, 0))
RATINGS = (
    (9, 3, 5, 1),
    (2, 8, 4, 7),
    (6, 6, 9, 2),
    (1, 2, 3, 10),
    (7, None, 2, 5),
    (4, 9, 8, 3),
    (10, 1, 6, 4),
    (3, 5, 10, 6),
)


def f4_ratings(sociomap_fixture: Any) -> RatingsMatrix:
    f4 = sociomap_fixture("F4")
    columns = f4["input"]["columns"]
    rows = [list(r) for r in zip(*(f4["input"]["ratings"][c] for c in columns), strict=True)]
    return RatingsMatrix(
        respondent_ids=tuple(f"r{i:02d}" for i in range(len(rows))),
        object_ids=tuple(columns),
        values=rows,
    )


def ratings(rows: Any = RATINGS, ids: tuple[str, ...] | None = None) -> RatingsMatrix:
    return RatingsMatrix(
        respondent_ids=ids or tuple(f"p{i}" for i in range(len(rows))),
        object_ids=OBJECTS,
        values=rows,
    )


def with_relation(rows: Any = RATINGS, relation: Any = F6_RELATION) -> SociomapInputs:
    return SociomapInputs(
        ratings=ratings(rows),
        object_relation=RelationMatrix(entity_ids=OBJECTS, values=relation),
    )


@pytest.fixture(scope="module")
def artifact() -> SociomapArtifact:
    return compute_sociomap(with_relation(), AIA_SOCIOMAP_V1)


def spec_with(**changes: Any) -> SociomapSpec:
    return AIA_SOCIOMAP_V1.model_copy(update=changes)


def layout_with(**changes: Any) -> LayoutSpec:
    return AIA_SOCIOMAP_V1.layout.model_copy(update=changes)


# ----------------------------------------------------------------- golden --


def test_golden_fixture_is_this_engine_version() -> None:
    golden = json.loads(GOLDEN.read_text(encoding="utf-8"))
    assert golden["engine_implementation_version"] == ENGINE_IMPLEMENTATION_VERSION
    assert golden["spec"] == RATINGS_ONLY.model_dump(mode="json")


def test_golden_layout_and_terrain_are_reproduced(sociomap_fixture: Any) -> None:
    golden = json.loads(GOLDEN.read_text(encoding="utf-8"))
    expected, tol = golden["expected_output"], golden["tolerance"]
    got = compute_sociomap(
        SociomapInputs(ratings=f4_ratings(sociomap_fixture), object_relation=None), RATINGS_ONLY
    )
    assert got.layout.algorithm == expected["layout_algorithm"]
    assert list(got.layout.respondent_ids) == expected["respondent_ids"]
    assert got.excluded_respondents == expected["excluded_respondents"]
    assert got.layout.iterations == expected["iterations"]
    assert got.layout.converged is expected["converged"]
    for name in ("stress_1", "normalized_stress", "layout_to_map_scale"):
        assert getattr(got.layout, name) == pytest.approx(expected[name], abs=tol)
    for field in ("respondent_xy", "object_xy"):
        for a, e in zip(getattr(got.layout, field), expected[field], strict=True):
            assert a == pytest.approx(tuple(e), abs=tol)
    for metric, values in expected["object_metrics"].items():
        assert list(got.object_metrics[metric].values) == pytest.approx(values, abs=tol)
    for key, field in (
        ("respondent_terrain", got.respondent_terrain),
        ("object_terrain", got.object_terrain),
    ):
        want = expected[key]
        assert [field.normalizer_lo, field.normalizer_hi] == pytest.approx(want["normalizer"])
        for s in want["samples"]:
            hr = field.height_raw[s["gy"]][s["gx"]]
            assert (hr is None) is (s["hr"] is None)
            if hr is not None:
                assert hr == pytest.approx(s["hr"], abs=tol)
            assert field.height_normalised[s["gy"]][s["gx"]] == pytest.approx(s["ht"], abs=tol)
    assert expected["object_terrain"]["finite_cells"] == got.object_terrain.finite_cells
    assert list(got.warnings) == expected["warnings"]


def test_identical_inputs_give_an_identical_artifact() -> None:
    a = compute_sociomap(with_relation(), AIA_SOCIOMAP_V1)
    b = compute_sociomap(with_relation(), AIA_SOCIOMAP_V1)
    assert a == b and a.fingerprint() == b.fingerprint()


# ------------------------------------------------------ fail-closed spec --


@pytest.mark.parametrize(
    ("spec", "field"),
    [
        (spec_with(layout=layout_with(algorithm="python_weighted_unfolding")), "layout.algorithm"),
        (spec_with(layout=layout_with(algorithm="r_smacof_unfolding")), "layout.algorithm"),
        (spec_with(layout=layout_with(algorithm="auto")), "layout.algorithm"),
        (spec_with(layout=layout_with(seed=20260814)), "layout.seed"),
        (spec_with(layout=layout_with(parameters={"dimensions": 2})), "layout.parameters"),
        (
            spec_with(ratings=AIA_SOCIOMAP_V1.ratings.model_copy(update={"ipsatize": True})),
            "ratings.ipsatize",
        ),
        (
            spec_with(
                metrics=MetricsSpec(
                    object_height_metric="popularity", object_colour_metric="support_n"
                )
            ),
            "metrics.object_height_metric",
        ),
        (
            spec_with(
                terrain=AIA_SOCIOMAP_V1.terrain.model_copy(update={"normalization": "zscore"})
            ),
            "terrain.normalization",
        ),
        (
            RATINGS_ONLY.model_copy(
                update={
                    "metrics": MetricsSpec(
                        object_height_metric="relation_classic_tscore",
                        object_colour_metric="mean_rating",
                    )
                }
            ),
            "metrics.object_height_metric",
        ),
        (
            spec_with(
                metrics=MetricsSpec(
                    object_height_metric="support_n", object_colour_metric="support_n"
                ),
                terrain=AIA_SOCIOMAP_V1.terrain.model_copy(update={"normalization": "absolute"}),
            ),
            "terrain.normalization",
        ),
        (
            spec_with(
                relation=RelationSpec(
                    scale_coercion="reference_coerce_1_10",
                    position_projection="max",
                    missing_data_policy="refuse",
                )
            ),
            "relation.position_projection",
        ),
    ],
)
def test_unsupported_methodology_fails_closed(spec: SociomapSpec, field: str) -> None:
    with pytest.raises(UnsupportedMethodology) as caught:
        compute_sociomap(with_relation(), spec)
    assert field in caught.value.unsupported


def test_absolute_normalisation_runs_where_bounds_were_recovered() -> None:
    spec = RATINGS_ONLY.model_copy(
        update={"terrain": RATINGS_ONLY.terrain.model_copy(update={"normalization": "absolute"})}
    )
    art = compute_sociomap(SociomapInputs(ratings=ratings(), object_relation=None), spec)
    assert (art.object_terrain.normalizer_lo, art.object_terrain.normalizer_hi) == (1.0, 10.0)


def test_absolute_normalisation_uses_a_declared_non_default_scale() -> None:
    spec = RATINGS_ONLY.model_copy(
        update={
            "ratings": RATINGS_ONLY.ratings.model_copy(
                update={"rating_scale_min": 0.0, "rating_scale_max": 5.0}
            ),
            "terrain": RATINGS_ONLY.terrain.model_copy(update={"normalization": "absolute"}),
        }
    )
    rows = [[min(5, v) if v is not None else None for v in r] for r in RATINGS]
    rows[0] = [5, 5, 5, 0]  # a perfect mean on A must normalise towards 1, not 4/9
    art = compute_sociomap(SociomapInputs(ratings=ratings(rows), object_relation=None), spec)
    assert (art.object_terrain.normalizer_lo, art.object_terrain.normalizer_hi) == (0.0, 5.0)


# --------------------------------------------------------- input refusals --


def test_a_rating_off_the_declared_scale_is_refused() -> None:
    rows = [list(r) for r in RATINGS]
    rows[0][0] = 11
    with pytest.raises(SociomapInputError, match="outside the declared scale"):
        compute_sociomap(with_relation(rows), AIA_SOCIOMAP_V1)


def test_a_missing_relation_cell_is_refused_by_default() -> None:
    relation = [list(r) for r in F6_RELATION]
    relation[0][1] = None
    with pytest.raises(SociomapInputError, match="policy is 'refuse'"):
        compute_sociomap(with_relation(relation=relation), AIA_SOCIOMAP_V1)


def test_the_reference_sentinel_is_used_only_when_declared_and_is_recorded() -> None:
    relation = [list(r) for r in F6_RELATION]
    relation[0][1] = None
    spec = spec_with(
        relation=AIA_SOCIOMAP_V1.relation.model_copy(  # type: ignore[union-attr]
            update={"missing_data_policy": "reference_midpoint_sentinel"}
        )
    )
    art = compute_sociomap(with_relation(relation=relation), spec)
    assert art.relation is not None
    assert art.relation.coerced.cell("A", "B") == 5.5
    assert art.relation.substituted_cells == (("A", "B"),)
    assert any("5.5 midpoint sentinel" in w for w in art.warnings)


def test_a_relation_the_spec_does_not_use_is_refused_not_ignored() -> None:
    with pytest.raises(SociomapInputError, match="silently ignored"):
        compute_sociomap(with_relation(), RATINGS_ONLY)


def test_a_relation_the_spec_needs_must_be_supplied() -> None:
    with pytest.raises(SociomapInputError, match="none was supplied"):
        compute_sociomap(SociomapInputs(ratings=ratings(), object_relation=None), AIA_SOCIOMAP_V1)


def test_relation_objects_must_match_the_ratings_order() -> None:
    with pytest.raises(ValueError, match="same order"):
        SociomapInputs(
            ratings=ratings(),
            object_relation=RelationMatrix(entity_ids=("B", "A", "C", "D"), values=F6_RELATION),
        )


# ------------------------------------------------------------ exclusions --


def test_unplaceable_respondents_are_excluded_with_a_reason_and_still_counted() -> None:
    rows = [*RATINGS, (10, 10, 10, 10), (None, 4, None, None)]
    art = compute_sociomap(with_relation(rows), AIA_SOCIOMAP_V1)
    assert set(art.excluded_respondents) == {"p8", "p9"}
    assert "top of the scale" in art.excluded_respondents["p8"]
    assert "at least 2" in art.excluded_respondents["p9"]
    assert "p8" not in art.layout.respondent_ids
    assert art.respondent_terrain.source_ids == art.layout.respondent_ids
    # Their ratings are real: support counts them.
    assert art.object_metrics["support_n"].values == (9.0, 9.0, 9.0, 9.0)  # not (8, 7, 8, 8)
    assert any("excluded" in w for w in art.warnings)


def test_every_respondent_is_placed_or_excluded(artifact: SociomapArtifact) -> None:
    body = artifact.model_dump()
    body["excluded_respondents"] = {}
    body["layout"]["respondent_ids"] = body["layout"]["respondent_ids"][1:]
    body["layout"]["respondent_xy"] = body["layout"]["respondent_xy"][1:]
    with pytest.raises(ValueError, match="either placed or excluded"):
        SociomapArtifact.model_validate(body)


# ----------------------------------------------------------- the artifact --


def test_relation_metrics_through_the_pipeline_match_f6(
    artifact: SociomapArtifact, sociomap_fixture: Any
) -> None:
    expected = sociomap_fixture("F6")["expected_output"]
    assert artifact.relation is not None and artifact.relation.coercion_branch == "clip_1_10"
    assert list(artifact.object_metrics["relation_classic"].values) == pytest.approx(
        expected["relation_classic"], abs=1e-9
    )
    assert list(artifact.object_metrics["relation_classic_tscore"].values) == pytest.approx(
        expected["tscore_default"], abs=1e-9
    )


def test_direction_is_kept_in_the_matrix_and_collapsed_only_for_position(
    artifact: SociomapArtifact,
) -> None:
    assert artifact.relation is not None
    assert artifact.relation.coerced.cell("A", "B") == 4.0
    assert artifact.relation.coerced.cell("B", "A") == 6.0
    assert artifact.relation.position_input.is_symmetric()
    assert artifact.relation.position_input.cell("A", "B") == pytest.approx((5 - 1) / 9)


def test_the_two_terrains_carry_different_quantities(artifact: SociomapArtifact) -> None:
    assert artifact.respondent_terrain.mode == "respondent_density"
    assert artifact.respondent_terrain.metric_id == "density"
    assert artifact.respondent_terrain.parameters.sigma == 9.5
    assert artifact.object_terrain.mode == "object_metric"
    assert artifact.object_terrain.metric_id == "relation_classic_tscore"
    assert artifact.object_terrain.parameters.sigma == 12.0
    assert artifact.respondent_terrain.finite_cells == 43 * 43


def test_coordinates_fit_the_declared_map_frame(artifact: SociomapArtifact) -> None:
    reach = max(
        abs(c) for p in (*artifact.layout.respondent_xy, *artifact.layout.object_xy) for c in p
    )
    assert reach == pytest.approx(AIA_SOCIOMAP_V1.layout.map_frame.extent)


def test_changing_the_height_metric_moves_no_point() -> None:
    a = compute_sociomap(with_relation(), AIA_SOCIOMAP_V1)
    b = compute_sociomap(
        with_relation(),
        spec_with(
            metrics=MetricsSpec(
                object_height_metric="support_n", object_colour_metric="mean_rating"
            )
        ),
    )
    assert a.layout == b.layout
    assert a.object_terrain != b.object_terrain
    assert a.fingerprint() != b.fingerprint()


def test_provenance_records_inputs_algorithm_and_version(artifact: SociomapArtifact) -> None:
    p = artifact.provenance
    assert set(p.input_fingerprints) == {"ratings", "object_relation"}
    assert p.input_fingerprints["ratings"] == ratings().fingerprint()
    assert p.layout_algorithm == "aia_rowcond_unfolding_v1" and p.seed is None
    assert p.implementation_version == ENGINE_IMPLEMENTATION_VERSION


def test_artifact_round_trips_and_refuses_tampering(artifact: SociomapArtifact) -> None:
    payload = json.loads(json.dumps(artifact.to_payload()))
    assert SociomapArtifact.from_payload(payload) == artifact
    tampered = json.loads(json.dumps(payload))
    tampered["artifact"]["layout"]["object_xy"][0][0] += 1e-6
    with pytest.raises(ArtifactIntegrityError):
        SociomapArtifact.from_payload(tampered)
    for key in ("artifact", "artifact_fingerprint", "spec_fingerprint"):
        partial = {k: v for k, v in payload.items() if k != key}
        with pytest.raises(ArtifactIntegrityError):
            SociomapArtifact.from_payload(partial)


def test_artifact_is_immutable(artifact: SociomapArtifact) -> None:
    with pytest.raises(ValueError):
        artifact.warnings = ("edited",)  # type: ignore[misc]


def test_artifact_forbids_presentation_fields(artifact: SociomapArtifact) -> None:
    body = artifact.model_dump()
    body["palette"] = "viridis"
    with pytest.raises(ValueError):
        SociomapArtifact.model_validate(body)


# ------------------------------------------------------------- view (F9) --


def test_f9_manual_drag_is_a_view_override(
    artifact: SociomapArtifact, sociomap_fixture: Any
) -> None:
    f9 = sociomap_fixture("F9")
    target = f9["input"]["manual_override"]
    before_fp = artifact.fingerprint()
    base = artifact.respondent_position("p0")
    empty = ViewOverrides(artifact_fingerprint=before_fp)
    before = apply_view_overrides(artifact, empty)
    after = apply_view_overrides(artifact, empty.moving_respondent("p0", target["x"], target["y"]))

    # position_changed
    assert after.respondent_xy[0] == (target["x"], target["y"]) != before.respondent_xy[0]
    # base_point_unchanged / relation_matrix_unchanged: the artifact is untouched
    assert artifact.respondent_position("p0") == base
    assert artifact.fingerprint() == before_fp
    # cache_key_changed: anything drawn from the view is invalidated
    assert after.view_key() != before.view_key()
    assert after.moved_respondents == ("p0",) and before.moved_respondents == ()
    expected = f9["expected_output"]
    assert expected["position_changed"] and expected["base_point_unchanged"]
    assert expected["relation_matrix_unchanged"] and expected["cache_key_changed"]


def test_view_terrain_follows_the_drag_and_the_artifact_terrain_does_not(
    artifact: SociomapArtifact,
) -> None:
    overrides = ViewOverrides(artifact_fingerprint=artifact.fingerprint()).moving_respondent(
        "p0", 60.0, 60.0
    )
    displayed = apply_view_overrides(artifact, overrides)
    dragged = view_terrain(artifact, displayed, mode="respondent_density")
    undragged = view_terrain(
        artifact,
        apply_view_overrides(artifact, ViewOverrides(artifact_fingerprint=artifact.fingerprint())),
        mode="respondent_density",
    )
    assert undragged == artifact.respondent_terrain
    assert dragged != artifact.respondent_terrain


def test_view_terrain_scopes_to_a_subset_and_redraws_another_metric(
    artifact: SociomapArtifact,
) -> None:
    displayed = apply_view_overrides(
        artifact, ViewOverrides(artifact_fingerprint=artifact.fingerprint())
    )
    subset = view_terrain(
        artifact, displayed, mode="respondent_density", respondent_subset=("p0", "p1")
    )
    assert subset.source_ids == ("p0", "p1")
    other = view_terrain(artifact, displayed, mode="object_metric", height_metric="mean_rating")
    assert other.metric_id == "mean_rating"
    with pytest.raises(ViewOverrideMismatch):
        view_terrain(artifact, displayed, mode="respondent_density", respondent_subset=("zed",))
    empty = view_terrain(artifact, displayed, mode="respondent_density", respondent_subset=())
    assert empty.source_ids == ()
    assert all(v == 0.0 for row in empty.height_normalised for v in row)
    with pytest.raises(ValueError, match="unknown terrain mode"):
        view_terrain(artifact, displayed, mode="storm")


def test_stale_or_foreign_overrides_are_refused(artifact: SociomapArtifact) -> None:
    with pytest.raises(ViewOverrideMismatch, match="different artifact"):
        apply_view_overrides(artifact, ViewOverrides(artifact_fingerprint="0" * 64))
    fp = artifact.fingerprint()
    for bad in (
        ViewOverrides(artifact_fingerprint=fp).moving_respondent("nobody", 0, 0),
        ViewOverrides(artifact_fingerprint=fp).moving_object("Z", 0, 0),
    ):
        with pytest.raises(ViewOverrideMismatch, match="not placed"):
            apply_view_overrides(artifact, bad)


def test_overrides_are_immutable_values_and_reset(artifact: SociomapArtifact) -> None:
    empty = ViewOverrides(artifact_fingerprint=artifact.fingerprint())
    moved = empty.moving_object("A", 1.0, 2.0)
    assert empty.objects == {} and moved.reset("A").objects == {}
    with pytest.raises(ValueError):
        empty.moving_respondent("p0", math.nan, 0.0)
    with pytest.raises(ValueError, match="boolean"):
        empty.moving_respondent("p0", True, 0.0)


# -------------------------------------------------------------- scenario --


def test_scenario_recomputes_relation_metrics_and_leaves_the_base(
    artifact: SociomapArtifact,
) -> None:
    before = artifact.fingerprint()
    layer = ScenarioLayer(
        base_artifact_fingerprint=before,
        edits=(RelationEdit(source="A", target="B", value=10.0),),
        label="A trusts B fully",
    )
    result = apply_scenario(artifact, layer)
    assert artifact.fingerprint() == before
    assert result.base_artifact_fingerprint == before
    assert result.effective_relation.cell("A", "B") == 10.0
    assert result.effective_relation.cell("A", "A") == 0.0
    # relation_classic[A] = 31 in the base (F6); +6 on A->B adds 6 to A and to B.
    assert result.object_metrics["relation_classic"].values[:2] == (37.0, 41.0)
    assert result.object_metrics["mean_rating"] == artifact.object_metrics["mean_rating"]
    assert result.object_terrain != artifact.object_terrain
    assert len(result.fingerprint()) == 64


def test_scenario_is_bound_and_well_formed(artifact: SociomapArtifact) -> None:
    fp = artifact.fingerprint()
    edit = RelationEdit(source="A", target="B", value=2.0)
    with pytest.raises(ViewOverrideMismatch):
        apply_scenario(artifact, ScenarioLayer(base_artifact_fingerprint="0" * 64, edits=(edit,)))
    with pytest.raises(ViewOverrideMismatch, match="unknown object"):
        apply_scenario(
            artifact,
            ScenarioLayer(
                base_artifact_fingerprint=fp, edits=(RelationEdit(source="A", target="Z", value=2),)
            ),
        )
    with pytest.raises(ValueError, match="no edits"):
        ScenarioLayer(base_artifact_fingerprint=fp, edits=())
    with pytest.raises(ValueError, match="once"):
        ScenarioLayer(base_artifact_fingerprint=fp, edits=(edit, edit))
    with pytest.raises(ValueError, match="diagonal"):
        RelationEdit(source="A", target="A", value=5)
    with pytest.raises(ValueError, match="1-10"):
        RelationEdit(source="A", target="B", value=0.5)
    with pytest.raises(ValueError, match="boolean"):
        RelationEdit(source="A", target="B", value=True)


def test_scenario_needs_a_relation_matrix() -> None:
    art = compute_sociomap(SociomapInputs(ratings=ratings(), object_relation=None), RATINGS_ONLY)
    layer = ScenarioLayer(
        base_artifact_fingerprint=art.fingerprint(),
        edits=(RelationEdit(source="A", target="B", value=2.0),),
    )
    with pytest.raises(ViewOverrideMismatch, match="no relation matrix"):
        apply_scenario(art, layer)
