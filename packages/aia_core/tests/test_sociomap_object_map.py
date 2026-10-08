"""``aia-sociomap-2``: spec contract 3, the object-map engine and its artifact (S2, chunk 2d).

Plan ``sociomap-formula-corrections`` § 8.2. The engine composes functions other chunks
landed and tested (2a, 1a, 2b, 2c, 1b, 4a), so the central tests here check that every
number the artifact holds is the one those functions give on the same input; the rest
check the contract's refusals, the outcomes a family can have, and that nothing stored
under contract 2 moves.
"""

from __future__ import annotations

import math
import random
import statistics
from typing import Any

import pytest

from aia_core.domain.research_design import SpecBattery, SpecObject
from aia_core.domain.research_sociomap import (
    CONNECTEDNESS_RESAMPLES,
    CONNECTEDNESS_SEED,
    SociomapMethod,
    battery_sociomap,
    default_methods,
    object_map_inputs,
    research_sociomaps,
)
from aia_core.domain.sociomap import (
    AIA_SOCIOMAP_V1,
    AIA_SOCIOMAP_V2,
    ArtifactIntegrityError,
    MapOutcome,
    NotMappableReason,
    ObjectMapInputs,
    RatingItem,
    SociomapArtifactV3,
    SociomapSpecV3,
    UnsupportedMethodology,
    compute_object_map,
    read_artifact,
    read_spec,
    require_supported,
    spec_payload,
)
from aia_core.domain.sociomap.engine_v2 import CONNECTEDNESS_OFF, NOT_PLACED_NO_SPREAD
from aia_core.domain.sociomap.layout import (
    LayoutAlgorithm,
    correlation_distances,
    fit_smacof_objects,
)
from aia_core.domain.sociomap.metrics import ObjectRole, connectedness_100, primary_scores
from aia_core.domain.sociomap.pairs import derive_pair_relations
from aia_core.domain.sociomap.relations import PairStatus, person_minmax
from aia_core.domain.sociomap.specification import (
    DissimilarityTarget,
    MapFrameMethod,
)
from aia_core.domain.sociomap.view import stress_quality

#: The v2 preset's fingerprint. It moves only when the method does, and then the preset's
#: version moves with it.
V2_FINGERPRINT = "3f1c01221492f883ce715b5763a3815ae2a8f4c1e5456f3c581a9f67838d6b43"
V1_FINGERPRINT = "9d4dffeac5531f3fc0e18c2db6a2a9c8d823d5fd299fbec30870c9aa2f31c211"


# --------------------------------------------------------------------- the spec --


def test_the_presets_fingerprints() -> None:
    assert AIA_SOCIOMAP_V2.fingerprint() == V2_FINGERPRINT
    assert AIA_SOCIOMAP_V1.fingerprint() == V1_FINGERPRINT


def test_the_v2_preset_is_supported_and_reads_back_under_contract_3() -> None:
    require_supported(AIA_SOCIOMAP_V2)
    payload = spec_payload(AIA_SOCIOMAP_V2)
    assert payload["contract_version"] == "3"
    assert read_spec(payload) == AIA_SOCIOMAP_V2
    assert read_spec(spec_payload(AIA_SOCIOMAP_V1)) == AIA_SOCIOMAP_V1


def _v1_with(**layout: Any) -> Any:
    return AIA_SOCIOMAP_V1.model_copy(
        update={"layout": AIA_SOCIOMAP_V1.layout.model_copy(update=layout)}
    )


@pytest.mark.parametrize(
    ("spec", "field"),
    [
        (
            AIA_SOCIOMAP_V1.model_copy(
                update={
                    "ratings": AIA_SOCIOMAP_V1.ratings.model_copy(
                        update={"dissimilarity": DissimilarityTarget.CORRELATION_DISTANCE}
                    )
                }
            ),
            "ratings.dissimilarity",
        ),
        (_v1_with(algorithm=LayoutAlgorithm.AIA_SMACOF_OBJECTS_V1), "layout.algorithm"),
        (
            _v1_with(
                map_frame=AIA_SOCIOMAP_V1.layout.map_frame.model_copy(
                    update={"method": MapFrameMethod.FIXED_RULER}
                )
            ),
            "layout.map_frame.method",
        ),
    ],
)
def test_contract_2_refuses_contract_3s_members(spec: Any, field: str) -> None:
    with pytest.raises(UnsupportedMethodology) as caught:
        require_supported(spec)
    assert "contract 3" in caught.value.unsupported[field]


