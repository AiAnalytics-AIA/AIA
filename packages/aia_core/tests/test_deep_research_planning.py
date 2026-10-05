"""Planning: subjects from the design, tracks and their fingerprints, depth and stopping."""

from __future__ import annotations

import hashlib
import json
from typing import Any

import pytest

from aia_core.domain.deep_research.contracts import (
    HARNESS_VERSION,
    Channel,
    CoverageCell,
    DeepResearchRequest,
    FrozenKnowledge,
    KnowledgeSource,
    StopReason,
    SubjectKind,
    TrackStatus,
)
from aia_core.domain.deep_research.planning import (
    PRESETS,
    TrackInputs,
    UnknownPreset,
    allocate,
    brief_digest,
    build_tracks,
    check_plan_coverage,
    coverage_grid,
    extract_subjects,
    preset,
    screen_questions,
    stop_reason,
)
from aia_core.domain.residency import DataClass

DESIGN: dict[str, Any] = {
    "title": "Rostlinné nápoje",
    "goal": "Pochopit, proč lidé přecházejí na ovesné nápoje od značky Aroma",
    "decision_use": "Uvedení nové řady",
    "briefing": "Zajímá nás Česko.",
    "research_plan": {
        "research_questions": ["Proč lidé kupují rostlinné nápoje?", "Kdo je kupuje?", ""],
        "tracked_sets": [{"objects": ["Aroma", "Borealis", "aroma"]}],
    },
    "tracked_objects": ["Cedrus", 7],
    "sections": [
        {
            "id": "s1",
            "type": "questions",
            "questions": [
                {
                    "id": "q1",
                    "text": "Jak často kupujete rostlinné nápoje?",
                    "kategorie": ["Denně", "Nikdy"],
                },
                {"id": "q2", "text": "Souhlasíte?", "volby": ["Ano", "Ne"]},
                {"id": "q3", "text": ""},
            ],
        },
        {
            "id": "b1",
            "type": "object_battery",
            "object_question": "Jak hodnotíte značku {object}?",
            "objects": ["Aroma", "Dubina"],
        },
    ],
}


def _knowledge(*items: KnowledgeSource) -> FrozenKnowledge:
    return FrozenKnowledge(items=items, omitted_ids=(), retrieval_limit=200)


def _entity(title: str, revision: int = 1) -> KnowledgeSource:
    return KnowledgeSource(
        ref=f"KNW-00000000000{revision:03d}@{revision}",
        item_id=f"KNW-00000000000{revision:03d}",
        revision=revision,
        kind="ENTITY",
        title=title,
        text=title,
        data_class=DataClass.CLASS_B_DERIVED_CLIENT,
        lineage=(),
        truncated=False,
        public=False,
    )


def _request(
    design: dict[str, Any], knowledge: FrozenKnowledge | None = None, **fields: Any
) -> DeepResearchRequest:
    knowledge = knowledge or _knowledge()
    values: dict[str, Any] = {
        "harness_version": HARNESS_VERSION,
        "design_revision_id": "REV-1",
        "design_revision": 1,
        "preset": "QUICK",
        "channels": (Channel.INTERNAL, Channel.WEB),
        "brief": brief_digest(design),
        "subjects": extract_subjects(design, knowledge),
        "questionnaire": screen_questions(design),
        "knowledge": knowledge,
        "client_terms": (),
        **fields,
    }
    return DeepResearchRequest.model_validate(values)


INPUTS = TrackInputs(
    policy_version="test-v1",
    prompt_versions={Channel.WEB: "1", Channel.INTERNAL: "1"},
    web_retrieval={"search": "search-recorded", "mode": "RECORDED"},
)


# --------------------------------------------------------------------------- subjects


