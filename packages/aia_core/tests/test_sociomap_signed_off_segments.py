"""The signed-off methodology's taste segments, number for number against its code.

``fixtures/sociomap/aia/signed_off_tastes.json`` holds eleven studies -- clear segments (300
respondents, 12 objects), none, a borderline near-tie, too few respondents (25), four objects
(too few for slopes and for jittered maps), a step-down (3,000 respondents, 24 objects, the
fit's four segments shown as three), a shown map rejected by the shuffle guard (with and
without the other maps), segments not stable across the maps, segments shown only by the other
maps (fitted on the shown map with their most common number), and a borderline decision no map
votes for (the likely split from the shown map's criterion) -- with their ratings (1-10), the
shown map's positions, the other maps (the four near-identical maps of jittered ratings, or
maps given to reach a branch), and what the methodology's own code
(``find_segments_consensus``, ``segment_profiles``) computes from them with the AIA panel's
caller rules, produced outside this repository under numpy 2.5 / numba 0.68. The maps are the
fixture's, not BB1's (BB1 differs between platforms), so the decision is checked exactly. The
fixture also holds the first noise values of each jittered map, which pin the jitter's stream.

The mixture's EM loop is compiled; on macOS arm64 the port gives the methodology's numbers bit
for bit (the same kernel, the same flags). The tolerance (1e-9 relative, 1e-12 absolute) only
leaves room for a last-bit difference of the compiled loop on another platform: every decision,
label, share, colour, vote and named object is compared exactly.
"""

from __future__ import annotations

import inspect
import json
import sys
from collections.abc import Callable, Iterable, Iterator
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from aia_core.domain.pipeline import fingerprint
from aia_core.domain.sociomap import engine_v2, signed_off_segments
from aia_core.domain.sociomap.engine_v2 import _prepare, _signed_off_layout, compute_object_map
from aia_core.domain.sociomap.metrics import ObjectRole
from aia_core.domain.sociomap.models_v3 import (
    ObjectMapInputs,
    ObjectMapLayout,
    RatingItem,
    RespondentMap,
    SociomapArtifactV3,
    TasteSegments,
)
from aia_core.domain.sociomap.signed_off_respondents import PLACED, place_respondents
from aia_core.domain.sociomap.signed_off_segments import (
    SHUFFLE_BATCH,
    Segments,
    Split,
    consensus_state,
    jittered_ratings,
    map_decision,
    segment_profiles,
    taste_segments,
)
from aia_core.domain.sociomap.specification import (
    AIA_SOCIOMAP_V2,
    AIA_SOCIOMAP_V3,
    AIA_SOCIOMAP_V4,
    AIA_SOCIOMAP_V5,
    SociomapSpecV3,
    TasteSegmentsSpec,
    UnsupportedMethodology,
    require_supported,
    spec_payload,
)

FIXTURE = json.loads(
    (Path(__file__).parent / "fixtures/sociomap/aia/signed_off_tastes.json").read_text("utf-8")
)
STUDIES = {study["name"]: study for study in FIXTURE["studies"]}
RULES = AIA_SOCIOMAP_V5.segments
RESPONDENT_MAP = AIA_SOCIOMAP_V5.respondent_map
assert RULES is not None and RESPONDENT_MAP is not None
RTOL, ATOL = 1e-9, 1e-12
#: The methodology's statements, as the decision and reason the map stores.
STATEMENTS = {
    "Too few respondents to look for taste segments": ("NONE", "TOO_FEW_RESPONDENTS"),
    "No clear taste segments": ("NONE", "NO_CLEAR_SEGMENTS"),
    "No clear taste segments (no stronger than in shuffled ratings)": (
        "NONE",
        "NOT_ABOVE_SHUFFLED",
    ),
    "No clear taste segments (not stable across map variants)": ("NONE", "NOT_STABLE"),
}


def _raw(name: str) -> Any:
    return np.array(
        [[np.nan if v is None else v for v in row] for row in STUDIES[name]["ratings"]],
        dtype=float,
    )


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


def _on_0_1(name: str) -> Any:
    # The engine's own scaling onto each item's declared 0-1 scale.
    return np.array(
        [[np.nan if v is None else v for v in row] for row in engine_v2._scaled(_inputs(name))],
        dtype=float,
    )


def _placed(points: Any, ratings: Any) -> Any:
    assert RESPONDENT_MAP is not None
    status = place_respondents(
        points,
        ratings,
        chance_level=RESPONDENT_MAP.chance_level,
        min_ratings=RESPONDENT_MAP.min_ratings,
    ).status
    return np.array([s == PLACED for s in status], dtype=bool)


