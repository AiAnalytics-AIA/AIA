"""Invariant tests for the Sociomapping contracts: spec v2 and the input types.

What the product requires of a Sociomapa regardless of algorithm:

* methodology is explicit, versioned and fingerprinted, with no hidden default;
* an unsupported method fails closed instead of becoming a different algorithm
  (the engine-level refusals are in ``test_sociomap_engine.py``);
* inputs are validated (square or rectangular as declared, unique ids, finite,
  aligned) and missing values are preserved rather than imputed.

The artifact, view and scenario invariants are tested end to end in
``test_sociomap_engine.py``, against artifacts the engine actually produced.
"""

from __future__ import annotations

import itertools
import json
import math
from typing import Any

import pytest
from pydantic import ValidationError

from aia_core.domain.sociomap import (
    AIA_SOCIOMAP_V1,
    SPEC_CONTRACT_VERSION,
    TERRAIN66_OBJECT,
    TERRAIN66_RESPONDENT,
    MetricValues,
    RatingsMatrix,
    RelationMatrix,
    SociomapSpec,
    UnsupportedMethodology,
    require_supported,
)

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


def spec_dict() -> dict[str, Any]:
    return AIA_SOCIOMAP_V1.model_dump(mode="json")


# --------------------------------------------------------------------------- #
# SociomapSpec v2: explicit, versioned, fingerprinted


def test_contract_version_is_two() -> None:
    assert SPEC_CONTRACT_VERSION == "2"


def _paths(tree: dict[str, Any], prefix: str = "") -> list[str]:
    out: list[str] = []
    for key, value in tree.items():
        path = f"{prefix}{key}"
        out.append(path)
        if isinstance(value, dict) and key != "parameters":
            out.extend(_paths(value, f"{path}."))
    return out


@pytest.mark.parametrize("path", _paths(spec_dict()))
def test_spec_has_no_hidden_defaults(path: str) -> None:
    """Removing any field, at any depth, makes the spec unconstructible."""
    tree = spec_dict()
    node = tree
    *parents, leaf = path.split(".")
    for key in parents:
        node = node[key]
    del node[leaf]
    with pytest.raises(ValidationError):
        SociomapSpec.model_validate(tree)


def test_spec_is_frozen_and_forbids_extras() -> None:
    with pytest.raises(ValidationError):
        AIA_SOCIOMAP_V1.methodology_version = "other"  # type: ignore[misc]
    tree = spec_dict()
    tree["layout"]["auto_fallback"] = True
    with pytest.raises(ValidationError):
        SociomapSpec.model_validate(tree)


def test_blank_methodology_version_is_refused() -> None:
    with pytest.raises(ValidationError, match="must be stated"):
        SociomapSpec.model_validate({**spec_dict(), "methodology_version": "  "})


def test_rating_scale_must_be_ordered_and_finite() -> None:
    tree = spec_dict()
    tree["ratings"]["rating_scale_max"] = 1.0
    with pytest.raises(ValidationError, match="must exceed"):
        SociomapSpec.model_validate(tree)
    tree["ratings"]["rating_scale_max"] = math.inf
    with pytest.raises(ValidationError, match="finite"):
        SociomapSpec.model_validate(tree)


@pytest.mark.parametrize(
    "path",
    [
        "layout.map_frame.extent",
        "layout.seed",
        "ratings.rating_scale_min",
        "ratings.rating_scale_max",
        "terrain.respondent.sigma",
    ],
)
def test_json_booleans_are_refused_where_numbers_are_expected(path: str) -> None:
    # pydantic coerces true -> 1.0 before an after-validator sees it; "extent":
    # true would silently compress every map to extent 1.
    tree = spec_dict()
    node = tree
    *parents, leaf = path.split(".")
    for key in parents:
        node = node[key]
    node[leaf] = True
    with pytest.raises(ValidationError, match="boolean"):
        SociomapSpec.model_validate(json.loads(json.dumps(tree)))


def test_map_frame_extent_must_be_positive() -> None:
    tree = spec_dict()
    tree["layout"]["map_frame"]["extent"] = 0
    with pytest.raises(ValidationError):
        SociomapSpec.model_validate(tree)


@pytest.mark.parametrize("bad", [math.nan, math.inf, object()])
def test_layout_parameters_must_be_json_data(bad: Any) -> None:
    tree = spec_dict()
    tree["layout"]["parameters"] = {"x": bad}
    with pytest.raises(ValidationError):
        SociomapSpec.model_validate(tree)


def test_spec_fingerprint_is_stable_and_order_independent() -> None:
    tree = spec_dict()
    reordered = dict(reversed(list(tree.items())))
    assert SociomapSpec.model_validate(reordered).fingerprint() == AIA_SOCIOMAP_V1.fingerprint()
    assert len(AIA_SOCIOMAP_V1.fingerprint()) == 64