def test_questions_then_objects_from_every_place_the_unit_keeps_them() -> None:
    subjects = extract_subjects(DESIGN, _knowledge())
    kinds = [(s.kind, s.text) for s in subjects]
    assert kinds == [
        (SubjectKind.QUESTION, "Proč lidé kupují rostlinné nápoje?"),
        (SubjectKind.QUESTION, "Kdo je kupuje?"),
        (SubjectKind.OBJECT, "Aroma"),  # "aroma" is the same object
        (SubjectKind.OBJECT, "Borealis"),
        (SubjectKind.OBJECT, "Cedrus"),  # 7 is not a label
        (SubjectKind.OBJECT, "Dubina"),
    ]
    assert subjects[2].origin == "research_plan.tracked_sets[0].objects[0]"
    assert subjects[-1].origin == "sections[1].objects[1]"


def test_without_research_questions_the_goal_is_the_one_question() -> None:
    subjects = extract_subjects({"goal": "Porozumět trhu"}, _knowledge())
    assert [(s.kind, s.text, s.origin) for s in subjects] == [
        (SubjectKind.QUESTION, "Porozumět trhu", "goal (no research questions yet)")
    ]
    assert extract_subjects({}, _knowledge()) == ()


def test_an_entity_becomes_an_object_only_when_the_brief_names_it() -> None:
    knowledge = _knowledge(_entity("Aroma", 1), _entity("Neznámá značka", 2))
    subjects = extract_subjects({"goal": "Jak si vede AROMA?"}, knowledge)
    objects = [s for s in subjects if s.kind is SubjectKind.OBJECT]
    assert [(o.text, o.origin) for o in objects] == [
        ("Aroma", "knowledge:KNW-00000000000001@1 (named in the brief)")
    ]


def test_the_screen_reads_survey_questions_and_battery_objects_not_research_questions() -> None:
    screen = screen_questions(DESIGN)
    assert [(q.id, q.text, q.kategorie) for q in screen] == [
        ("q1", "Jak často kupujete rostlinné nápoje?", ("Denně", "Nikdy")),
        ("q2", "Souhlasíte?", ("Ano", "Ne")),
        ("b1_obj_1", "Jak hodnotíte značku Aroma?", ()),
        ("b1_obj_2", "Jak hodnotíte značku Dubina?", ()),
    ]
    assert screen_questions({"research_plan": DESIGN["research_plan"]}) == ()


# --------------------------------------------------------------------------- tracks


def test_tracks_run_in_subject_order_internal_before_web() -> None:
    tracks, beyond = build_tracks(_request(DESIGN), PRESETS["QUICK"], inputs=INPUTS)
    assert beyond == ()
    assert [(t.subject.text, t.channel) for t in tracks][:4] == [
        ("Proč lidé kupují rostlinné nápoje?", Channel.INTERNAL),
        ("Proč lidé kupují rostlinné nápoje?", Channel.WEB),
        ("Kdo je kupuje?", Channel.INTERNAL),
        ("Kdo je kupuje?", Channel.WEB),
    ]
    assert len(tracks) == 12
    assert all(t.track_id.startswith("DRT-") for t in tracks)


def test_only_requested_channels_get_tracks_and_crosses_only_when_the_preset_opens_them() -> None:
    web_only = _request(DESIGN, channels=(Channel.WEB,))
    tracks, _ = build_tracks(web_only, PRESETS["QUICK"], inputs=INPUTS)
    assert {t.channel for t in tracks} == {Channel.WEB}
    deep, _ = build_tracks(web_only, PRESETS["DEEP"], inputs=INPUTS)
    crosses = [t for t in deep if t.subject.kind is SubjectKind.CROSS]
    assert len(crosses) == 2 * 4  # two questions x four objects
    assert crosses[0].subject.question_key and crosses[0].subject.object_key


def test_tracks_beyond_the_limit_are_returned_to_be_recorded_never_dropped() -> None:
    small = PRESETS["QUICK"].model_copy(update={"max_tracks": 5})
    tracks, beyond = build_tracks(_request(DESIGN), small, inputs=INPUTS)
    assert len(tracks) == 5 and len(beyond) == 7