def _segments(name: str, rules: TasteSegmentsSpec | None = RULES) -> Segments:
    assert rules is not None
    study = STUDIES[name]
    ruler = np.array(study["ruler"], dtype=float)
    ratings = _on_0_1(name)
    others = [np.array(m, dtype=float) for m in study["alt_maps"]]
    return taste_segments(ruler, others, ratings, _placed(ruler, ratings), rules)


def _close(port: Any, expected: Any) -> None:
    np.testing.assert_allclose(
        np.asarray(port, dtype=float),
        np.array(expected, dtype=float),
        rtol=RTOL,
        atol=ATOL,
        equal_nan=True,
    )


def _check_split(split: Split, expected: dict[str, Any], name: str) -> None:
    assert split.k == expected["k"]
    assert split.labels.tolist() == expected["labels"]
    assert split.shares == expected["share"]
    assert split.coloured.tolist() == expected["confident"]
    assert split.distinct is expected["distinct"]
    _close(split.membership, [np.nan if v is None else v for v in expected["prob"]])
    _close(split.post, [[np.nan if v is None else v for v in row] for row in expected["post"]])
    _close(split.separation, expected["separation"])
    profiles = segment_profiles(
        _raw(name),
        split,
        false_discovery_rate=RULES.profile_false_discovery_rate,
        top=RULES.profile_top,
    )
    want = expected["profiles"]
    _close(profiles.difference, want["diff"])
    _close(profiles.standard_error, want["se"])
    _close(profiles.p_value, want["p"])
    assert profiles.distinctive.tolist() == want["distinctive"]
    assert [[f"o{j}" for j in g] for g in profiles.likes] == want["likes"]
    assert [[f"o{j}" for j in g] for g in profiles.dislikes] == want["dislikes"]


@pytest.mark.parametrize("name", sorted(STUDIES))
def test_the_segments_match_the_methodologys_own_code(name: str) -> None:
    study, found = STUDIES[name], _segments(name)
    shown = study["segments"]
    if study["borderline"]:
        assert (found.decision, found.reason) == ("BORDERLINE", None)
    elif shown["k"] >= 2:
        assert (found.decision, found.reason) == ("SEGMENTS", None)
    else:
        assert (found.decision, found.reason) == STATEMENTS[shown["statement"]]
    assert found.k_fit == study["k_fit"]
    _close(found.gain, study["gain"])
    if study["null_gain_max"] is None:
        assert found.null_gain_max is None
    else:
        _close(found.null_gain_max, study["null_gain_max"])
    # Rounded to two decimals by the methodology itself: equal as stored.
    assert found.margins == (None if study["margins"] is None else tuple(study["margins"]))
    if study["mean_margin"] is None:
        assert found.mean_margin is None
    else:
        _close(found.mean_margin, study["mean_margin"])
    assert (found.votes, found.maps) == (study["votes"], study["maps"])
    if found.split is None:
        assert shown["k"] == 0 and not shown["share"]
        assert all(label == -1 for label in shown["labels"])
    else:
        _check_split(found.split, shown, name)
    if found.hint is None:
        assert study["k_hint"] is None and "hint" not in study
    else:
        assert found.hint.k == study["k_hint"]
        _check_split(found.hint, study["hint"], name)