def _v2_with(**update: Any) -> SociomapSpecV3:
    return AIA_SOCIOMAP_V2.model_copy(update=update)


@pytest.mark.parametrize(
    ("spec", "field"),
    [
        (_v2_with(respondent_placement="aia_ideal_point_v1"), "respondent_placement"),
        (_v2_with(terrain="object_envelope"), "terrain"),
        (
            _v2_with(
                layout=AIA_SOCIOMAP_V2.layout.model_copy(
                    update={"algorithm": LayoutAlgorithm.AIA_ROWCOND_UNFOLDING_V1}
                )
            ),
            "layout.algorithm",
        ),
        (
            _v2_with(
                layout=AIA_SOCIOMAP_V2.layout.model_copy(
                    update={
                        "map_frame": AIA_SOCIOMAP_V2.layout.map_frame.model_copy(
                            update={"extent": 45.0}
                        )
                    }
                )
            ),
            "layout.map_frame.extent",
        ),
        (
            _v2_with(
                layout=AIA_SOCIOMAP_V2.layout.model_copy(
                    update={
                        "map_frame": AIA_SOCIOMAP_V2.layout.map_frame.model_copy(
                            update={"method": MapFrameMethod.MAX_ABS_TO_EXTENT}
                        )
                    }
                )
            ),
            "layout.map_frame.method",
        ),
        (
            _v2_with(relation=AIA_SOCIOMAP_V2.relation.model_copy(update={"n_min": 3})),
            "relation.n_min",
        ),
        (
            _v2_with(relation=AIA_SOCIOMAP_V2.relation.model_copy(update={"confidence": 1.0})),
            "relation.confidence",
        ),
        (
            _v2_with(relation=AIA_SOCIOMAP_V2.relation.model_copy(update={"basis": "kish"})),
            "relation.basis",
        ),
        (
            _v2_with(scores=AIA_SOCIOMAP_V2.scores.model_copy(update={"height": "tscore"})),
            "scores.height",
        ),
    ],
)
def test_contract_3_refuses_what_it_cannot_compute_by_name(spec: Any, field: str) -> None:
    with pytest.raises(UnsupportedMethodology) as caught:
        require_supported(spec)
    assert field in caught.value.unsupported


def test_a_boolean_is_not_a_number_in_contract_3() -> None:
    body = spec_payload(AIA_SOCIOMAP_V2)
    body["spec"]["relation"]["n_min"] = True
    with pytest.raises(ValueError, match="boolean"):
        read_spec(body)


# ------------------------------------------------------------------- the engine --


def _taste_panel(
    seed: int, n: int, m: int, *, loadings: list[float] | None = None
) -> list[list[float | None]]:
    """Integer 1-10 ratings: a generosity habit, one shared taste with the given loadings
    (none: independent objects), and noise."""
    rng = random.Random(seed)
    load = loadings or [0.0] * m
    rows: list[list[float | None]] = []
    for _ in range(n):
        g = rng.gauss(0.0, 1.2)
        f = rng.gauss(0.0, 1.0)
        rows.append(
            [
                float(min(10, max(1, round(5.5 + g + 2.0 * load[j] * f + rng.gauss(0.0, 1.5)))))
                for j in range(m)
            ]
        )
    return rows


def _inputs(
    rows: list[list[float | None]],
    *,
    family: int | None = None,
    scales: list[tuple[float, float]] | None = None,
    weights: list[float] | None = None,
) -> ObjectMapInputs:
    p = len(rows[0])
    k = p if family is None else family
    ends = scales or [(1.0, 10.0)] * p
    return ObjectMapInputs(
        respondent_ids=tuple(f"R{i}" for i in range(len(rows))),
        donor_ids=tuple(f"D{i // 2}" for i in range(len(rows))),
        items=tuple(
            RatingItem(item_id=f"i{j}", scale_min=ends[j][0], scale_max=ends[j][1])
            for j in range(p)
        ),
        values=tuple(tuple(r) for r in rows),
        weights=tuple(weights or [1.0] * len(rows)),
        object_ids=tuple(f"o{j}" for j in range(k)),
        object_items=tuple(f"i{j}" for j in range(k)),
        roles={f"o{j}": ObjectRole.PRIMARY.value for j in range(k)},
    )


