"""The signed-off methodology's object positions against the owner's code, on any platform.

``fixtures/sociomap/aia/signed_off_layout.json`` holds six seeded studies (8, 12, 12, 20, 3
and 2 objects; the 20-object one with its planted truth) and what the methodology's own code
computes from them: the soft-rank layout's internals, its full run, Interval MDS, the ruler
scale and the method its fixed object-count rule picks, produced outside this repository on
macOS arm64 under numpy 2.5 / scipy 1.18 / numba 0.68.

With the same library versions macOS and Linux agree on everything deterministic but can
give different full soft-rank maps (the compiled kernel's last bits differ, and the criterion
is chaotic). So this file is exact where the method is deterministic on every platform (the
scaled relations, soft ranks, active rows, random starts, the rule, Interval MDS, the ruler
scale) and statistical for full soft-rank runs (recovery of the planted map, the kept
restart's hard-rank Spearman, determinism within a machine).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from aia_core.domain.sociomap.engine_v2 import compute_object_map
from aia_core.domain.sociomap.layout import LayoutAlgorithm
from aia_core.domain.sociomap.metrics import ObjectRole
from aia_core.domain.sociomap.models_v3 import ObjectMapInputs, RatingItem, SociomapArtifactV3
from aia_core.domain.sociomap.signed_off_inputs import PreparedInputs, prepare
from aia_core.domain.sociomap.signed_off_layout import (
    PositionMethod,
    choose_method,
    classical_start,
    interval_mds,
    prep_a,
    rescale_unit,
    soft_rank_spearman,
    to_ruler,
    za_rows,
)
from aia_core.domain.sociomap.slots import DISTANCE, STRESS_1
from aia_core.domain.sociomap.specification import (
    AIA_SOCIOMAP_V1,
    AIA_SOCIOMAP_V4,
    AIA_SOCIOMAP_V5,
    IntervalMdsSpec,
    SociomapSpecV3,
    UnsupportedMethodology,
    require_supported,
    spec_payload,
)

FIXTURE = json.loads(
    (Path(__file__).parent / "fixtures/sociomap/aia/signed_off_layout.json").read_text("utf-8")
)
STUDIES = {study["name"]: study for study in FIXTURE["studies"]}
#: The fixture names the soft-rank method by its optimiser, as the original does.
METHODS = {"bb1": PositionMethod.SOFT_RANK_SPEARMAN_COULOMB, "interval_mds": "interval_mds"}
SRS = AIA_SOCIOMAP_V5.layout.soft_rank_spearman
assert SRS is not None


def _floats(value: Any) -> np.ndarray[Any, np.dtype[np.float64]]:
    return np.array(
        np.vectorize(lambda v: np.nan if v is None else v, otypes=[float])(value), dtype=float
    )


def _prepared(name: str) -> PreparedInputs:
    return prepare(
        _floats(STUDIES[name]["ratings"]),
        n_min=10,
        layout_floor=5,
        layout_weight_full_at=20,
        false_discovery_rate=0.05,
        noise_rule=True,
        noise_permutations=100,
        noise_seed=0,
        precision_weight_cap=20.0,
        sparse_share=0.30,
        min_layout_partners=3,
    )


def _fitted(prepared: PreparedInputs) -> np.ndarray[Any, np.dtype[np.bool_]]:
    m = len(prepared.unknown_layout)
    out: np.ndarray[Any, np.dtype[np.bool_]] = ~prepared.unknown_layout & ~np.eye(m, dtype=bool)
    return out


def _run(name: str, *, seed: int = 1, restarts: int = 10) -> Any:
    return soft_rank_spearman(
        _prepared(name),
        repulsion_weight=0.15,
        seed=seed,
        restarts_below_ten_objects=15,
        restarts=restarts,
        max_passes=500,
        min_partners=3,
    )


def _triplet_accuracy(xy: Any, truth: Any) -> float:
    """The methodology's self-test criterion: the share of triplets (i; j, k) with
    ``|truth_ij - truth_ik| > 0.02`` whose order the map reproduces."""
    d = np.sqrt(((xy[:, None] - xy[None]) ** 2).sum(-1))
    m, good, total = len(xy), 0, 0
    for i in range(m):
        for j in range(m):
            for k in range(j + 1, m):
                if i in (j, k) or abs(truth[i, j] - truth[i, k]) <= 0.02:
                    continue
                total += 1
                good += (truth[i, j] < truth[i, k]) == (d[i, j] < d[i, k])
    return good / total


SOFT_RANK_STUDIES = sorted(name for name, s in STUDIES.items() if "bb1" in s)


@pytest.mark.parametrize("name", SOFT_RANK_STUDIES)
def test_the_deterministic_parts_match_the_methodologys_own_code_exactly(name: str) -> None:
    bb1, prepared = STUDIES[name]["bb1"], _prepared(name)
    a = prep_a(prepared.relation_layout)
    np.testing.assert_allclose(a, _floats(bb1["prep_A"]), rtol=0, atol=1e-12)
    m = len(a)
    off = ~np.eye(m, dtype=bool)
    ws = prepared.layout_weight * off
    ranked = ws > 0
    active = ranked.sum(1) >= 3
    if (ws == off).all():
        active = np.ones(m, bool)
    assert active.tolist() == bb1["active"]
    za = za_rows(a, ranked, ws, 1.0 / min(m, 50) ** 2)
    np.testing.assert_allclose(za, _floats(bb1["zA"]), rtol=0, atol=1e-12)
    # The random starts; the classical start's eigenvector signs are the platform's LAPACK's.
    rng = np.random.default_rng(SRS.seed)
    starts = bb1["starts"]
    assert len(starts) == (SRS.restarts_below_ten_objects if m < 10 else SRS.restarts)
    for start in starts[1:]:
        np.testing.assert_allclose(
            rescale_unit(rng.random((m, 2))), _floats(start), rtol=0, atol=1e-12
        )
    first = classical_start(a)
    assert first.min() >= -1e-12 and first.max() <= 1 + 1e-12


def test_the_fixed_object_count_rule() -> None:
    srs = PositionMethod.SOFT_RANK_SPEARMAN_COULOMB
    rule = {m: choose_method(m, SRS.min_objects, SRS.max_objects) for m in (2, 3, 4, 163, 164)}
    assert rule == {
        2: PositionMethod.INTERVAL_MDS,
        3: PositionMethod.INTERVAL_MDS,
        4: srs,
        163: srs,
        164: PositionMethod.INTERVAL_MDS,
    }
    for study in STUDIES.values():
        m = len(study["layout"])
        assert choose_method(m, SRS.min_objects, SRS.max_objects) == METHODS[study["method"]]


@pytest.mark.parametrize("name", sorted(STUDIES))
def test_interval_mds_matches_the_methodologys_own_code(name: str) -> None:
    xy, iterations = interval_mds(_prepared(name), starts=2, kappa=0.5)
    np.testing.assert_allclose(xy, _floats(STUDIES[name]["interval_mds"]), rtol=0, atol=1e-9)
    assert iterations >= 1


@pytest.mark.parametrize("name", sorted(STUDIES))
def test_the_ruler_scale_matches_the_methodologys_own_code(name: str) -> None:
    study, prepared = STUDIES[name], _prepared(name)
    ruler = to_ruler(_floats(study["layout"]), prepared.delta_layout, _fitted(prepared))
    np.testing.assert_allclose(ruler, _floats(study["ruler"]), rtol=0, atol=1e-12)
    # No fitted pair: the root-mean-square distance becomes sqrt 2.
    none = np.zeros((len(ruler), len(ruler)), bool)
    lone = to_ruler(_floats(study["layout"]), prepared.delta_layout, none)
    d = np.sqrt(((lone[:, None] - lone[None]) ** 2).sum(-1))[np.triu_indices(len(lone), 1)]
    assert np.sqrt((d**2).mean()) == pytest.approx(np.sqrt(2), abs=1e-12)


def test_the_soft_rank_layout_recovers_the_planted_map() -> None:
    study = STUDIES["twenty"]
    run = _run("twenty")
    assert run.points.min() >= -1e-12 and run.points.max() <= 1 + 1e-12
    assert _triplet_accuracy(run.points, _floats(study["truth_delta"])) > 0.85
    for name in SOFT_RANK_STUDIES:
        kept = _run(name)
        assert kept.points.min() >= -1e-12 and kept.points.max() <= 1 + 1e-12, name
        assert kept.hrs == max(kept.all_hrs), name
        assert kept.hrs == pytest.approx(STUDIES[name]["bb1"]["hrs"], abs=0.01), name


def test_the_soft_rank_layout_is_deterministic_and_honours_its_restarts_and_seed() -> None:
    first, again = _run("sparse"), _run("sparse")
    assert np.array_equal(first.points, again.points) and first.all_f == again.all_f
    assert len(first.all_hrs) == len(first.all_passes) == 10
    assert len(_run("complete").all_hrs) == 15  # below ten objects
    assert len(_run("sparse", restarts=3).all_hrs) == 3
    # Another seed draws other random starts; the classical first start is the same.
    other = _run("sparse", seed=2)
    assert other.all_f[0] == first.all_f[0] and other.all_f[1:] != first.all_f[1:]


# --------------------------------------------------------------------------- the object map


def _inputs(name: str) -> ObjectMapInputs:
    ratings = STUDIES[name]["ratings"]
    ids = tuple(f"o{j}" for j in range(len(ratings[0])))
    people = tuple(f"r{k}" for k in range(len(ratings)))
    return ObjectMapInputs(
        respondent_ids=people,
        donor_ids=people,
        items=tuple(RatingItem(item_id=i, scale_min=1, scale_max=10) for i in ids),
        values=tuple(tuple(row) for row in ratings),
        weights=tuple(1.0 + (k % 3) for k in range(len(ratings))),
        object_ids=ids,
        object_items=ids,
        roles=dict.fromkeys(ids, ObjectRole.PRIMARY.value),
    )


@pytest.mark.parametrize("name", ["complete", "three", "two"])
def test_the_object_map_records_the_signed_off_positions_under_aia_sociomap_5(name: str) -> None:
    study, prepared = STUDIES[name], _prepared(name)
    artifact = compute_object_map(_inputs(name), AIA_SOCIOMAP_V5, connectedness_interval=False)
    layout = artifact.layout
    assert layout is not None and artifact.outcome == "MAPPED"
    assert layout.method == METHODS[study["method"]]
    fitted = _fitted(prepared)
    if layout.method == PositionMethod.INTERVAL_MDS:
        np.testing.assert_allclose(layout.points, _floats(study["ruler"]), rtol=0, atol=1e-9)
    else:
        # The kept soft-rank map, scaled to the ruler: whatever the platform's run gave.
        expected = to_ruler(_run(name).points, prepared.delta_layout, fitted)
        assert np.array_equal(np.array(layout.points), expected)
    # No Stress-1: the methodology judges a map by its split-half check.
    stored = artifact.model_dump(mode="json")["layout"]
    assert layout.stress_1 is layout.raw_stress is layout.quality is None
    assert not {"stress_1", "raw_stress", "quality"} & stored.keys()
    assert layout.known_pairs == int(fitted.sum()) // 2 and layout.start_fill is None
    assert SociomapArtifactV3.from_payload(artifact.to_payload()) == artifact
    # Earlier presets record no method and keep their Stress-1: stored maps read as before.
    if name == "complete":
        v4 = compute_object_map(_inputs(name), AIA_SOCIOMAP_V4, connectedness_interval=False)
        assert v4.layout is not None and v4.layout.stress_1 is not None
        assert "method" not in v4.model_dump(mode="json")["layout"]


def _with_layout(**update: Any) -> SociomapSpecV3:
    return AIA_SOCIOMAP_V5.model_copy(
        update={"layout": AIA_SOCIOMAP_V5.layout.model_copy(update=update)}
    )


def test_the_signed_off_layout_is_declared_whole_and_refuses_what_it_does_not_read() -> None:
    require_supported(AIA_SOCIOMAP_V5)
    assert AIA_SOCIOMAP_V5.layout.algorithm == LayoutAlgorithm.SOFT_RANK_SPEARMAN_OR_INTERVAL_MDS
    # The signed-off layout and the baseline-corrected relation come together.
    for spec, field in (
        (_with_layout(algorithm=LayoutAlgorithm.AIA_SMACOF_OBJECTS_V1), "layout.algorithm"),
        (_with_layout(interval_mds=None), "layout.interval_mds"),
        (_with_layout(max_iterations=100), "layout.max_iterations"),
        (_with_layout(tolerance=1e-6), "layout.tolerance"),
        (_with_layout(min_objects=1), "layout.min_objects"),
        (_with_layout(stress_bands=(0.05, 0.10, 0.20)), "layout.stress_bands"),
        (_with_layout(layout_weight_full_at=3), "layout.layout_weight_full_at"),
        (
            _with_layout(interval_mds=IntervalMdsSpec(random_starts=2, floor_fraction=1.5)),
            "layout.interval_mds.floor_fraction",
        ),
        (
            _with_layout(soft_rank_spearman=SRS.model_copy(update={"min_objects": 200})),
            "layout.soft_rank_spearman.min_objects",
        ),
        (
            _with_layout(soft_rank_spearman=SRS.model_copy(update={"restarts": 0})),
            "layout.soft_rank_spearman.restarts",
        ),
    ):
        with pytest.raises(UnsupportedMethodology) as refused:
            require_supported(spec)
        assert field in refused.value.unsupported
    borrowed = AIA_SOCIOMAP_V4.model_copy(
        update={
            "layout": AIA_SOCIOMAP_V4.layout.model_copy(
                update={"algorithm": LayoutAlgorithm.SOFT_RANK_SPEARMAN_OR_INTERVAL_MDS}
            )
        }
    )
    with pytest.raises(UnsupportedMethodology) as refused:
        require_supported(borrowed)
    assert "layout.algorithm" in refused.value.unsupported
    assert "soft_rank_spearman" not in spec_payload(AIA_SOCIOMAP_V4)["spec"]["layout"]
    # Contract 2 places respondents and objects together and refuses it by name.
    joint = AIA_SOCIOMAP_V1.model_copy(
        update={
            "layout": AIA_SOCIOMAP_V1.layout.model_copy(
                update={"algorithm": LayoutAlgorithm.SOFT_RANK_SPEARMAN_OR_INTERVAL_MDS}
            )
        }
    )
    with pytest.raises(UnsupportedMethodology) as refused:
        require_supported(joint)
    assert "contract 3" in refused.value.unsupported["layout.algorithm"]
    # The SMACOF target and Stress-1 formulas are not read under it: refused, not stored to
    # do nothing.
    with pytest.raises(UnsupportedMethodology) as refused:
        compute_object_map(
            _inputs("three"),
            AIA_SOCIOMAP_V5,
            connectedness_interval=False,
            slots={DISTANCE: lambda **_: 0.0, STRESS_1: lambda **_: 0.0},
        )
    assert set(refused.value.unsupported) == {DISTANCE, STRESS_1}


def test_no_pair_at_the_layout_floor_is_not_mappable() -> None:
    # Every pair has two co-raters: below the layout floor of 5.
    ratings = [[1, 5, None, None], [3, 9, None, None], [None, None, 2, 8], [None, None, 7, 1]]
    ids = ("a", "b", "c", "d")
    people = tuple(f"r{k}" for k in range(4))
    inputs = ObjectMapInputs(
        respondent_ids=people,
        donor_ids=people,
        items=tuple(RatingItem(item_id=i, scale_min=1, scale_max=10) for i in ids),
        values=tuple(tuple(row) for row in ratings),
        weights=(1.0,) * 4,
        object_ids=ids,
        object_items=ids,
        roles=dict.fromkeys(ids, ObjectRole.PRIMARY.value),
    )
    artifact = compute_object_map(inputs, AIA_SOCIOMAP_V5, connectedness_interval=False)
    assert artifact.outcome == "NOT_MAPPABLE" and artifact.not_mappable is not None
    assert artifact.not_mappable.reason == "NO_KNOWN_PAIR"