def test_the_studies_cover_the_decisions() -> None:
    decided = {name: _segments(name) for name in ("clear", "none", "borderline")}
    assert decided["clear"].decision == "SEGMENTS" and decided["clear"].split is not None
    assert decided["none"].reason == "NO_CLEAR_SEGMENTS"
    assert decided["borderline"].decision == "BORDERLINE"
    # The step-down: the fit chose four segments, three are shown.
    assert STUDIES["step_down"]["k_fit"] == 4 and STUDIES["step_down"]["segments"]["k"] == 3
    # Too few respondents with a slope, with and without jittered maps.
    assert len(STUDIES["few"]["ratings"]) < RULES.min_respondents and STUDIES["few"]["maps"]
    assert len(STUDIES["four_objects"]["ruler"]) < RULES.consensus_min_objects
    assert not STUDIES["four_objects"]["alt_maps"]
    # Some respondents of the clear study are labelled but grey: their membership is high,
    # but they are not clearly placed.
    split = decided["clear"].split
    ruler = np.array(STUDIES["clear"]["ruler"], dtype=float)
    placed = _placed(ruler, _on_0_1("clear"))
    assert split is not None and (split.labels >= 0).all()
    assert ((split.membership >= RULES.colour_membership) & ~placed).any()
    assert not (split.coloured & ~placed).any()
    # The branches the other studies reach.
    guarded = STUDIES["shuffle_guard_shown_only"]
    assert guarded["null_gain_max"] > guarded["gain"] > 0 and not guarded["alt_maps"]
    assert STATEMENTS[guarded["segments"]["statement"]][1] == "NOT_ABOVE_SHUFFLED"
    assert STUDIES["shuffle_guard"]["borderline"] and STUDIES["shuffle_guard"]["votes"] == 1
    unstable = STUDIES["not_stable"]
    assert STATEMENTS[unstable["segments"]["statement"]][1] == "NOT_STABLE"
    assert unstable["margins"][0] < 0 and unstable["mean_margin"] > RULES.borderline_margin
    variants = STUDIES["from_variants"]
    assert variants["margins"][0] > 0 and variants["segments"]["k"] == variants["k_fit"] == 2
    hinted = STUDIES["hint_from_criterion"]
    assert hinted["borderline"] and hinted["votes"] == 0 and hinted["k_hint"] == 2


def test_the_jittered_ratings_draw_the_methodologys_stream() -> None:
    # Each near-identical map's noise, independent of the layout: its first 2 x 3 values.
    copies = jittered_ratings(
        np.zeros((2, 3)), copies=len(FIXTURE["jitter_head"]), jitter=1e-9, seed=0
    )
    for copy, head in zip(copies, FIXTURE["jitter_head"], strict=True):
        np.testing.assert_array_equal(copy, np.array(head))


def test_segments_shown_only_by_the_other_maps_take_their_most_common_number() -> None:
    # The shown map of from_variants shows none; of the other maps, the clear study's shown map
    # shows three segments and three of from_variants' own maps two each: fitted with two.
    study = STUDIES["from_variants"]
    ruler = np.array(study["ruler"], dtype=float)
    others = [np.array(STUDIES["clear"]["ruler"], dtype=float)] + [
        np.array(m, dtype=float) for m in study["alt_maps"][:3]
    ]
    ratings = _on_0_1("from_variants")
    assert [map_decision(m, ratings, RULES).k for m in others] == [3, 2, 2, 2]
    found = taste_segments(ruler, others, ratings, _placed(ruler, ratings), RULES)
    assert found.decision == "SEGMENTS" and found.votes == 4
    assert found.split is not None and found.split.k == found.k_fit == 2


def test_the_maps_decide_together_within_the_band() -> None:
    band = RULES.borderline_margin
    margins = np.array
    # Clearly favoured by the mean margin and shown on at least half the maps.
    assert consensus_state(margins([-5.0, -4.5, -6.0]), [2, 2, 0], band) == "SEGMENTS"
    assert consensus_state(margins([-5.0, -4.5, -6.0]), [2, 0, 0], band) == "BORDERLINE"
    # Clearly against, or no map shows segments and the mean leans against.
    assert consensus_state(margins([5.0, 4.5, 6.0]), [2, 2, 2], band) == "NONE"
    assert consensus_state(margins([0.5, 1.0, -0.2]), [0, 0, 0], band) == "NONE"
    assert consensus_state(margins([0.5, 1.0, -0.2]), [0, 2, 0], band) == "BORDERLINE"
    assert consensus_state(margins([-0.5, -1.0, 0.2]), [0, 0, 0], band) == "BORDERLINE"
    # A map with too few respondents has no margin; with none at all, there are no segments.
    assert consensus_state(margins([np.nan, -6.0]), [0, 2], band) == "SEGMENTS"
    assert consensus_state(margins([np.nan, np.nan]), [0, 0], band) == "NONE"


def _jittered_maps(name: str, spec: SociomapSpecV3) -> list[Any]:
    """The jittered maps the engine lays out, made here from the same ported pieces."""
    assert spec.segments is not None
    inputs = _inputs(name)
    maps = []
    for copy in jittered_ratings(
        _raw(name),
        copies=spec.segments.consensus_maps - 1,
        jitter=spec.segments.jitter,
        seed=spec.segments.seed,
    ):
        layout = _signed_off_layout(_prepare(copy, spec), inputs.object_ids, spec)
        assert isinstance(layout, ObjectMapLayout)
        maps.append(np.array(layout.points, dtype=float))
    return maps