def _components(inputs: ObjectMapInputs) -> tuple[Any, Any, list[int]]:
    """F1 then F2 by hand, the family's columns, and their pair relations."""
    scaled = [
        [
            None if v is None else (v - it.scale_min) / (it.scale_max - it.scale_min)
            for v, it in zip(row, inputs.items, strict=True)
        ]
        for row in inputs.values
    ]
    person = person_minmax(scaled)
    columns = list(inputs.object_columns())
    family = [[row[c] for c in columns] for row in person.values]
    pairs = derive_pair_relations(family, list(inputs.weights), n_min=30, confidence=0.95)
    return person, pairs, columns


def test_every_number_is_the_landed_functions_on_the_same_input() -> None:
    rows = _taste_panel(7, 400, 8, loadings=[0.9, 0.8, 0.7, 0.0, -0.6, -0.8, 0.3, 0.1])
    inputs = _inputs(rows, family=6)  # two items rated, not mapped: they enter F2 only
    art = compute_object_map(inputs, AIA_SOCIOMAP_V2, connectedness_interval=False)
    person, pairs, _ = _components(inputs)

    assert art.outcome == MapOutcome.MAPPED
    assert art.relations == pairs
    assert art.abs_r == tuple(tuple(None if v is None else abs(v) for v in r) for r in pairs.r)
    known = [
        [i != j and pairs.status[i][j] in (PairStatus.RELIABLE, PairStatus.WEAK) for j in range(6)]
        for i in range(6)
    ]
    fit = fit_smacof_objects(
        correlation_distances(pairs.r, known), max_iterations=5000, tolerance=1e-12
    )
    assert art.layout is not None
    assert art.layout.points == fit.points
    assert art.layout.stress_1 == fit.stress_1
    assert art.layout.quality == stress_quality(fit.stress_1).value
    assert art.layout.extent == 2.0
    scores = primary_scores(
        list(inputs.object_ids), pairs.r, pairs.status, dict(inputs.roles)
    ).to_payload()
    assert art.scores == scores
    assert set(art.not_placed) == {inputs.respondent_ids[k] for k in person.excluded}
    assert art.respondents.status == art.terrain.status == "not_computed"
    assert art.connectedness_100 == CONNECTEDNESS_OFF


def test_the_rating_habit_is_removed_through_the_engine() -> None:
    """Audit F2 [C1]: six independent objects; raw mean r ~ +0.39, the engine's ~ -0.09."""
    rows = _taste_panel(1, 3000, 6)
    art = compute_object_map(_inputs(rows), AIA_SOCIOMAP_V2, connectedness_interval=False)
    m = len(art.object_ids)
    values = [art.relations.r[i][j] for i in range(m) for j in range(i + 1, m)]
    assert statistics.fmean(v for v in values if v is not None) == pytest.approx(-0.09, abs=0.01)
    # Independent objects: no structure, and the map says so instead of stretching it.
    assert art.layout is not None and art.layout.quality == "unreliable"
    assert max(math.hypot(x, y) for x, y in art.layout.points) < 1.1


def test_the_ruler_is_fixed_a_weak_family_is_drawn_small() -> None:
    weak = compute_object_map(
        _inputs(_taste_panel(3, 600, 8)), AIA_SOCIOMAP_V2, connectedness_interval=False
    )
    strong = compute_object_map(
        _inputs(_taste_panel(3, 600, 8, loadings=[1.0, 0.9, 0.8, -0.8, -0.9, -1.0, 0.5, -0.5])),
        AIA_SOCIOMAP_V2,
        connectedness_interval=False,
    )
    assert weak.layout is not None and strong.layout is not None
    assert strong.layout.stress_1 < weak.layout.stress_1

    def spread(art: SociomapArtifactV3) -> float:
        assert art.layout is not None
        return max(math.hypot(x, y) for x, y in art.layout.points)

    assert spread(strong) > spread(weak)


def test_a_straight_liner_is_not_placed_but_their_ratings_count_in_the_heights() -> None:
    rows = _taste_panel(5, 200, 5, loadings=[0.9, 0.8, -0.7, 0.6, 0.0])
    rows.append([7.0] * 5)
    art = compute_object_map(_inputs(rows), AIA_SOCIOMAP_V2, connectedness_interval=False)
    assert art.not_placed == {"R200": NOT_PLACED_NO_SPREAD}
    assert art.heights.support_n == (201,) * 5
    expected = statistics.fmean((r[0] - 1.0) / 9.0 for r in rows if r[0] is not None)
    assert art.heights.values[0] == pytest.approx(expected, abs=1e-12)


