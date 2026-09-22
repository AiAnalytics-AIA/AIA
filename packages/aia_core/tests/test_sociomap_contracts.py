"""Invariant tests for the deterministic Sociomapping contracts.

No Sociomapping mathematics is tested here because none has been ported: the
legacy reference was unavailable when these contracts were written. What *is*
tested is everything the product already requires of a Sociomapa regardless of
algorithm:

* methodology is explicit, versioned and fingerprinted, with no hidden default;
* an unsupported method fails closed instead of becoming a different algorithm;
* inputs are validated (square, unique ids, finite, aligned) and missing values
  are preserved rather than imputed;
* the artifact is immutable, fingerprinted, round-trips through JSON and refuses
  a tampered payload;
* height and colour change without moving a single point;
* dragging a node and running a what-if never touch the canonical result.
"""

from __future__ import annotations

import copy
import itertools
import json
import math
from typing import Any

import pytest
from pydantic import ValidationError

from aia_core.domain.sociomap import (
    IMPLEMENTED,
    WHAT_IF_BASE_KEY,
    ArtifactIntegrityError,
    ImplementedMethods,
    LayoutResult,
    MapKind,
    MetricValues,
    Provenance,
    RelationEdit,
    RelationMatrix,
    SociomapArtifact,
    SociomapSpec,
    UnsupportedMethodology,
    ViewOverrideMismatch,
    ViewOverrides,
    WhatIfLayer,
    apply_view_overrides,
    derive_what_if_relation,
    require_supported,
    what_if_inputs,
)

# --------------------------------------------------------------------------- #
# Fixtures


def make_spec(**overrides: Any) -> SociomapSpec:
    """A fully explicit spec. Method names are placeholders, not implementations."""
    base: dict[str, Any] = {
        "methodology_version": "legacy-18.6.6-pending-port",
        "map_kind": MapKind.RESPONDENT,
        "relation_method": "pairwise_evaluation_distance",
        "matrix_transform": "identity",
        "normalization_method": "none",
        "missing_data_policy": "fail",
        "weighting_policy": "unweighted",
        "layout_algorithm": "legacy_unfolding",
        "layout_parameters": {"iterations": 500, "tolerance": 1e-6},
        "layout_seed": 42,
        "height_metric": "row_mean",
        "colour_metric": "column_mean",
    }
    base.update(overrides)
    return SociomapSpec(**base)


IDS = ("alice", "bob", "carol", "dave")
VALUES = (
    (0.0, 0.2, 0.9, 0.4),
    (0.3, 0.0, 0.5, 0.7),
    (0.9, 0.6, 0.0, 0.1),
    (0.4, 0.8, 0.1, 0.0),
)


@pytest.fixture
def matrix() -> RelationMatrix:
    return RelationMatrix(entity_ids=IDS, values=VALUES)


@pytest.fixture
def artifact(matrix: RelationMatrix) -> SociomapArtifact:
    return SociomapArtifact(
        spec=make_spec(),
        entity_ids=IDS,
        relation=matrix,
        layout=LayoutResult(
            algorithm="legacy_unfolding",
            x=(0.0, 1.0, 0.5, -0.5),
            y=(0.0, 0.0, 0.8, 0.8),
            gauge_fixed=None,
            diagnostics={"iterations": 120, "stress": 0.031},
        ),
        height=MetricValues(metric_id="row_mean", values=(0.375, 0.375, 0.4, 0.325)),
        colour=MetricValues(metric_id="column_mean", values=(0.4, 0.4, 0.375, 0.3)),
        provenance=Provenance(
            input_fingerprints={"relation": matrix.fingerprint()},
            seed=42,
            dependencies={"python": "3.12"},
        ),
        quality={"stress": 0.031},
        warnings=("fixture data, not a real map",),
    )


# --------------------------------------------------------------------------- #
# SociomapSpec: explicit, versioned, fingerprinted


