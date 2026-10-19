"""The signed-off methodology's input stage, number for number against the owner's code.

``fixtures/sociomap/aia/signed_off_inputs.json`` holds three seeded studies (complete, sparse,
very sparse) and every output of the methodology's own ``prepare`` with the noise rule on at
100 permutations from seed 0, produced outside this repository under numpy 2.5 / scipy 1.18.
The port must reproduce every field: floats to 1e-9 (NaN where the fixture has null),
flags and counts exactly; ``aia-sociomap-5``'s object map must record what the port computes.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from aia_core.domain.research_sociomap import default_methods
from aia_core.domain.sociomap.engine_v2 import compute_object_map
from aia_core.domain.sociomap.metrics import ObjectRole
from aia_core.domain.sociomap.models_v3 import ObjectMapInputs, RatingItem, SociomapArtifactV3
from aia_core.domain.sociomap.signed_off_inputs import PreparedInputs, prepare
from aia_core.domain.sociomap.slots import PERSON
from aia_core.domain.sociomap.specification import (
    AIA_SOCIOMAP_V4,
    AIA_SOCIOMAP_V5,
    NoiseRuleSpec,
    UnsupportedMethodology,
    require_supported,
    spec_payload,
)

FIXTURE = json.loads(
    (Path(__file__).parent / "fixtures/sociomap/aia/signed_off_inputs.json").read_text("utf-8")
)
STUDIES = {study["name"]: study for study in FIXTURE["studies"]}

#: The fixture's names (the original's) and the port's.
FLOATS = {
    "rt": "rt",
    "n": "n",
    "p": "p",
    "delta": "delta",
    "W": "precision",
    "R": "relation",
    "Q": "charge",
    "R_layout": "relation_layout",
    "W_layout": "layout_weight",
    "delta_layout": "delta_layout",
    "W_mds_layout": "precision_layout",
    "mean_rating": "mean_rating",
}
FLAGS = {"known": "known", "reliable": "reliable", "unknown_layout": "unknown_layout"}


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


@pytest.mark.parametrize("name", sorted(STUDIES))
def test_the_port_reproduces_every_output_of_the_methodologys_own_code(name: str) -> None:
    study, port = STUDIES[name], _prepared(name)
    for key, attribute in FLOATS.items():
        expected, actual = _floats(study[key]), getattr(port, attribute)
        assert actual.shape == expected.shape, key
        assert np.array_equal(np.isnan(actual), np.isnan(expected)), key
        np.testing.assert_allclose(actual, expected, rtol=0, atol=1e-9, equal_nan=True, err_msg=key)
    for key, attribute in FLAGS.items():
        assert np.array_equal(getattr(port, attribute), np.array(study[key], dtype=bool)), key
    assert port.sparse.flag is study["sparse"]["flag"]
    assert port.sparse.weakly_connected == study["sparse"]["weakly_connected"]
    assert port.sparse.share_below_layout_floor == pytest.approx(
        study["sparse"]["share_below_layout_floor"], abs=1e-12
    )


def test_the_studies_cover_complete_sparse_and_very_sparse_data() -> None:
    # The complete study takes the noise rule's fast path, the others its general path with
    # half the permutations; the very sparse one sets the sparse-design note.
    assert set(STUDIES) == {"complete", "sparse", "very_sparse"}
    assert not np.isnan(_floats(STUDIES["complete"]["ratings"])).any()
    assert np.isnan(_floats(STUDIES["sparse"]["ratings"])).any()
    assert STUDIES["very_sparse"]["sparse"]["flag"] is True
    assert any(any(row) for row in STUDIES["complete"]["reliable"])


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
        # Unequal weights: the method is unweighted, so they must change nothing.
        weights=tuple(1.0 + (k % 3) for k in range(len(ratings))),
        object_ids=ids,
        object_items=ids,
        roles=dict.fromkeys(ids, ObjectRole.PRIMARY.value),
    )


@pytest.mark.parametrize("name", sorted(STUDIES))
def test_the_object_map_records_the_baseline_corrected_relations_under_aia_sociomap_5(
    name: str,
) -> None:
    study = STUDIES[name]
    artifact = compute_object_map(_inputs(name), AIA_SOCIOMAP_V5, connectedness_interval=True)
    relations, m = artifact.relations, len(study["rt"])
    for i in range(m):
        for j in range(m):
            if i == j:
                assert relations.r[i][j] is relations.n[i][j] is relations.status[i][j] is None
                continue
            known, reliable = study["known"][i][j], study["reliable"][i][j]
            assert relations.n[i][j] == int(study["n"][i][j])
            assert relations.interval[i][j] is None
            expected = "reliable" if reliable else "weak" if known else "unknown"
            assert relations.status[i][j] == expected
            if known:
                assert relations.r[i][j] == pytest.approx(study["rt"][i][j], abs=1e-12)
            else:
                assert relations.r[i][j] is None
    assert relations.n_min == 10
    assert artifact.sparse_design is not None
    assert artifact.sparse_design.flag is study["sparse"]["flag"]
    assert artifact.sparse_design.weakly_connected == tuple(
        f"o{k}" for k in study["sparse"]["weakly_connected"]
    )
    assert artifact.connectedness_100["status"] == "not_computed"
    assert artifact.support.weighting.startswith("the relations are unweighted")
    assert SociomapArtifactV3.from_payload(artifact.to_payload()) == artifact
    # Earlier presets record no note: their stored maps read byte for byte as before.
    v4 = compute_object_map(_inputs(name), AIA_SOCIOMAP_V4, connectedness_interval=False)
    assert "sparse_design" not in v4.model_dump(mode="json")


def test_the_baseline_corrected_relation_is_declared_whole_and_only_by_itself() -> None:
    require_supported(AIA_SOCIOMAP_V5)
    assert "aia-sociomap-5" not in [m.method_id for m in default_methods()]
    half = AIA_SOCIOMAP_V5.model_copy(
        update={"ratings": AIA_SOCIOMAP_V4.ratings, "layout": AIA_SOCIOMAP_V4.layout}
    )
    with pytest.raises(UnsupportedMethodology) as refused:
        require_supported(half)
    assert {"ratings.person_normalization", "layout.layout_floor"} <= set(refused.value.unsupported)
    borrowed = AIA_SOCIOMAP_V4.model_copy(
        update={
            "relation": AIA_SOCIOMAP_V4.relation.model_copy(
                update={"noise_rule": AIA_SOCIOMAP_V5.relation.noise_rule}
            )
        }
    )
    with pytest.raises(UnsupportedMethodology) as refused:
        require_supported(borrowed)
    assert "relation.noise_rule" in refused.value.unsupported
    assert "noise_rule" not in spec_payload(AIA_SOCIOMAP_V4)["spec"]["relation"]
    negative_seed = AIA_SOCIOMAP_V5.model_copy(
        update={
            "relation": AIA_SOCIOMAP_V5.relation.model_copy(
                update={"noise_rule": NoiseRuleSpec(enabled=True, permutations=100, seed=-1)}
            )
        }
    )
    with pytest.raises(UnsupportedMethodology) as refused:
        require_supported(negative_seed)
    assert set(refused.value.unsupported) == {"relation.noise_rule.seed"}
    # A formula the method never reads is refused, not stored to do nothing.
    with pytest.raises(UnsupportedMethodology) as refused:
        compute_object_map(
            _inputs("complete"),
            AIA_SOCIOMAP_V5,
            connectedness_interval=False,
            slots={PERSON: lambda **_: 0.0},
        )
    assert set(refused.value.unsupported) == {PERSON}