def _stored(artifact: SociomapArtifactV3) -> TasteSegments:
    assert isinstance(artifact.respondents, RespondentMap)
    assert artifact.respondents.segments is not None
    return artifact.respondents.segments


def test_the_object_map_stores_the_segments_under_aia_sociomap_5() -> None:
    artifact = compute_object_map(_inputs("clear"), AIA_SOCIOMAP_V5, connectedness_interval=False)
    layout, respondents = artifact.layout, artifact.respondents
    assert layout is not None and isinstance(respondents, RespondentMap)
    stored = _stored(artifact)
    # The positions are BB1's on this machine: the stored segments are checked against the
    # ported functions on its own layout and jittered maps, not against the fixture.
    ruler = np.array(layout.points, dtype=float)
    ratings = _on_0_1("clear")
    placed = np.array([s == PLACED for s in respondents.placement], dtype=bool)
    found = taste_segments(ruler, _jittered_maps("clear", AIA_SOCIOMAP_V5), ratings, placed, RULES)
    assert found.split is not None and stored.decision == "SEGMENTS" and stored.reason is None
    assert stored.k == found.split.k and stored.k_fit == found.k_fit
    assert (stored.gain, stored.null_gain_max) == (found.gain, found.null_gain_max)
    assert (stored.margins, stored.mean_margin) == (found.margins, found.mean_margin)
    assert (stored.votes, stored.maps) == (found.votes, found.maps) == (5, 5)
    assert stored.shares == tuple(found.split.shares)
    assert stored.separation == found.split.separation
    assert stored.distinct is found.split.distinct
    assert stored.label == tuple(found.split.labels.tolist())
    assert stored.membership == tuple(round(float(v), 5) for v in found.split.membership)
    assert stored.coloured == tuple(found.split.coloured.tolist())
    # Only clearly placed respondents are coloured.
    assert all(
        status == PLACED
        for status, coloured in zip(respondents.placement, stored.coloured, strict=True)
        if coloured
    )
    profiles = segment_profiles(
        _raw("clear"),
        found.split,
        false_discovery_rate=RULES.profile_false_discovery_rate,
        top=RULES.profile_top,
    )
    for g, profile in enumerate(stored.profiles):
        assert profile.likes == tuple(f"o{j}" for j in profiles.likes[g])
        assert profile.dislikes == tuple(f"o{j}" for j in profiles.dislikes[g])
        assert profile.difference == tuple(profiles.difference[g].tolist())
        assert profile.p_value == tuple(profiles.p_value[g].tolist())
    assert stored.hint is None
    body = artifact.model_dump(mode="json")
    assert set(body["respondents"]["segments"]) == {
        "decision",
        "reason",
        "k",
        "k_fit",
        "gain",
        "null_gain_max",
        "margins",
        "mean_margin",
        "votes",
        "maps",
        "shares",
        "separation",
        "distinct",
        "profiles",
        "label",
        "membership",
        "coloured",
        "hint",
    }
    assert body["spec"]["segments"] == RULES.model_dump(mode="json")
    assert SociomapArtifactV3.from_payload(artifact.to_payload()) == artifact


def test_without_segments_nobody_is_labelled() -> None:
    artifact = compute_object_map(_inputs("none"), AIA_SOCIOMAP_V5, connectedness_interval=False)
    stored = _stored(artifact)
    assert (stored.decision, stored.reason, stored.k) == ("NONE", "NO_CLEAR_SEGMENTS", 0)
    assert stored.label is None and stored.membership is None and stored.coloured is None
    assert stored.shares == () and stored.profiles == () and stored.hint is None
    assert SociomapArtifactV3.from_payload(artifact.to_payload()) == artifact


def _counting_layouts(monkeypatch: pytest.MonkeyPatch) -> list[int]:
    calls: list[int] = []
    layout = engine_v2._signed_off_layout

    def counted(*args: Any, **kwargs: Any) -> Any:
        calls.append(1)
        return layout(*args, **kwargs)

    monkeypatch.setattr(engine_v2, "_signed_off_layout", counted)
    return calls