def _fingerprints(request: DeepResearchRequest, inputs: TrackInputs = INPUTS) -> dict[str, str]:
    tracks, _ = build_tracks(request, PRESETS["QUICK"], inputs=inputs)
    return {t.track_id: t.fingerprint for t in tracks}


def test_adding_an_object_leaves_every_existing_track_fingerprint_unchanged() -> None:
    before = _fingerprints(_request(DESIGN))
    later = dict(DESIGN, tracked_objects=["Cedrus", "Eben"])
    after = _fingerprints(_request(later))
    assert set(before) < set(after)
    assert all(after[t] == fp for t, fp in before.items())
    assert len(set(after) - set(before)) == 2  # Eben, on both channels


def test_knowledge_changes_internal_tracks_only_and_retrieval_changes_web_tracks_only() -> None:
    base = _fingerprints(_request(DESIGN))
    with_item = _fingerprints(_request(DESIGN, knowledge=_knowledge(_entity("Nová položka", 9))))
    live = _fingerprints(
        _request(DESIGN),
        TrackInputs(
            policy_version="test-v1",
            prompt_versions={Channel.WEB: "1", Channel.INTERNAL: "1"},
            web_retrieval={"search": "search-live", "mode": "LIVE"},
        ),
    )
    for track, fp in base.items():
        internal = track.startswith("DRT-I-")
        assert (with_item[track] != fp) is internal
        assert (live[track] != fp) is not internal


def test_a_changed_brief_or_depth_changes_every_track() -> None:
    base = _fingerprints(_request(DESIGN))
    rebriefed = _fingerprints(_request(dict(DESIGN, briefing="Zajímá nás i Slovensko.")))
    assert all(rebriefed[t] != fp for t, fp in base.items())
    tracks, _ = build_tracks(_request(DESIGN), PRESETS["STANDARD"], inputs=INPUTS)
    assert all(t.fingerprint != base[t.track_id] for t in tracks)


# --------------------------------------------------------------------------- the plan


def test_a_plan_must_cover_every_requested_track_once_and_nothing_else() -> None:
    assert check_plan_coverage(["A", "B"], {"A": ["q"], "B": ["q2"]}) == ()
    problems = check_plan_coverage(["A", "B"], {"A": ["  "], "C": ["q"]})
    assert {(p.track_id, p.problem) for p in problems} == {
        ("B", "no plan for this track"),
        ("C", "the plan names a track that was not requested"),
        ("A", "the plan gives this track no query"),
    }


# --------------------------------------------------------------------------- depth


def test_presets_are_named_explicitly_and_there_is_no_default() -> None:
    assert preset("QUICK") is PRESETS["QUICK"]
    with pytest.raises(UnknownPreset):
        preset("DEFAULT")


def test_limits_are_shared_equally_with_the_remainder_to_earlier_tracks() -> None:
    depth = PRESETS["QUICK"].model_copy(update={"max_search_calls": 5, "max_fetches": 7})
    shares = allocate(["t1", "t2", "t3"], depth)
    assert [shares[t].search_calls for t in ("t1", "t2", "t3")] == [2, 2, 1]
    assert [shares[t].fetches for t in ("t1", "t2", "t3")] == [3, 2, 2]
    starved = allocate(["t1", "t2"], depth.model_copy(update={"max_search_calls": 1}))
    assert starved["t2"].search_calls == 0  # it will stop at once: budget_exhausted
    assert allocate([], depth) == {}