@pytest.mark.parametrize(
    ("path", "value"),
    [
        ("methodology_version", "aia-sociomap-1b"),
        ("ratings.rating_scale_max", 9.0),
        ("relation", None),
        ("layout.parameters.max_iterations", 2001),
        ("layout.parameters.convergence_tolerance", 1e-8),
        ("layout.map_frame.extent", 44.0),
        ("metrics.object_height_metric", "mean_rating"),
        ("terrain.respondent.sigma", 9.4),
        ("terrain.object.kernel_cutoff", 0.001),
        ("terrain.normalization", "sigma"),
    ],
)
def test_every_field_changes_the_fingerprint(path: str, value: Any) -> None:
    tree = spec_dict()
    node = tree
    *parents, leaf = path.split(".")
    for key in parents:
        node = node[key]
    node[leaf] = value
    assert SociomapSpec.model_validate(tree).fingerprint() != AIA_SOCIOMAP_V1.fingerprint()


def test_spec_round_trips_through_json() -> None:
    restored = SociomapSpec.model_validate(json.loads(AIA_SOCIOMAP_V1.model_dump_json()))
    assert restored == AIA_SOCIOMAP_V1
    assert restored.fingerprint() == AIA_SOCIOMAP_V1.fingerprint()


def test_the_preset_is_supported_and_uses_the_reference_terrain_constants() -> None:
    require_supported(AIA_SOCIOMAP_V1)
    assert AIA_SOCIOMAP_V1.terrain.respondent == TERRAIN66_RESPONDENT
    assert AIA_SOCIOMAP_V1.terrain.object == TERRAIN66_OBJECT
    assert AIA_SOCIOMAP_V1.layout.seed is None


def test_require_supported_reports_every_problem_at_once() -> None:
    tree = spec_dict()
    tree["ratings"]["dissimilarity"] = "rank"
    tree["layout"]["algorithm"] = "python_weighted_unfolding"
    tree["layout"]["map_frame"]["method"] = "fit_to_screen"
    tree["terrain"]["normalization"] = "zscore"
    with pytest.raises(UnsupportedMethodology) as caught:
        require_supported(SociomapSpec.model_validate(tree))
    assert set(caught.value.unsupported) == {
        "ratings.dissimilarity",
        "layout.algorithm",
        "layout.map_frame.method",
        "terrain.normalization",
    }
    assert "no fallback is permitted" in str(caught.value)


def test_relation_policies_are_validated() -> None:
    tree = spec_dict()
    tree["relation"] = {
        "scale_coercion": "zscore",
        "position_projection": "mutual_arithmetic_mean",
        "missing_data_policy": "impute_mean",
    }
    tree["ratings"]["missing_data_policy"] = "listwise"
    with pytest.raises(UnsupportedMethodology) as caught:
        require_supported(SociomapSpec.model_validate(tree))
    assert set(caught.value.unsupported) == {
        "relation.scale_coercion",
        "relation.missing_data_policy",
        "ratings.missing_data_policy",
    }


# --------------------------------------------------------------------------- #
# RatingsMatrix


def test_ratings_shape_and_ids_are_validated() -> None:
    ok = RatingsMatrix(respondent_ids=("r1",), object_ids=("a", "b", "c"), values=((1, None, 3),))
    assert ok.values == ((1.0, None, 3.0),)
    with pytest.raises(ValidationError, match="at least 3"):
        RatingsMatrix(respondent_ids=("r1",), object_ids=("a", "b"), values=((1, 2),))
    with pytest.raises(ValidationError, match="rows for"):
        RatingsMatrix(respondent_ids=("r1", "r2"), object_ids=("a", "b", "c"), values=((1, 2, 3),))
    with pytest.raises(ValidationError, match="cells for"):
        RatingsMatrix(respondent_ids=("r1",), object_ids=("a", "b", "c"), values=((1, 2),))
    with pytest.raises(ValidationError, match="duplicate"):
        RatingsMatrix(respondent_ids=("r", "r"), object_ids=("a", "b", "c"), values=((1,) * 3,) * 2)


@pytest.mark.parametrize("bad", [math.nan, math.inf, True])
def test_ratings_reject_non_finite_and_boolean_cells(bad: Any) -> None:
    with pytest.raises(ValidationError):
        RatingsMatrix(respondent_ids=("r1",), object_ids=("a", "b", "c"), values=((1, bad, 3),))


def test_ratings_fingerprint_is_sensitive_to_one_cell() -> None:
    a = RatingsMatrix(respondent_ids=("r1",), object_ids=("a", "b", "c"), values=((1, 2, 3),))
    b = RatingsMatrix(respondent_ids=("r1",), object_ids=("a", "b", "c"), values=((1, 2, 4),))
    assert a.fingerprint() != b.fingerprint()


def test_metric_values_reject_non_finite_and_blank_ids() -> None:
    with pytest.raises(ValidationError, match="finite"):
        MetricValues(metric_id="m", values=(1.0, math.inf))
    with pytest.raises(ValidationError, match="blank"):
        MetricValues(metric_id=" ", values=(1.0,))


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