def test_too_few_objects_is_not_mappable() -> None:
    art = compute_object_map(
        _inputs(_taste_panel(2, 200, 4), family=2), AIA_SOCIOMAP_V2, connectedness_interval=False
    )
    assert art.outcome == MapOutcome.NOT_MAPPABLE and art.layout is None
    assert art.not_mappable is not None
    assert art.not_mappable.reason == NotMappableReason.TOO_FEW_OBJECTS


def test_a_sample_below_n_min_is_not_mappable_however_large_its_numbers() -> None:
    rows = _taste_panel(4, 25, 5, loadings=[1.0, 1.0, 1.0, 1.0, 1.0])
    art = compute_object_map(_inputs(rows), AIA_SOCIOMAP_V2, connectedness_interval=False)
    assert art.not_mappable is not None
    assert art.not_mappable.reason == NotMappableReason.NO_KNOWN_PAIR
    assert art.status_counts == {"unknown": 10, "reliable": 0, "weak": 0}


def test_an_object_too_few_rated_is_named_and_the_family_is_not_stretched_around_it() -> None:
    rows = _taste_panel(6, 300, 5, loadings=[0.9, 0.8, 0.7, -0.6, 0.5])
    for k in range(20, 300):
        rows[k][4] = None  # only twenty respondents rated the fifth object
    art = compute_object_map(_inputs(rows), AIA_SOCIOMAP_V2, connectedness_interval=False)
    assert art.not_mappable is not None
    assert art.not_mappable.reason == NotMappableReason.DISCONNECTED
    assert art.not_mappable.objects == ("o4",)


def test_a_rating_off_its_declared_scale_is_refused() -> None:
    rows = _taste_panel(8, 50, 4)
    rows[0][0] = 11.0
    with pytest.raises(ValueError, match="outside its declared scale"):
        compute_object_map(_inputs(rows), AIA_SOCIOMAP_V2, connectedness_interval=False)


def test_items_with_different_ends_compare_on_their_own_scales() -> None:
    """F1: an item on 1-5 and one on 1-10 are each put on 0-1 by their declared ends."""
    rows: list[list[float | None]] = [
        [1.0, 1.0, 5.0],
        [5.0, 10.0, 1.0],
        [3.0, 5.5, 3.0],
    ]
    inputs = _inputs(rows, scales=[(1.0, 5.0), (1.0, 10.0), (1.0, 5.0)])
    art = compute_object_map(inputs, AIA_SOCIOMAP_V2, connectedness_interval=False)
    assert art.heights.values == pytest.approx((0.5, 0.5, 0.5))


def test_the_bootstrap_runs_only_when_asked_and_is_4as() -> None:
    rows = _taste_panel(9, 120, 5, loadings=[0.9, 0.8, -0.7, 0.6, 0.2])
    small = _v2_with(
        connectedness=AIA_SOCIOMAP_V2.connectedness.model_copy(update={"resamples": 40})
    )
    inputs = _inputs(rows)
    art = compute_object_map(inputs, small, connectedness_interval=True)
    _, _pairs, columns = _components(inputs)
    scaled_family = [
        [None if v is None else (v - 1.0) / 9.0 for v in [row[c] for c in columns]] for row in rows
    ]
    family = [[row[c] for c in columns] for row in person_minmax(scaled_family).values]

    def correlate(mult: Any) -> Any:
        drawn = derive_pair_relations(family, [float(k) for k in mult], n_min=30, confidence=0.95)
        return drawn.r, drawn.status

    direct = connectedness_100(
        list(inputs.object_ids),
        dict(inputs.roles),
        correlate,
        respondents=len(rows),
        resamples=40,
        seed=small.connectedness.seed,
    ).to_payload()
    assert art.connectedness_100["status"] == "computed"
    assert {k: v for k, v in art.connectedness_100.items() if k not in ("status", "ranking")} == (
        direct
    )


# ----------------------------------------------------------------- the artifact --


