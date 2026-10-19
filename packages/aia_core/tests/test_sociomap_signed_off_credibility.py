"""The signed-off methodology's map credibility, number for number against its code.

``fixtures/sociomap/aia/signed_off_credibility.json`` holds nine studies -- six seeded ones (8,
12, 12 very sparse, 20, 3 and 2 objects) and three edge cases (halves too small to map, too few
respondents to bootstrap, pure noise) -- and what the methodology's own code computes from their
ratings, with the AIA panel's fallbacks: the split-half agreement (or the error that stopped
it), which rule decided, whether the map is weakly determined, the RELIABLE pairs, the
uncertainty radius and each object's spread (or the error that stopped them), produced outside
this repository under numpy 2.5. Every map behind them is Interval MDS, so this stage is checked
exactly (scores and radii to 1e-12, rules and flags as they are) on these studies, on macOS and
Linux alike. On data full of ties a near-zero distance difference can change sign between
platforms, and with it the split-half score; the fixture's studies have none.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from aia_core.domain.sociomap import engine_v2
from aia_core.domain.sociomap.engine_v2 import _credibility, _prepare, _ratings, compute_object_map
from aia_core.domain.sociomap.metrics import ObjectRole
from aia_core.domain.sociomap.models_v3 import (
    CredibilityRule,
    MapCredibility,
    ObjectMapInputs,
    RatingItem,
    SociomapArtifactV3,
)
from aia_core.domain.sociomap.signed_off_credibility import map_uncertainty, split_half_agreement
from aia_core.domain.sociomap.signed_off_layout import interval_mds
from aia_core.domain.sociomap.specification import (
    AIA_SOCIOMAP_V4,
    AIA_SOCIOMAP_V5,
    SociomapSpecV3,
    UnsupportedMethodology,
    require_supported,
    spec_payload,
)

FIXTURE = json.loads(
    (Path(__file__).parent / "fixtures/sociomap/aia/signed_off_credibility.json").read_text("utf-8")
)
STUDIES = {study["name"]: study for study in FIXTURE["studies"]}
CREDIBILITY = AIA_SOCIOMAP_V5.credibility
IMDS = AIA_SOCIOMAP_V5.layout.interval_mds
assert CREDIBILITY is not None and IMDS is not None


def _family(name: str) -> list[list[float | None]]:
    return [list(row) for row in STUDIES[name]["ratings"]]


def _map_of(part: Any) -> Any:
    return interval_mds(
        _prepare(part, AIA_SOCIOMAP_V5, noise_rule=False),
        starts=IMDS.random_starts,
        kappa=IMDS.floor_fraction,
    )[0]


def _credibility_of(name: str, spec: SociomapSpecV3 = AIA_SOCIOMAP_V5) -> MapCredibility:
    family = _family(name)
    prepared = _prepare(_ratings(family, len(family[0])), spec)
    return _credibility(family, prepared, spec)


def _inputs(name: str) -> ObjectMapInputs:
    ratings = STUDIES[name]["ratings"]
    ids = tuple(f"o{j}" for j in range(len(ratings[0])))
    people = tuple(f"r{k}" for k in range(len(ratings)))
    return ObjectMapInputs(
        respondent_ids=people,
        donor_ids=people,
        items=tuple(RatingItem(item_id=i, scale_min=1, scale_max=10) for i in ids),
        values=tuple(tuple(row) for row in ratings),
        weights=(1.0,) * len(people),
        object_ids=ids,
        object_items=ids,
        roles=dict.fromkeys(ids, ObjectRole.PRIMARY.value),
    )


@pytest.mark.parametrize("name", sorted(STUDIES))
def test_the_split_half_check_and_the_radius_match_the_methodologys_own_code(name: str) -> None:
    study = STUDIES[name]
    ratings = _ratings(_family(name), len(study["ratings"][0]))
    if study["split_half_error"] is None:
        score = split_half_agreement(
            ratings,
            splits=CREDIBILITY.split_half_splits,
            seed=CREDIBILITY.split_half_seed,
            map_of=_map_of,
        )
        # Two objects have no triplet: no score, which the fixture stores as null.
        if study["split_half"] is None:
            assert np.isnan(score)
        else:
            assert score == pytest.approx(study["split_half"], abs=1e-12)
    else:
        with pytest.raises(np.linalg.LinAlgError):
            split_half_agreement(ratings, splits=2, seed=0, map_of=_map_of)
    if study["radius_error"] is None:
        uncertainty = map_uncertainty(
            ratings,
            resamples=CREDIBILITY.bootstrap_resamples,
            seed=CREDIBILITY.bootstrap_seed,
            safety=CREDIBILITY.safety_factor,
            map_of=_map_of,
        )
        assert uncertainty.radius == pytest.approx(study["radius"], abs=1e-12)
        np.testing.assert_allclose(uncertainty.per_object, study["per_object"], rtol=0, atol=1e-12)
    else:
        with pytest.raises(np.linalg.LinAlgError):
            map_uncertainty(ratings, resamples=20, seed=0, safety=1.2, map_of=_map_of)


@pytest.mark.parametrize("name", sorted(STUDIES))
def test_the_rule_and_the_flag_are_the_panels(name: str) -> None:
    study, credibility = STUDIES[name], _credibility_of(name)
    # The split-half check decides exactly when it has a score.
    assert (
        credibility.rule
        == study["rule"]
        == (
            CredibilityRule.NO_RELIABLE_PAIR
            if study["split_half"] is None
            else CredibilityRule.SPLIT_HALF
        )
    )
    assert credibility.weakly_determined is study["weakly_determined"]
    assert credibility.reliable_pairs == study["n_reliable"]
    assert credibility.threshold == CREDIBILITY.split_half_threshold
    if study["split_half"] is None:
        assert credibility.split_half is None
    else:
        assert credibility.split_half == pytest.approx(study["split_half"], abs=1e-12)
    if study["radius"] is None:
        assert credibility.uncertainty_radius is None
    else:
        assert credibility.uncertainty_radius == pytest.approx(study["radius"], abs=1e-12)


def test_the_studies_cover_the_fallbacks() -> None:
    # A half the methodology cannot map, two objects without a triplet, and no bootstrap map.
    assert STUDIES["halves_fail"]["split_half_error"] == "LinAlgError"
    assert STUDIES["very_sparse"]["split_half_error"] == "LinAlgError"
    assert STUDIES["two"]["split_half"] is None and STUDIES["two"]["split_half_error"] is None
    assert STUDIES["bootstrap_fails"]["radius_error"] == "LinAlgError"
    # Weakly determined by each rule: noise by the split-half check, the failed halves by no
    # reliable pair; and a two-object map with a reliable pair is not.
    assert STUDIES["noise"]["split_half"] < 0.59 and STUDIES["noise"]["weakly_determined"]
    assert STUDIES["halves_fail"]["weakly_determined"] and STUDIES["halves_fail"]["n_reliable"] == 0
    assert not STUDIES["two"]["weakly_determined"] and STUDIES["two"]["n_reliable"] == 1


def test_a_half_with_no_layout_pair_falls_back_to_the_no_reliable_pair_rule() -> None:
    # Two objects rated by nine people: the map stands on its one pair, a half of four has no
    # pair at the layout floor, and Interval MDS divides by zero, as the original does.
    rng = np.random.default_rng(3)
    family = rng.integers(1, 11, (9, 2)).astype(float).tolist()
    ratings = _ratings(family, 2)
    with pytest.raises(ZeroDivisionError):
        split_half_agreement(ratings, splits=2, seed=0, map_of=_map_of)
    credibility = _credibility(family, _prepare(ratings, AIA_SOCIOMAP_V5), AIA_SOCIOMAP_V5)
    assert credibility.rule == CredibilityRule.NO_RELIABLE_PAIR
    assert credibility.split_half is None and credibility.uncertainty_radius is not None


def test_any_other_error_propagates(monkeypatch: pytest.MonkeyPatch) -> None:
    def broken(*args: Any, **kwargs: Any) -> Any:
        raise ValueError("a defect, not too little data")

    monkeypatch.setattr(engine_v2, "split_half_agreement", broken)
    with pytest.raises(ValueError, match="a defect"):
        _credibility_of("three")
    monkeypatch.undo()
    monkeypatch.setattr(engine_v2, "map_uncertainty", broken)
    with pytest.raises(ValueError, match="a defect"):
        _credibility_of("three")


def test_the_object_map_stores_the_credibility_under_aia_sociomap_5() -> None:
    # Every study the map draws records the credibility of its own ratings.
    for name in STUDIES:
        drawn = compute_object_map(_inputs(name), AIA_SOCIOMAP_V5, connectedness_interval=False)
        if drawn.layout is not None:
            assert drawn.credibility == _credibility_of(name)
    artifact = compute_object_map(_inputs("three"), AIA_SOCIOMAP_V5, connectedness_interval=False)
    stored = artifact.model_dump(mode="json")
    assert set(stored["credibility"]) == {
        "rule",
        "split_half",
        "threshold",
        "weakly_determined",
        "reliable_pairs",
        "uncertainty_radius",
    }
    assert stored["spec"]["credibility"] == CREDIBILITY.model_dump(mode="json")
    assert SociomapArtifactV3.from_payload(artifact.to_payload()) == artifact
    # A map that is not drawn has nothing to judge.
    unmapped = compute_object_map(
        _inputs("bootstrap_fails"), AIA_SOCIOMAP_V5, connectedness_interval=False
    )
    assert unmapped.layout is None and unmapped.credibility is None
    assert "credibility" not in unmapped.model_dump(mode="json")


def test_earlier_presets_store_exactly_what_they_stored() -> None:
    v4 = compute_object_map(_inputs("three"), AIA_SOCIOMAP_V4, connectedness_interval=False)
    assert v4.credibility is None
    assert "credibility" not in v4.model_dump(mode="json")
    assert "credibility" not in spec_payload(AIA_SOCIOMAP_V4)["spec"]


def _with(**update: Any) -> SociomapSpecV3:
    assert CREDIBILITY is not None
    return AIA_SOCIOMAP_V5.model_copy(update={"credibility": CREDIBILITY.model_copy(update=update)})


def test_the_credibility_is_declared_exactly_under_the_signed_off_methodology() -> None:
    require_supported(AIA_SOCIOMAP_V5)
    for spec, field in (
        (AIA_SOCIOMAP_V5.model_copy(update={"credibility": None}), "credibility"),
        (AIA_SOCIOMAP_V4.model_copy(update={"credibility": CREDIBILITY}), "credibility"),
        (_with(split_half_threshold=1.5), "credibility.split_half_threshold"),
        (_with(split_half_splits=0), "credibility.split_half_splits"),
        (_with(split_half_seed=-1), "credibility.split_half_seed"),
        (_with(bootstrap_resamples=1), "credibility.bootstrap_resamples"),
        (_with(bootstrap_seed=-1), "credibility.bootstrap_seed"),
        (_with(safety_factor=0.0), "credibility.safety_factor"),
    ):
        with pytest.raises(UnsupportedMethodology) as refused:
            require_supported(spec)
        assert field in refused.value.unsupported


def test_every_value_of_the_stage_changes_the_map_when_edited() -> None:
    def credibility(spec: SociomapSpecV3) -> MapCredibility:
        artifact = compute_object_map(_inputs("complete"), spec, connectedness_interval=False)
        assert artifact.credibility is not None
        return artifact.credibility

    base = credibility(AIA_SOCIOMAP_V5)
    assert base.rule == CredibilityRule.SPLIT_HALF and not base.weakly_determined
    assert base.split_half is not None and base.uncertainty_radius is not None
    # The complete study agrees on 0.607 of its triplets: just above the threshold.
    assert credibility(_with(split_half_threshold=0.65)).weakly_determined
    assert credibility(_with(split_half_splits=3)).split_half != base.split_half
    assert credibility(_with(split_half_seed=1)).split_half != base.split_half
    assert credibility(_with(bootstrap_resamples=10)).uncertainty_radius != base.uncertainty_radius
    assert credibility(_with(bootstrap_seed=1)).uncertainty_radius != base.uncertainty_radius
    assert credibility(_with(safety_factor=2.4)).uncertainty_radius == pytest.approx(
        2 * base.uncertainty_radius, rel=1e-12
    )