def test_spec_has_no_hidden_defaults() -> None:
    """Every methodology field must be stated. Omitting one is an error, not a default."""
    for field in SociomapSpec.model_fields:
        kwargs = make_spec().model_dump()
        del kwargs[field]
        with pytest.raises(ValidationError):
            SociomapSpec(**kwargs)


@pytest.mark.parametrize(
    "field",
    [
        "methodology_version",
        "relation_method",
        "matrix_transform",
        "normalization_method",
        "missing_data_policy",
        "weighting_policy",
        "layout_algorithm",
        "height_metric",
        "colour_metric",
    ],
)
def test_spec_rejects_blank_method_names(field: str) -> None:
    with pytest.raises(ValidationError, match="blank is not a default"):
        make_spec(**{field: "   "})


def test_spec_is_frozen_and_forbids_extras() -> None:
    spec = make_spec()
    with pytest.raises(ValidationError):
        spec.layout_seed = 7  # type: ignore[misc]
    with pytest.raises(ValidationError):
        make_spec(arrow_rules={"threshold": 0.5})


def test_spec_fingerprint_is_stable_and_order_independent() -> None:
    a = make_spec(layout_parameters={"iterations": 500, "tolerance": 1e-6})
    b = make_spec(layout_parameters={"tolerance": 1e-6, "iterations": 500})
    assert a.fingerprint() == b.fingerprint()
    assert a.fingerprint() == make_spec().fingerprint()
    assert len(a.fingerprint()) == 64


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("methodology_version", "other"),
        ("map_kind", MapKind.OBJECT),
        ("relation_method", "other"),
        ("matrix_transform", "other"),
        ("normalization_method", "other"),
        ("missing_data_policy", "other"),
        ("weighting_policy", "other"),
        ("layout_algorithm", "other"),
        ("layout_parameters", {"iterations": 501, "tolerance": 1e-6}),
        ("layout_seed", 43),
        ("layout_seed", None),
        ("height_metric", "other"),
        ("colour_metric", "other"),
    ],
)
def test_every_spec_field_changes_the_fingerprint(field: str, value: Any) -> None:
    """A methodology change must never be invisible to reuse or audit."""
    assert make_spec(**{field: value}).fingerprint() != make_spec().fingerprint()


def test_spec_parameters_must_be_json_data() -> None:
    with pytest.raises(ValidationError, match="finite"):
        make_spec(layout_parameters={"tolerance": float("nan")})
    with pytest.raises(ValidationError, match="JSON data"):
        make_spec(layout_parameters={"callback": object()})


def test_spec_round_trips_through_json() -> None:
    spec = make_spec()
    restored = SociomapSpec.model_validate(json.loads(spec.model_dump_json()))
    assert restored == spec
    assert restored.fingerprint() == spec.fingerprint()


# --------------------------------------------------------------------------- #
# Fail closed: no method is implemented yet, and nothing falls back


def test_no_methodology_is_implemented_yet() -> None:
    """Documents the honest state: contracts exist, computation does not.

    When the first algorithm is ported from the reference with parity evidence,
    this test changes deliberately -- it must not be made to pass by registering
    a method ahead of its implementation.
    """
    assert ImplementedMethods() == IMPLEMENTED
    for field_name in ImplementedMethods.__dataclass_fields__:
        assert getattr(IMPLEMENTED, field_name) == frozenset()


def test_require_supported_fails_closed_and_names_every_missing_method() -> None:
    spec = make_spec()
    with pytest.raises(UnsupportedMethodology) as excinfo:
        require_supported(spec)
    missing = excinfo.value.unsupported
    assert missing == {
        "relation_method": "pairwise_evaluation_distance",
        "matrix_transform": "identity",
        "normalization_method": "none",
        "missing_data_policy": "fail",
        "weighting_policy": "unweighted",
        "layout_algorithm": "legacy_unfolding",
        "height_metric": "row_mean",
        "colour_metric": "column_mean",
    }
    assert "no fallback is permitted" in str(excinfo.value)