def test_the_artifact_round_trips_and_an_edit_is_refused() -> None:
    art = compute_object_map(
        _inputs(_taste_panel(10, 150, 5, loadings=[0.9, 0.8, 0.7, -0.6, 0.5])),
        AIA_SOCIOMAP_V2,
        connectedness_interval=False,
    )
    payload = art.to_payload()
    assert read_artifact(payload) == art
    assert SociomapArtifactV3.from_payload(payload) == art
    edited = {**payload, "artifact": {**payload["artifact"], "outcome": "NOT_MAPPABLE"}}
    with pytest.raises((ArtifactIntegrityError, ValueError)):
        read_artifact(edited)
    moved = {
        **payload,
        "artifact": {
            **payload["artifact"],
            "heights": {**payload["artifact"]["heights"], "support_n": [1] * 5},
        },
    }
    with pytest.raises(ArtifactIntegrityError):
        read_artifact(moved)


def test_a_contract_2_artifact_reads_as_it_always_did() -> None:
    from aia_core.domain.sociomap import compute_sociomap
    from aia_core.domain.sociomap.models import RatingsMatrix, SociomapInputs

    rows = _taste_panel(11, 30, 4, loadings=[0.9, 0.8, -0.7, 0.6])
    art = compute_sociomap(
        SociomapInputs(
            ratings=RatingsMatrix(
                respondent_ids=tuple(f"R{i}" for i in range(30)),
                object_ids=("a", "b", "c", "d"),
                values=tuple(tuple(r) for r in rows),
            ),
            object_relation=None,
        ),
        AIA_SOCIOMAP_V1.model_copy(
            update={
                "relation": None,
                "metrics": AIA_SOCIOMAP_V1.metrics.model_copy(
                    update={
                        "object_height_metric": "mean_rating",
                        "object_colour_metric": "mean_rating",
                    }
                ),
            }
        ),
    )
    assert read_artifact(art.to_payload()) == art
    with pytest.raises(ArtifactIntegrityError, match="contract"):
        read_artifact({"artifact": {**art.to_payload()["artifact"], "contract_version": "9"}})


# ------------------------------------------------------------- the research body --


def _battery(bid: str, labels: list[str], scale: tuple[int, int]) -> SpecBattery:
    return SpecBattery(
        id=bid,
        title=bid,
        family="f",
        question_template="{object}",
        scale=scale,
        scale_labels=("low", "high"),
        objects=tuple(SpecObject(id=f"{bid}{i}", label=label) for i, label in enumerate(labels)),
        familiarity_required=False,
        output_type="sociomap",
    )


class _Respondent:
    def __init__(self, rid: str, answers: dict[str, int], weight: float = 1.0) -> None:
        self.respondent_id, self.answers, self.weight = rid, answers, weight
        self.donor_id = f"D-{rid}"


class _Dataset:
    def __init__(self, respondents: list[_Respondent]) -> None:
        self.respondents = respondents
        self.origin = None


def _study(seed: int, n: int) -> tuple[SpecBattery, SpecBattery, _Dataset]:
    a = _battery("A", ["Káva", "Čaj", "Kakao", "Džus", "Voda"], (1, 10))
    b = _battery("B", ["Ráno", "Večer", "Víkend"], (1, 5))
    rng = random.Random(seed)
    people = []
    for k in range(n):
        g, f = rng.gauss(0, 1.0), rng.gauss(0, 1.0)
        answers = {
            a.question_id(o): int(min(10, max(1, round(5.5 + g + 2 * w * f + rng.gauss(0, 1.5)))))
            for o, w in zip(a.objects, [0.9, 0.7, -0.6, 0.5, 0.0], strict=True)
        }
        answers |= {
            b.question_id(o): int(min(5, max(1, round(3 + g / 2 + rng.gauss(0, 1.0)))))
            for o in b.objects
        }
        people.append(_Respondent(f"P{k}", answers, weight=0.5 + rng.random()))
    return a, b, _Dataset(people)


def test_a_new_run_pins_both_methods() -> None:
    ids = [m.method_id for m in default_methods()]
    assert ids == ["aia-sociomap-1", "aia-sociomap-2"]


def test_the_research_body_stores_the_object_map_beside_the_v1_map() -> None:
    a, b, data = _study(12, 240)
    body = battery_sociomap(
        a,
        data,  # type: ignore[arg-type]
        rated_with=(a, b),
        connectedness_interval=False,
        map_spec=AIA_SOCIOMAP_V1,
        object_maps=(AIA_SOCIOMAP_V2,),
    )
    assert body["sociomap"]["kind"] == "sociomap" and body["sociomap"]["contract_version"] == "2"
    art = read_artifact(body["maps"]["aia-sociomap-2"])
    assert isinstance(art, SociomapArtifactV3)
    # The object map's relations and scores are the body's own over each person's scale.
    assert [list(r) for r in art.relations.r] == body["relation_rescaled"]["r"]
    assert art.scores == body["object_scores"]
    assert art.object_items == tuple(a.question_id(o) for o in a.objects)
    assert {i.item_id for i in art.items} == {x.question_id(o) for x in (a, b) for o in x.objects}