@pytest.mark.parametrize(
    ("kwargs", "reason"),
    [
        (
            {"grounded": 4, "new_by_round": [4], "queries_left": 1, "searches_left": 1},
            StopReason.DEPTH_TARGET_MET,
        ),
        (
            {"grounded": 1, "new_by_round": [1, 0], "queries_left": 1, "searches_left": 1},
            StopReason.SATURATED,
        ),
        (
            {"grounded": 1, "new_by_round": [1], "queries_left": 1, "searches_left": 0},
            StopReason.BUDGET_EXHAUSTED,
        ),
        (
            {"grounded": 1, "new_by_round": [1], "queries_left": 0, "searches_left": 1},
            StopReason.QUERIES_EXHAUSTED,
        ),
        ({"grounded": 1, "new_by_round": [1], "queries_left": 1, "searches_left": 1}, None),
        ({"grounded": 0, "new_by_round": [], "queries_left": 2, "searches_left": 2}, None),
    ],
)
def test_a_track_stops_on_depth_saturation_budget_or_exhaustion(
    kwargs: dict[str, Any], reason: StopReason | None
) -> None:
    assert stop_reason(depth=PRESETS["QUICK"], **kwargs) is reason


# --------------------------------------------------------------------------- coverage


def test_a_cell_is_covered_by_a_cross_or_by_both_its_tracks_completed() -> None:
    request = _request(DESIGN)
    tracks, _ = build_tracks(request, PRESETS["QUICK"], inputs=INPUTS)
    question, obj = request.subjects[0], request.subjects[2]

    def cell(track: Any, status: TrackStatus) -> CoverageCell:
        return CoverageCell(
            subject_key=track.subject.key,
            channel=track.channel,
            track_id=track.track_id,
            status=status,
            stop_reason=StopReason.SATURATED,
            reused=False,
            accepted=0,
            quarantined=0,
        )

    q_web = next(t for t in tracks if t.subject.key == question.key and t.channel is Channel.WEB)
    o_web = next(t for t in tracks if t.subject.key == obj.key and t.channel is Channel.WEB)
    covered = coverage_grid(
        request.subjects, [cell(q_web, TrackStatus.COMPLETED), cell(o_web, TrackStatus.COMPLETED)]
    )
    first = next(g for g in covered if g.question_key == question.key and g.object_key == obj.key)
    assert first.covered and first.cross_track is None
    blocked = coverage_grid(
        request.subjects, [cell(q_web, TrackStatus.COMPLETED), cell(o_web, TrackStatus.BLOCKED)]
    )
    assert not next(
        g for g in blocked if g.object_key == obj.key and g.question_key == question.key
    ).covered


#: The fingerprints of ``_request(DESIGN)``'s tracks under ``INPUTS``, digested, as
#: origin/develop @ 757154e computed them before the thinking budget existed. A
#: deliberate change to the harness, the rules or this file's design moves it (re-pin
#: it then); a thinking budget left unset never may.
FINGERPRINTS_WITHOUT_THINKING = "ebcebd817430c267256764a0fe0d2612d7dfba2007a7cb0dbc46f7919a583b50"


def _thinking(budget: int | None) -> TrackInputs:
    return TrackInputs(
        policy_version=INPUTS.policy_version,
        prompt_versions=INPUTS.prompt_versions,
        web_retrieval=INPUTS.web_retrieval,
        thinking_budget_tokens=budget,
    )


def test_without_a_thinking_budget_every_fingerprint_is_the_one_it_was() -> None:
    fingerprints = _fingerprints(_request(DESIGN), _thinking(None))
    digest = hashlib.sha256(json.dumps(fingerprints, sort_keys=True).encode()).hexdigest()
    assert digest == FINGERPRINTS_WITHOUT_THINKING
    assert fingerprints == _fingerprints(_request(DESIGN))


def test_a_thinking_budget_is_part_of_every_track_and_its_size_matters() -> None:
    base = _fingerprints(_request(DESIGN))
    thinking = _fingerprints(_request(DESIGN), _thinking(2048))
    more = _fingerprints(_request(DESIGN), _thinking(4096))
    assert all(thinking[t] != fp for t, fp in base.items())
    assert all(more[t] != fp for t, fp in thinking.items())