def test_require_supported_passes_only_when_every_dimension_is_implemented() -> None:
    spec = make_spec()
    everything = ImplementedMethods(
        relation_methods=frozenset({spec.relation_method}),
        matrix_transforms=frozenset({spec.matrix_transform}),
        normalization_methods=frozenset({spec.normalization_method}),
        missing_data_policies=frozenset({spec.missing_data_policy}),
        weighting_policies=frozenset({spec.weighting_policy}),
        layout_algorithms=frozenset({spec.layout_algorithm}),
        height_metrics=frozenset({spec.height_metric}),
        colour_metrics=frozenset({spec.colour_metric}),
    )
    require_supported(spec, everything)

    # One dimension short -> refused, and only that dimension is reported.
    almost = ImplementedMethods(
        **{
            **{f: getattr(everything, f) for f in ImplementedMethods.__dataclass_fields__},
            "layout_algorithms": frozenset({"something_else"}),
        }
    )
    with pytest.raises(UnsupportedMethodology) as excinfo:
        require_supported(spec, almost)
    assert excinfo.value.unsupported == {"layout_algorithm": "legacy_unfolding"}


# --------------------------------------------------------------------------- #
# RelationMatrix: validation


def test_matrix_requires_square_shape() -> None:
    with pytest.raises(ValidationError, match="must be square"):
        RelationMatrix(entity_ids=("a", "b"), values=((0.0, 1.0),))
    with pytest.raises(ValidationError, match="must be square"):
        RelationMatrix(entity_ids=("a", "b"), values=((0.0, 1.0, 2.0), (1.0, 0.0, 2.0)))


def test_matrix_requires_at_least_two_entities() -> None:
    with pytest.raises(ValidationError, match="at least two entities"):
        RelationMatrix(entity_ids=("solo",), values=((0.0,),))
    with pytest.raises(ValidationError, match="at least two entities"):
        RelationMatrix(entity_ids=(), values=())


def test_matrix_rejects_duplicate_and_blank_ids() -> None:
    with pytest.raises(ValidationError, match="duplicate entity id"):
        RelationMatrix(entity_ids=("a", "a"), values=((0.0, 1.0), (1.0, 0.0)))
    with pytest.raises(ValidationError, match="non-blank"):
        RelationMatrix(entity_ids=("a", " "), values=((0.0, 1.0), (1.0, 0.0)))


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf")])
def test_matrix_rejects_non_finite_values(bad: float) -> None:
    with pytest.raises(ValidationError, match="finite"):
        RelationMatrix(entity_ids=("a", "b"), values=((0.0, bad), (1.0, 0.0)))


def test_matrix_rejects_booleans_masquerading_as_numbers() -> None:
    with pytest.raises(ValidationError, match="boolean"):
        RelationMatrix(entity_ids=("a", "b"), values=((0.0, True), (1.0, 0.0)))


def test_matrix_rejects_strings() -> None:
    with pytest.raises(ValidationError):
        RelationMatrix(entity_ids=("a", "b"), values=((0.0, "high"), (1.0, 0.0)))  # type: ignore[arg-type]


def test_matrix_preserves_missing_values_without_imputing() -> None:
    m = RelationMatrix(
        entity_ids=("a", "b", "c"), values=((0.0, None, 1.0), (None, 0.0, 2.0), (1.0, 2.0, 0.0))
    )
    assert m.missing_count == 2
    assert not m.is_complete
    assert m.cell("a", "b") is None
    assert m.cell("a", "c") == 1.0


def test_matrix_accepts_integers_as_floats(matrix: RelationMatrix) -> None:
    m = RelationMatrix(entity_ids=("a", "b"), values=((0, 3), (3, 0)))
    assert m.values == ((0.0, 3.0), (3.0, 0.0))
    assert all(isinstance(v, float) for row in m.values for v in row)