def test_a_set_below_the_consensus_minimum_makes_no_jittered_maps(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = _counting_layouts(monkeypatch)
    artifact = compute_object_map(
        _inputs("four_objects"), AIA_SOCIOMAP_V5, connectedness_interval=False
    )
    # The shown map only: four objects are below the five the near-identical maps need.
    assert len(calls) == 1
    stored = _stored(artifact)
    assert stored.margins is None and stored.votes is None and stored.maps is None
    assert stored.reason == "TOO_FEW_RESPONDENTS"


def test_earlier_presets_store_exactly_what_they_stored() -> None:
    # The specs and the maps every earlier preset has stored, byte for byte.
    for spec, expected in (
        (AIA_SOCIOMAP_V2, "3f1c01221492f883ce715b5763a3815ae2a8f4c1e5456f3c581a9f67838d6b43"),
        (AIA_SOCIOMAP_V3, "e16dc0d0636109322900ab56ed9613e6b2d4f6e65f2dd7e26b9ada059b7cf241"),
        (AIA_SOCIOMAP_V4, "9aae1e1ca107626be07f873afe39d6d010e43b6ee93b9c9593cb3fe8f03bc4b4"),
    ):
        assert spec.segments is None and "segments" not in spec_payload(spec)["spec"]
        assert spec.fingerprint() == expected
    # A computed map's last float digits differ between macOS and Linux (CI), so each
    # platform pins what develop's own code stores there.
    maps = {
        "darwin": (
            (AIA_SOCIOMAP_V3, "cc70932a8128f9c379518c32863cca342d634be064e3f3a9a3ce36f70e2f7dc3"),
            (AIA_SOCIOMAP_V4, "61228f037e6f462219e4a50d8aaf50f4cac43b25d11c9f3ef7f8631ef3fa6745"),
        ),
        "linux": (
            (AIA_SOCIOMAP_V3, "bfe7d6b00e6cb8ce8cd8e02dbf6ea2525bd4ea572fd6372496740d672985f8ad"),
            (AIA_SOCIOMAP_V4, "10479eb63fb6699c7a06db0c8fb655b229160372ba680990815854592f54d225"),
        ),
    }
    assert sys.platform in maps, f"no stored maps pinned for {sys.platform}"
    for spec, expected in maps[sys.platform]:
        artifact = compute_object_map(_inputs("none"), spec, connectedness_interval=False)
        assert artifact.fingerprint() == expected
        assert fingerprint(artifact.model_dump(mode="json")) == expected


def _with(**update: Any) -> TasteSegmentsSpec:
    assert RULES is not None
    return RULES.model_copy(update=update)


def _spec(**update: Any) -> SociomapSpecV3:
    return AIA_SOCIOMAP_V5.model_copy(update={"segments": _with(**update)})


def test_the_segments_are_declared_exactly_under_the_signed_off_methodology() -> None:
    require_supported(AIA_SOCIOMAP_V5)
    for spec, field in (
        (AIA_SOCIOMAP_V5.model_copy(update={"segments": None}), "segments"),
        (AIA_SOCIOMAP_V4.model_copy(update={"segments": RULES}), "segments"),
        (_spec(max_segments=1), "segments.max_segments"),
        (_spec(min_respondents=3), "segments.min_respondents"),
        (_spec(min_ratings=3), "segments.min_ratings"),
        (_spec(penalty_factor=0.0), "segments.penalty_factor"),
        (_spec(shuffles=-1), "segments.shuffles"),
        (_spec(min_gain_share=1.5), "segments.min_gain_share"),
        (_spec(min_segment_share=-0.1), "segments.min_segment_share"),
        (_spec(min_separation=float("nan")), "segments.min_separation"),
        (_spec(colour_membership=0.0), "segments.colour_membership"),
        (_spec(distinct_separation=-1.0), "segments.distinct_separation"),
        (_spec(profile_false_discovery_rate=1.0), "segments.profile_false_discovery_rate"),
        (_spec(profile_top=0), "segments.profile_top"),
        (_spec(consensus_maps=0), "segments.consensus_maps"),
        (_spec(consensus_min_objects=0), "segments.consensus_min_objects"),
        (_spec(borderline_margin=float("inf")), "segments.borderline_margin"),
        (_spec(jitter=0.0), "segments.jitter"),
        (_spec(seed=-1), "segments.seed"),
    ):
        with pytest.raises(UnsupportedMethodology) as refused:
            require_supported(spec)
        assert field in refused.value.unsupported
    with pytest.raises(ValueError, match="boolean"):
        TasteSegmentsSpec.model_validate(RULES.model_dump() | {"shuffles": True})


def test_every_value_of_the_stage_changes_the_segments_when_edited() -> None:
    base = _segments("clear")
    assert base.split is not None and base.split.k == 3 and base.split.distinct
    assert base.null_gain_max == 0.0

    def k_of(found: Segments) -> int:
        return 0 if found.split is None else found.split.k

    assert k_of(_segments("clear", _with(max_segments=2))) == 2
    assert _segments("clear", _with(penalty_factor=1.0)).gain != base.gain
    assert _segments("clear", _with(shuffles=0)).null_gain_max is None
    assert _segments("clear", _with(min_respondents=301)).reason == "TOO_FEW_RESPONDENTS"
    # Every respondent of the clear study rated its twelve objects.
    assert _segments("clear", _with(min_ratings=13)).reason == "TOO_FEW_RESPONDENTS"
    assert k_of(_segments("clear", _with(min_gain_share=0.9))) == 2
    assert k_of(_segments("clear", _with(min_segment_share=0.34))) == 2
    # Stepped down only below the share: at exactly the smallest fitted share, kept.
    ruler = np.array(STUDIES["clear"]["ruler"], dtype=float)
    fitted = map_decision(ruler, _on_0_1("clear"), RULES).fitted
    assert fitted is not None
    smallest = float(fitted.fits[2].shares.min())
    assert k_of(_segments("clear", _with(min_segment_share=smallest))) == 3
    assert k_of(_segments("clear", _with(min_separation=4.0))) == 2
    fewer = _segments("clear", _with(colour_membership=0.99)).split
    assert fewer is not None and fewer.coloured.sum() < base.split.coloured.sum()
    overlapping = _segments("clear", _with(distinct_separation=4.0)).split
    assert overlapping is not None and not overlapping.distinct
    assert _segments("borderline").decision == "BORDERLINE"
    assert _segments("borderline", _with(borderline_margin=0.5)).decision == "NONE"

    # Through the object map: the profiles and the near-identical maps are the engine's.
    stored = _stored(
        compute_object_map(_inputs("clear"), AIA_SOCIOMAP_V5, connectedness_interval=False)
    )

    def edited(**update: Any) -> TasteSegments:
        return _stored(
            compute_object_map(_inputs("clear"), _spec(**update), connectedness_interval=False)
        )

    def distinctive(found: TasteSegments) -> int:
        return sum(sum(p.distinctive) for p in found.profiles)

    assert max(len(p.likes) for p in stored.profiles) == 3
    assert distinctive(edited(profile_false_discovery_rate=1e-12)) < distinctive(stored)
    assert max(len(p.likes) for p in edited(profile_top=1).profiles) == 1

    assert edited(consensus_maps=3).maps == 3 and stored.maps == 5
    assert edited(consensus_min_objects=13).maps is None
    assert edited(jitter=1e-3).mean_margin != stored.mean_margin
    assert edited(seed=1).mean_margin != stored.mean_margin


class _OneAtATime:
    """A stand-in for the thread pool that fits every shuffle on the calling thread, in
    order."""

    def __init__(self, workers: int) -> None:
        self.workers = workers

    def __enter__(self) -> _OneAtATime:
        return self

    def __exit__(self, *exc: object) -> None:
        return None

    def map(self, fn: Callable[[Any], Any], items: Iterable[Any]) -> Iterator[Any]:
        return iter([fn(item) for item in items])


def test_the_threads_never_change_a_stored_value(monkeypatch: pytest.MonkeyPatch) -> None:
    # The batch is the method's fixed size, never the machine's core count: the guard's
    # largest shuffled gain depends on it. The threads only fit a batch's shuffles at once.
    source = inspect.getsource(signed_off_segments)
    assert SHUFFLE_BATCH == 4 and "cpu_count" not in source
    threaded = {name: _segments(name) for name in ("clear", "borderline")}
    monkeypatch.setattr(signed_off_segments, "ThreadPoolExecutor", _OneAtATime)
    for name, found in threaded.items():
        alone = _segments(name)
        assert (alone.decision, alone.reason, alone.k_fit) == (
            found.decision,
            found.reason,
            found.k_fit,
        )
        assert (alone.gain, alone.null_gain_max) == (found.gain, found.null_gain_max)
        assert (alone.margins, alone.mean_margin) == (found.margins, found.mean_margin)
        assert (alone.votes, alone.maps) == (found.votes, found.maps)
        for a, b in ((alone.split, found.split), (alone.hint, found.hint)):
            assert (a is None) == (b is None)
            if a is not None and b is not None:
                assert a.labels.tolist() == b.labels.tolist() and a.shares == b.shares
                np.testing.assert_array_equal(a.post, b.post)