def test_the_object_map_reads_every_set_the_specification_rates() -> None:
    a, b, data = _study(13, 240)
    alone = object_map_inputs(a, data, (a,), [1.0] * 240)  # type: ignore[arg-type]
    both = object_map_inputs(a, data, (a, b), [1.0] * 240)  # type: ignore[arg-type]
    assert len(alone.items) == 5 and len(both.items) == 8
    one = compute_object_map(alone, AIA_SOCIOMAP_V2, connectedness_interval=False)
    two = compute_object_map(both, AIA_SOCIOMAP_V2, connectedness_interval=False)
    assert one.relations.r != two.relations.r  # F2: the other set moves each person's ends


def test_with_the_switch_on_the_bootstrap_is_paid_once_and_matches() -> None:
    a, b, data = _study(14, 150)
    on = battery_sociomap(
        a,
        data,  # type: ignore[arg-type]
        rated_with=(a, b),
        connectedness_interval=True,
        map_spec=AIA_SOCIOMAP_V1,
        object_maps=(AIA_SOCIOMAP_V2,),
    )
    alone = battery_sociomap(
        a,
        data,  # type: ignore[arg-type]
        rated_with=(a, b),
        connectedness_interval=True,
        map_spec=AIA_SOCIOMAP_V1,
        object_maps=(),
    )
    art = read_artifact(on["maps"]["aia-sociomap-2"])
    assert isinstance(art, SociomapArtifactV3)
    assert art.spec.connectedness.resamples == CONNECTEDNESS_RESAMPLES
    assert art.spec.connectedness.seed == CONNECTEDNESS_SEED
    assert on["connectedness_100"] == alone["connectedness_100"] == art.connectedness_100


def test_research_sociomaps_names_both_pinned_methods() -> None:
    from aia_core.domain.research_design import compile_design

    spec, problems = compile_design(
        {
            "n": 60,
            "sections": [
                {
                    "type": "object_battery",
                    "object_family": "značky",
                    "objects": ["A", "B", "C", "D"],
                    "scale": [1, 10],
                }
            ],
        }
    )
    assert spec is not None, problems
    (battery,) = spec.batteries
    rng = random.Random(15)
    data = _Dataset(
        [
            _Respondent(
                f"P{k}",
                {battery.question_id(o): rng.randint(1, 10) for o in battery.objects},
            )
            for k in range(60)
        ]
    )
    body = research_sociomaps(
        spec,
        data,  # type: ignore[arg-type]
        methods=default_methods(),
        connectedness_interval=False,
    )
    assert [m["method_id"] for m in body["methods"]] == ["aia-sociomap-1", "aia-sociomap-2"]
    (set_body,) = body["batteries"]
    assert set(set_body["maps"]) == {"aia-sociomap-2"}
    assert body["sociomap_version"] == "aia-research-sociomap-7"
    pins = {m.method_id: m for m in default_methods()}
    assert pins["aia-sociomap-2"] == SociomapMethod.of(AIA_SOCIOMAP_V2)


def test_the_map_says_what_it_rests_on_and_how_weights_entered_it() -> None:
    rows = _taste_panel(16, 100, 5, loadings=[0.9, 0.8, -0.7, 0.6, 0.3])
    rows.append([4.0] * 5)
    weights = [1.0 + (k % 3) for k in range(101)]
    art = compute_object_map(
        _inputs(rows, weights=weights), AIA_SOCIOMAP_V2, connectedness_interval=False
    )
    support = art.support
    assert (support.respondents, support.placed, support.not_placed) == (101, 100, 1)
    placed = weights[:100]
    assert support.effective_n == pytest.approx(sum(placed) ** 2 / sum(w * w for w in placed))
    assert support.effective_n < 100  # unequal weights are worth fewer than their count
    assert support.donors == 50  # two respondents per fictional donor; R100 is not placed
    assert "not the weight" in support.weighting and "donors" in support.weighting