def test_matrix_extreme_magnitudes_are_preserved_exactly() -> None:
    big, tiny = 1e300, 5e-324
    m = RelationMatrix(entity_ids=("a", "b"), values=((0.0, big), (tiny, 0.0)))
    assert m.cell("a", "b") == big
    assert m.cell("b", "a") == tiny
    restored = RelationMatrix.model_validate(json.loads(m.model_dump_json()))
    assert restored == m


def test_zero_and_constant_matrices_are_valid_inputs() -> None:
    """Degenerate inputs are the engine's problem to diagnose, not the contract's to hide."""
    zero = RelationMatrix(entity_ids=("a", "b", "c"), values=((0.0,) * 3,) * 3)
    const = RelationMatrix(entity_ids=("a", "b", "c"), values=((7.0,) * 3,) * 3)
    assert zero.is_symmetric() and const.is_symmetric()
    assert zero.max_asymmetry() == 0.0


def test_sparse_matrix_symmetry_needs_both_sides_present() -> None:
    m = RelationMatrix(entity_ids=("a", "b"), values=((0.0, 1.0), (None, 0.0)))
    assert not m.is_symmetric()
    assert m.max_asymmetry() is None
    both_missing = RelationMatrix(entity_ids=("a", "b"), values=((0.0, None), (None, 0.0)))
    assert both_missing.is_symmetric()


def test_matrix_symmetry_and_asymmetry_are_descriptive(matrix: RelationMatrix) -> None:
    assert not matrix.is_symmetric()
    # alice<->bob 0.2/0.3, bob<->carol 0.5/0.6, bob<->dave 0.7/0.8; the rest agree.
    assert matrix.max_asymmetry() == pytest.approx(0.1)
    assert matrix.is_symmetric(abs_tol=0.1 + 1e-9)
    assert not matrix.is_symmetric(abs_tol=0.05)
    sym = RelationMatrix(entity_ids=("a", "b"), values=((0.0, 1.0), (1.0 + 1e-12, 0.0)))
    assert not sym.is_symmetric()
    assert sym.is_symmetric(abs_tol=1e-9)


def test_matrix_diagonal_is_stored_as_supplied() -> None:
    m = RelationMatrix(entity_ids=("a", "b"), values=((5.0, 1.0), (1.0, None)))
    assert m.cell("a", "a") == 5.0
    assert m.cell("b", "b") is None


def test_matrix_unknown_entity_raises_key_error(matrix: RelationMatrix) -> None:
    with pytest.raises(KeyError):
        matrix.cell("alice", "zed")


# --------------------------------------------------------------------------- #
# RelationMatrix: permutation and derivation


def test_reordering_preserves_every_relation_by_identity(matrix: RelationMatrix) -> None:
    for order in itertools.permutations(IDS):
        re = matrix.reordered(order)
        assert re.entity_ids == order
        for s in IDS:
            for t in IDS:
                assert re.cell(s, t) == matrix.cell(s, t)


def test_reordering_changes_fingerprint_but_not_relations(matrix: RelationMatrix) -> None:
    """Entity order is part of the canonical form, so it is part of the fingerprint."""
    re = matrix.reordered(tuple(reversed(IDS)))
    assert re.fingerprint() != matrix.fingerprint()
    assert re.reordered(IDS) == matrix
    assert re.reordered(IDS).fingerprint() == matrix.fingerprint()


def test_reordering_requires_a_permutation(matrix: RelationMatrix) -> None:
    with pytest.raises(ValueError, match="permutation"):
        matrix.reordered(("alice", "bob", "carol"))
    with pytest.raises(ValueError, match="permutation"):
        matrix.reordered(("alice", "bob", "carol", "zed"))


def test_with_cells_returns_a_new_matrix_and_leaves_the_original(matrix: RelationMatrix) -> None:
    before = matrix.fingerprint()
    derived = matrix.with_cells({("alice", "bob"): 0.99, ("dave", "dave"): None})
    assert derived.cell("alice", "bob") == 0.99
    assert derived.cell("dave", "dave") is None
    assert matrix.cell("alice", "bob") == 0.2
    assert matrix.fingerprint() == before
    assert derived is not matrix


def test_matrix_is_immutable(matrix: RelationMatrix) -> None:
    with pytest.raises(ValidationError):
        matrix.entity_ids = ("x", "y", "z", "w")  # type: ignore[misc]
    with pytest.raises(TypeError):
        matrix.values[0][1] = 5.0  # type: ignore[index]


def test_matrix_fingerprint_is_reproducible(matrix: RelationMatrix) -> None:
    again = RelationMatrix(entity_ids=IDS, values=VALUES)
    assert again.fingerprint() == matrix.fingerprint()
    assert (
        RelationMatrix(entity_ids=IDS, values=(*VALUES[:3], (0.4, 0.8, 0.1, 1e-9))).fingerprint()
        != matrix.fingerprint()
    )


def test_matrix_at_realistic_scale_validates_quickly() -> None:
    """A synthetic-population map may hold hundreds of entities; validation must stay cheap."""
    n = 400
    ids = tuple(f"r{i:04d}" for i in range(n))
    values = tuple(tuple(float((i * 7 + j * 13) % 97) / 97 for j in range(n)) for i in range(n))
    m = RelationMatrix(entity_ids=ids, values=values)
    assert m.n == n
    assert m.is_complete
    assert len(m.fingerprint()) == 64


# --------------------------------------------------------------------------- #
# Metrics and layout


def test_metric_values_reject_non_finite_and_blank_ids() -> None:
    with pytest.raises(ValidationError, match="finite"):
        MetricValues(metric_id="m", values=(1.0, math.inf))
    with pytest.raises(ValidationError, match="blank"):
        MetricValues(metric_id="", values=(1.0,))
    assert MetricValues(metric_id="m", values=(1.0, None)).values == (1.0, None)


def test_layout_requires_aligned_finite_coordinates() -> None:
    with pytest.raises(ValidationError, match="x has 2 values and y has 1"):
        LayoutResult(algorithm="a", x=(0.0, 1.0), y=(0.0,))
    with pytest.raises(ValidationError, match="finite"):
        LayoutResult(algorithm="a", x=(0.0, math.nan), y=(0.0, 1.0))
    layout = LayoutResult(algorithm="a", x=(0.0, 1.0), y=(0.0, 1.0))
    assert layout.gauge_fixed is None, "unknown until the implementation declares it"


# --------------------------------------------------------------------------- #
# SociomapArtifact: alignment, immutability, fingerprint, round trip


def test_artifact_requires_matrix_in_artifact_entity_order(
    matrix: RelationMatrix, artifact: SociomapArtifact
) -> None:
    with pytest.raises(ValidationError, match="entity order"):
        artifact.model_copy(
            update={"relation": matrix.reordered(tuple(reversed(IDS)))}
        ).model_validate(
            artifact.model_copy(
                update={"relation": matrix.reordered(tuple(reversed(IDS)))}
            ).model_dump()
        )


def test_artifact_requires_layout_and_metrics_aligned_with_entities(
    artifact: SociomapArtifact,
) -> None:
    body = artifact.model_dump()
    short_layout = {**body, "layout": {**body["layout"], "x": [0.0, 1.0], "y": [0.0, 1.0]}}
    with pytest.raises(ValidationError, match="layout places 2 entities"):
        SociomapArtifact.model_validate(short_layout)
    short_height = {**body, "height": {"metric_id": "h", "values": [1.0]}}
    with pytest.raises(ValidationError, match="height metric has 1 values"):
        SociomapArtifact.model_validate(short_height)


def test_artifact_rejects_duplicate_entity_ids(matrix: RelationMatrix) -> None:
    body = {
        "spec": make_spec().model_dump(),
        "entity_ids": ["a", "a"],
        "relation": {"entity_ids": ["a", "a"], "values": [[0.0, 1.0], [1.0, 0.0]]},
        "layout": {"algorithm": "x", "x": [0.0, 1.0], "y": [0.0, 1.0]},
    }
    with pytest.raises(ValidationError, match="duplicate entity id"):
        SociomapArtifact.model_validate(body)


def test_artifact_is_immutable(artifact: SociomapArtifact) -> None:
    with pytest.raises(ValidationError):
        artifact.layout = artifact.layout  # type: ignore[misc]
    with pytest.raises(TypeError):
        artifact.layout.x[0] = 99.0  # type: ignore[index]


def test_artifact_fingerprint_is_reproducible_and_sensitive(artifact: SociomapArtifact) -> None:
    same = SociomapArtifact.model_validate(artifact.model_dump())
    assert same.fingerprint() == artifact.fingerprint()

    moved = artifact.model_copy(
        update={"layout": artifact.layout.model_copy(update={"x": (1e-12, *artifact.layout.x[1:])})}
    )
    assert moved.fingerprint() != artifact.fingerprint()

    other_seed = artifact.model_copy(
        update={"provenance": artifact.provenance.model_copy(update={"seed": 43})}
    )
    assert other_seed.fingerprint() != artifact.fingerprint()

    other_spec = artifact.model_copy(update={"spec": make_spec(layout_seed=43)})
    assert other_spec.fingerprint() != artifact.fingerprint()
    assert other_spec.spec_fingerprint != artifact.spec_fingerprint

    warned = artifact.model_copy(update={"warnings": (*artifact.warnings, "another")})
    assert warned.fingerprint() != artifact.fingerprint()


def test_artifact_round_trips_through_json_payload(artifact: SociomapArtifact) -> None:
    payload = artifact.to_payload()
    wire = json.dumps(payload, sort_keys=True)
    restored = SociomapArtifact.from_payload(json.loads(wire))
    assert restored == artifact
    assert restored.fingerprint() == artifact.fingerprint() == payload["artifact_fingerprint"]
    assert restored.spec_fingerprint == payload["spec_fingerprint"]
    assert restored.relation.cell("alice", "carol") == 0.9
    assert restored.layout.x == artifact.layout.x


def test_artifact_payload_refuses_tampering(artifact: SociomapArtifact) -> None:
    payload = artifact.to_payload()

    moved = copy.deepcopy(payload)
    moved["artifact"]["layout"]["x"][0] += 0.001
    with pytest.raises(ArtifactIntegrityError, match="does not match its recorded fingerprint"):
        SociomapArtifact.from_payload(moved)

    respecced = copy.deepcopy(payload)
    respecced["artifact"]["spec"]["layout_seed"] = 7
    respecced["artifact_fingerprint"] = SociomapArtifact.model_validate(
        respecced["artifact"]
    ).fingerprint()
    with pytest.raises(ArtifactIntegrityError, match="spec does not match"):
        SociomapArtifact.from_payload(respecced)

    with pytest.raises(ArtifactIntegrityError, match="missing"):
        SociomapArtifact.from_payload({"artifact": payload["artifact"]})


def test_artifact_provenance_records_implementation_and_inputs(artifact: SociomapArtifact) -> None:
    assert artifact.provenance.implementation == "aia_core.domain.sociomap"
    assert artifact.provenance.implementation_version == "0.0.0-contracts"
    assert artifact.provenance.input_fingerprints["relation"] == artifact.relation.fingerprint()
    assert artifact.provenance.seed == 42
    with pytest.raises(ValidationError, match="non-blank"):
        Provenance(input_fingerprints={"relation": ""})


def test_artifact_contract_forbids_presentation_fields(artifact: SociomapArtifact) -> None:
    """Pixel positions, palettes and drag state are not research truth."""
    body = artifact.model_dump()
    for extra in ("pixel_x", "palette", "dragged_positions", "png"):
        with pytest.raises(ValidationError):
            SociomapArtifact.model_validate({**body, extra: 1})


# --------------------------------------------------------------------------- #
# Height and colour are independent of position


def test_changing_height_or_colour_moves_no_point(artifact: SociomapArtifact) -> None:
    new_height = MetricValues(metric_id="betweenness", values=(1.0, 2.0, 3.0, 4.0))
    new_colour = MetricValues(metric_id="segment_share", values=(0.1, 0.2, 0.3, 0.4))

    only_height = artifact.with_metrics(height=new_height)
    only_colour = artifact.with_metrics(colour=new_colour)
    both = artifact.with_metrics(height=new_height, colour=new_colour)
    cleared = artifact.with_metrics(height=None, colour=None)

    for derived in (only_height, only_colour, both, cleared):
        assert derived.layout == artifact.layout
        assert derived.layout.x == artifact.layout.x and derived.layout.y == artifact.layout.y
        assert derived.relation == artifact.relation
        assert derived.spec == artifact.spec
        assert derived.provenance == artifact.provenance

    assert only_height.height == new_height and only_height.colour == artifact.colour
    assert only_colour.colour == new_colour and only_colour.height == artifact.height
    assert both.height == new_height and both.colour == new_colour
    assert cleared.height is None and cleared.colour is None
    assert artifact.height is not None and artifact.height.metric_id == "row_mean"


def test_metric_swap_is_visible_in_the_fingerprint(artifact: SociomapArtifact) -> None:
    swapped = artifact.with_metrics(height=MetricValues(metric_id="other", values=(0.0,) * 4))
    assert swapped.fingerprint() != artifact.fingerprint()
    assert swapped.spec_fingerprint == artifact.spec_fingerprint


# --------------------------------------------------------------------------- #
# Manual drag is view state


def test_dragging_a_node_never_mutates_the_artifact(artifact: SociomapArtifact) -> None:
    before_fp = artifact.fingerprint()
    before_layout = artifact.layout.model_copy(deep=True)

    overrides = ViewOverrides(artifact_fingerprint=before_fp).with_position("carol", 9.0, -9.0)
    displayed = apply_view_overrides(artifact, overrides)

    assert artifact.fingerprint() == before_fp
    assert artifact.layout == before_layout
    assert displayed.artifact_fingerprint == before_fp
    assert displayed.overridden == ("carol",)
    carol = artifact.entity_ids.index("carol")
    assert (displayed.x[carol], displayed.y[carol]) == (9.0, -9.0)
    for i, entity in enumerate(artifact.entity_ids):
        if entity != "carol":
            assert (displayed.x[i], displayed.y[i]) == (artifact.layout.x[i], artifact.layout.y[i])


def test_overrides_are_themselves_immutable_values(artifact: SociomapArtifact) -> None:
    base = ViewOverrides(artifact_fingerprint=artifact.fingerprint())
    moved = base.with_position("alice", 1.0, 1.0)
    reset = moved.without("alice")
    assert base.positions == {} and reset.positions == {}
    assert set(moved.positions) == {"alice"}


def test_stale_overrides_are_refused_when_canonical_results_change(
    artifact: SociomapArtifact,
) -> None:
    overrides = ViewOverrides(artifact_fingerprint=artifact.fingerprint()).with_position(
        "bob", 0.0, 0.0
    )
    recomputed = artifact.model_copy(update={"spec": make_spec(layout_seed=1)})
    with pytest.raises(ViewOverrideMismatch, match="different artifact"):
        apply_view_overrides(recomputed, overrides)


def test_overrides_for_unknown_entities_are_refused(artifact: SociomapArtifact) -> None:
    overrides = ViewOverrides(artifact_fingerprint=artifact.fingerprint()).with_position(
        "zed", 0.0, 0.0
    )
    with pytest.raises(ViewOverrideMismatch, match="not in the artifact"):
        apply_view_overrides(artifact, overrides)


def test_empty_overrides_display_the_canonical_layout(artifact: SociomapArtifact) -> None:
    displayed = apply_view_overrides(
        artifact, ViewOverrides(artifact_fingerprint=artifact.fingerprint())
    )
    assert displayed.x == artifact.layout.x and displayed.y == artifact.layout.y
    assert displayed.overridden == ()


def test_overrides_reject_non_finite_positions(artifact: SociomapArtifact) -> None:
    with pytest.raises(ValidationError, match="finite"):
        ViewOverrides(artifact_fingerprint="f").with_position("alice", math.nan, 0.0)


# --------------------------------------------------------------------------- #
# What-if is a layer over immutable originals


def test_what_if_derives_new_inputs_and_leaves_the_base_untouched(
    artifact: SociomapArtifact,
) -> None:
    before_fp = artifact.fingerprint()
    layer = WhatIfLayer(
        base_artifact_fingerprint=before_fp,
        edits=(
            RelationEdit(source="alice", target="bob", value=0.95),
            RelationEdit(source="bob", target="alice", value=None),
        ),
        label="alice and bob collaborate",
    )
    derived = derive_what_if_relation(artifact, layer)

    assert artifact.fingerprint() == before_fp
    assert artifact.relation.cell("alice", "bob") == 0.2
    assert artifact.relation.cell("bob", "alice") == 0.3
    assert derived.cell("alice", "bob") == 0.95
    assert derived.cell("bob", "alice") is None
    for s in IDS:
        for t in IDS:
            if (s, t) not in {("alice", "bob"), ("bob", "alice")}:
                assert derived.cell(s, t) == artifact.relation.cell(s, t)

    inputs = what_if_inputs(artifact, layer)
    assert inputs["relation"] == derived
    assert inputs["spec"] == artifact.spec
    assert inputs["provenance_inputs"] == {WHAT_IF_BASE_KEY: before_fp}


def test_what_if_layer_must_be_bound_and_non_empty(artifact: SociomapArtifact) -> None:
    with pytest.raises(ValidationError, match="no edits"):
        WhatIfLayer(base_artifact_fingerprint="f", edits=())
    with pytest.raises(ValidationError, match="name its base"):
        WhatIfLayer(
            base_artifact_fingerprint=" ", edits=(RelationEdit(source="a", target="b", value=1.0),)
        )
    stale = WhatIfLayer(
        base_artifact_fingerprint="0" * 64,
        edits=(RelationEdit(source="alice", target="bob", value=1.0),),
    )
    with pytest.raises(ViewOverrideMismatch, match="different base"):
        derive_what_if_relation(artifact, stale)
    unknown = WhatIfLayer(
        base_artifact_fingerprint=artifact.fingerprint(),
        edits=(RelationEdit(source="alice", target="zed", value=1.0),),
    )
    with pytest.raises(ViewOverrideMismatch, match="unknown entity"):
        derive_what_if_relation(artifact, unknown)


def test_what_if_result_lineage_is_recorded_in_provenance(artifact: SociomapArtifact) -> None:
    """A derived artifact names its base; the base never names the derivative."""
    layer = WhatIfLayer(
        base_artifact_fingerprint=artifact.fingerprint(),
        edits=(RelationEdit(source="carol", target="dave", value=0.5),),
    )
    derived_relation = derive_what_if_relation(artifact, layer)
    derived = artifact.model_copy(
        update={
            "relation": derived_relation,
            "provenance": artifact.provenance.model_copy(
                update={
                    "input_fingerprints": {
                        **artifact.provenance.input_fingerprints,
                        **layer.provenance_inputs(),
                        "relation": derived_relation.fingerprint(),
                    }
                }
            ),
        }
    )
    assert derived.provenance.input_fingerprints[WHAT_IF_BASE_KEY] == artifact.fingerprint()
    assert derived.fingerprint() != artifact.fingerprint()
    assert WHAT_IF_BASE_KEY not in artifact.provenance.input_fingerprints
