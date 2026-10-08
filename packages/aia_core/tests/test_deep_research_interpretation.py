"""Interpretation Research's mission, built by code from its target (ADR 0021, chunk 30).

What is pinned here, in the domain:

* **each target kind's mission** -- its subjects, their kinds, Czech texts and origins, exactly
  as the plan's table says; the same target always the same subjects;
* **no respondent number** -- the mission is built from the specification and the design
  only, so nothing a result holds can be in a subject;
* **the enqueue rule** -- a spec is refused unless every subject carries its own target's
  origin: the design's subjects under an interpretation label, another target's mission and
  an empty request are refused; a design spec may not hold an interpretation subject.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

from aia_core.domain.analysis.modules import AnalysisModuleId
from aia_core.domain.deep_research.contracts import (
    DeepResearchRequest,
    FrozenKnowledge,
    ResearchSubject,
    subject_key,
)
from aia_core.domain.deep_research.integration import (
    RUN_SPEC_CONTRACT,
    AnalysisModuleTarget,
    ArtifactPin,
    DeepResearchPurpose,
    DeepResearchRunSpec,
    DesignLineage,
    DesignRevisionTarget,
    InterpretationLineage,
    ResearchTargetRef,
    ResultBatteryObjectTarget,
    ResultQuestionTarget,
    SociomapObjectTarget,
    SociomapRelationshipTarget,
    SociomapTarget,
    target_node,
)
from aia_core.domain.deep_research.interpretation import (
    InterpretationMissionMismatch,
    MissionTargetInvalid,
    interpretation_mission,
    mission_origin,
    require_interpretation_mission,
)
from aia_core.domain.deep_research.planning import extract_subjects
from aia_core.domain.research_design import ResearchSpecification, compile_design

RUN = "RUN-00000000000000a1"
AGG, SOC, ANA = "ART-00000000000000a3", "ART-00000000000000a4", "ART-00000000000000a5"
RQ1 = "Proč lidé přecházejí na rostlinné nápoje?"
RQ2 = "Kdo kupuje mandlový nápoj?"
DESIGN: dict[str, Any] = {
    "title": "Rostlinné nápoje",
    "goal": "Porozumět trhu rostlinných nápojů před uvedením nového nápoje.",
    # A design's own number: never a respondent's, and never read into a mission.
    "n": 8731,
    "research_plan": {"research_questions": [RQ1, RQ2]},
    "sections": [
        {
            "type": "questions",
            "questions": [
                {
                    "id": "q1",
                    "text": "Jaký podíl domácností kupuje rostlinné nápoje?",
                    "kategorie": ["Ano", "Ne"],
                },
                {"id": "q10", "text": "Jak často je kupujete?", "kategorie": ["Často", "Zřídka"]},
            ],
        },
        {
            "type": "object_battery",
            "id": "napoje",
            "title": "Nápoje",
            "object_family": "rostlinné nápoje",
            "objects": ["Ovesný nápoj", "Mandlový nápoj", "Sójový nápoj"],
            "object_question": "Jak hodnotíte {object}?",
        },
    ],
}


def _spec(design: dict[str, Any] = DESIGN) -> ResearchSpecification:
    spec, problems = compile_design(design)
    assert spec is not None, problems
    return spec


SPEC = _spec()
(BATTERY,) = SPEC.batteries
OATS, ALMOND, SOY = (o.id for o in BATTERY.objects)


def _q(question_id: str = "q1") -> ResultQuestionTarget:
    return ResultQuestionTarget(
        kind="RESULT_QUESTION",
        research_run_id=RUN,
        aggregate_artifact_id=AGG,
        question_id=question_id,
    )


def _bo(object_id: str = OATS) -> ResultBatteryObjectTarget:
    return ResultBatteryObjectTarget(
        kind="RESULT_BATTERY_OBJECT",
        research_run_id=RUN,
        aggregate_artifact_id=AGG,
        battery_id=BATTERY.id,
        object_id=object_id,
    )


def _am(module: AnalysisModuleId) -> AnalysisModuleTarget:
    return AnalysisModuleTarget(
        kind="ANALYSIS_MODULE", research_run_id=RUN, analysis_artifact_id=ANA, module_id=module
    )


def _sm() -> SociomapTarget:
    return SociomapTarget(
        kind="SOCIOMAP", research_run_id=RUN, sociomap_artifact_id=SOC, battery_id=BATTERY.id
    )


def _so(object_id: str = ALMOND) -> SociomapObjectTarget:
    return SociomapObjectTarget(
        kind="SOCIOMAP_OBJECT",
        research_run_id=RUN,
        sociomap_artifact_id=SOC,
        battery_id=BATTERY.id,
        object_id=object_id,
    )


def _sr(a: str = SOY, b: str = OATS) -> SociomapRelationshipTarget:
    return SociomapRelationshipTarget(
        kind="SOCIOMAP_RELATIONSHIP",
        research_run_id=RUN,
        sociomap_artifact_id=SOC,
        battery_id=BATTERY.id,
        source_object_id=a,
        target_object_id=b,
    )


def _mission(target: Any, design: dict[str, Any] = DESIGN) -> tuple[ResearchSubject, ...]:
    return interpretation_mission(
        target, specification=_spec(design).model_dump(mode="json"), design=design
    )


def _shape(subjects: tuple[ResearchSubject, ...]) -> list[tuple[str, str, str]]:
    return [(s.kind.value, s.text, s.origin) for s in subjects]


# --------------------------------------------------------------------------- each target kind


def test_a_question_result_researches_the_question_framed_as_its_results_context() -> None:
    assert _shape(_mission(_q())) == [
        (
            "QUESTION",
            "Kontext a srovnání pro výsledek otázky „Jaký podíl domácností kupuje rostlinné "
            "nápoje?“: srovnatelná měření, vývoj v čase a možná vysvětlení z veřejných zdrojů",
            f"interpretation:RESULT_QUESTION:{RUN}/q1",
        )
    ]


def test_a_battery_object_result_researches_the_object_and_its_question() -> None:
    base = f"interpretation:RESULT_BATTERY_OBJECT:{RUN}/napoje/{OATS}"
    assert _shape(_mission(_bo())) == [
        ("OBJECT", "Ovesný nápoj", f"{base}#object"),
        (
            "QUESTION",
            "Kontext a srovnání pro výsledek otázky „Jak hodnotíte Ovesný nápoj?“: srovnatelná "
            "měření, vývoj v čase a možná vysvětlení z veřejných zdrojů",
            f"{base}#question",
        ),
    ]


def test_the_research_questions_module_researches_each_research_question() -> None:
    base = f"interpretation:ANALYSIS_MODULE:{RUN}/research_questions"
    assert _shape(_mission(_am(AnalysisModuleId.RESEARCH_QUESTIONS))) == [
        (
            "QUESTION",
            f"Kontext a srovnání pro odpověď na výzkumnou otázku „{RQ1}“",
            f"{base}#research_questions[0]",
        ),
        (
            "QUESTION",
            f"Kontext a srovnání pro odpověď na výzkumnou otázku „{RQ2}“",
            f"{base}#research_questions[1]",
        ),
    ]
    # Without research questions, the goal is the one question, and its part says so.
    bare = {**DESIGN, "research_plan": {}}
    assert _shape(_mission(_am(AnalysisModuleId.RESEARCH_QUESTIONS), bare)) == [
        (
            "QUESTION",
            f"Kontext a srovnání pro odpověď na cíl studie „{DESIGN['goal']}“",
            f"{base}#goal",
        )
    ]


def test_the_objects_module_researches_each_tracked_object() -> None:
    base = f"interpretation:ANALYSIS_MODULE:{RUN}/objects"
    assert _shape(_mission(_am(AnalysisModuleId.OBJECTS))) == [
        ("OBJECT", "Ovesný nápoj", f"{base}#objects[0]"),
        ("OBJECT", "Mandlový nápoj", f"{base}#objects[1]"),
        ("OBJECT", "Sójový nápoj", f"{base}#objects[2]"),
    ]
    # A specification with no tracked set: nothing to research.
    no_battery = {**DESIGN, "sections": [DESIGN["sections"][0]]}
    assert _mission(_am(AnalysisModuleId.OBJECTS), no_battery) == ()


@pytest.mark.parametrize(
    ("module", "name"),
    [
        (AnalysisModuleId.EXECUTIVE, "Shrnutí pro rozhodnutí"),
        (AnalysisModuleId.AUDIENCE, "Cílová skupina"),
        (AnalysisModuleId.SEGMENTS, "Segmenty cílové skupiny"),
        (AnalysisModuleId.HYPOTHESES, "Hypotézy"),
        (AnalysisModuleId.IMPLICATIONS, "Důsledky a doporučení"),
        (AnalysisModuleId.LIMITATIONS, "Omezení a rizika výkladu"),
    ],
)
def test_any_other_module_researches_the_studys_goal_for_that_module(
    module: AnalysisModuleId, name: str
) -> None:
    assert _shape(_mission(_am(module))) == [
        (
            "QUESTION",
            f"{name} k cíli studie „{DESIGN['goal']}“: kontext, srovnání a možná vysvětlení "
            "z veřejných zdrojů",
            f"interpretation:ANALYSIS_MODULE:{RUN}/{module.value}#goal",
        )
    ]
    # No goal: the brief's title stands for it; neither: nothing to research.
    untitled = {k: v for k, v in DESIGN.items() if k != "goal"}
    assert "„Rostlinné nápoje“" in _mission(_am(module), untitled)[0].text
    assert _mission(_am(module), {k: v for k, v in untitled.items() if k != "title"}) == ()


def test_a_sociomap_researches_every_object_and_what_links_them() -> None:
    base = f"interpretation:SOCIOMAP:{RUN}/napoje"
    assert _shape(_mission(_sm())) == [
        ("OBJECT", "Ovesný nápoj", f"{base}#objects[0]"),
        ("OBJECT", "Mandlový nápoj", f"{base}#objects[1]"),
        ("OBJECT", "Sójový nápoj", f"{base}#objects[2]"),
        (
            "QUESTION",
            "Co spojuje a odlišuje položky kategorie „rostlinné nápoje“: „Ovesný nápoj“, "
            "„Mandlový nápoj“, „Sójový nápoj“",
            f"{base}#question",
        ),
    ]


def test_a_sociomap_object_researches_the_object() -> None:
    assert _shape(_mission(_so())) == [
        ("OBJECT", "Mandlový nápoj", f"interpretation:SOCIOMAP_OBJECT:{RUN}/napoje/{ALMOND}")
    ]


def test_a_relationship_researches_what_connects_the_pair_and_each_object() -> None:
    target = _sr()
    assert (target.source_object_id, target.target_object_id) == tuple(sorted((OATS, SOY)))
    pair = f"{target.source_object_id}+{target.target_object_id}"
    base = f"interpretation:SOCIOMAP_RELATIONSHIP:{RUN}/napoje/{pair}"
    first, second = (
        ("Ovesný nápoj", "Sójový nápoj") if OATS < SOY else ("Sójový nápoj", "Ovesný nápoj")
    )
    assert _shape(_mission(target)) == [
        (
            "QUESTION",
            f"Co spojuje a odlišuje položky „{first}“ a „{second}“ v kategorii „rostlinné nápoje“",
            f"{base}#question",
        ),
        ("OBJECT", first, f"{base}#source"),
        ("OBJECT", second, f"{base}#target"),
    ]
    # The pair named the other way round is the same relationship and the same mission.
    assert _mission(_sr(OATS, SOY)) == _mission(target)


ALL_TARGETS: list[Any] = [
    _q(),
    _q("q10"),
    _bo(),
    _bo(SOY),
    *(_am(m) for m in AnalysisModuleId),
    _sm(),
    _so(),
    _so(OATS),
    _sr(),
    _sr(ALMOND, SOY),
]


def test_the_same_target_is_always_the_same_mission_and_every_target_its_own() -> None:
    missions = [_mission(t) for t in ALL_TARGETS]
    assert missions == [_mission(t) for t in ALL_TARGETS]
    for target, mission in zip(ALL_TARGETS, missions, strict=True):
        assert mission, target
        assert all(s.key == subject_key(s.kind, s.text) for s in mission)
        assert len({s.key for s in mission}) == len(mission)
        origin = mission_origin(target)
        assert all(s.origin == origin or s.origin.startswith(origin + "#") for s in mission)
    # Two targets never share a mission: the origin names the target.
    assert len({tuple(m) for m in missions}) == len(missions)
    # The specification as a model or as its stored payload: the same subjects.
    assert interpretation_mission(_q(), specification=SPEC, design=DESIGN) == _mission(_q())


def test_a_mission_differs_from_the_design_runs_subjects_for_the_same_revision() -> None:
    design_subjects = set(extract_subjects(DESIGN, _no_knowledge()))
    for target in ALL_TARGETS:
        assert set(_mission(target)) != design_subjects
        assert not set(_mission(target)) & design_subjects  # origins differ, every one


# --------------------------------------------------------------------------- no respondent number


def test_no_number_of_the_result_or_the_specification_enters_a_mission() -> None:
    """A subject names what a result is about. The design here has no digit in any text, so
    a digit in a subject could only have come from a number -- and none does: the sample
    size 8731 and the scale's bounds are not read, and no result payload is given at all."""
    assert SPEC.n == 8731 and BATTERY.scale == (1, 10)
    for target in ALL_TARGETS:
        for subject in _mission(target):
            assert not any(ch.isdigit() for ch in subject.text), subject.text


# --------------------------------------------------------------------------- refusals


def test_an_entity_the_specification_does_not_hold_is_refused() -> None:
    for target in (
        _q("q99"),
        _bo("neexistuje"),
        _so("neexistuje"),
        _sr(OATS, "neexistuje"),
        _sm().model_copy(update={"battery_id": "neexistuje"}),
    ):
        with pytest.raises(MissionTargetInvalid):
            _mission(target)
    with pytest.raises(MissionTargetInvalid):
        interpretation_mission(
            DesignRevisionTarget(kind="DESIGN_REVISION", design_revision_id="REV-1"),
            specification=SPEC,
            design=DESIGN,
        )
    with pytest.raises(MissionTargetInvalid):
        interpretation_mission(_q(), specification={"questions": "nic"}, design=DESIGN)


def test_an_origin_stays_within_its_bound_and_names_long_ids_by_digest() -> None:
    design = {
        **DESIGN,
        "sections": [
            {**DESIGN["sections"][1], "id": "b" * 200, "objects": ["A" * 150, "B" * 150, "C"]}
        ],
    }
    spec = _spec(design)
    (battery,) = spec.batteries
    target = SociomapRelationshipTarget(
        kind="SOCIOMAP_RELATIONSHIP",
        research_run_id=RUN,
        sociomap_artifact_id=SOC,
        battery_id=battery.id,
        source_object_id=battery.objects[0].id,
        target_object_id=battery.objects[1].id,
    )
    assert len(battery.id) == 200 and len(battery.objects[0].id) > 140
    mission = interpretation_mission(target, specification=spec, design=design)
    assert all(len(s.origin) <= 300 for s in mission)
    assert mission_origin(target).startswith(f"interpretation:SOCIOMAP_RELATIONSHIP:{RUN}/sha256-")
    assert interpretation_mission(target, specification=spec, design=design) == mission


# --------------------------------------------------------------------------- the enqueue rule


FIXTURES = Path(__file__).parent / "fixtures" / "deep_research_pre_step1"


def _request(subjects: tuple[ResearchSubject, ...] | None = None) -> DeepResearchRequest:
    raw = (FIXTURES / "request.json").read_bytes()
    index = json.loads((FIXTURES / "index.json").read_text(encoding="utf-8"))
    assert hashlib.sha256(raw).hexdigest() == index["files"]["request.json"]
    request = DeepResearchRequest.model_validate(json.loads(raw))
    if subjects is None:
        return request
    return DeepResearchRequest.model_validate(
        {**request.model_dump(mode="json"), "subjects": [s.model_dump() for s in subjects]}
    )


def _no_knowledge() -> FrozenKnowledge:
    return FrozenKnowledge(items=(), omitted_ids=(), retrieval_limit=1)


def _interpretation(target: ResearchTargetRef, request: DeepResearchRequest) -> DeepResearchRunSpec:
    node = target_node(target)
    assert node is not None
    node_key, artifact_id, artifact_type = node
    pins = {
        "aggregate": ("ART-00000000000000a3", "research_aggregate"),
        "compile": ("ART-00000000000000a1", "research_specification"),
        "run": ("ART-00000000000000a2", "research_fieldwork_dataset"),
        node_key: (artifact_id, artifact_type),
    }
    return DeepResearchRunSpec(
        contract_version=RUN_SPEC_CONTRACT,
        purpose=DeepResearchPurpose.INTERPRETATION_RESEARCH,
        target=target,
        lineage=InterpretationLineage(
            kind="INTERPRETATION",
            research_run_id=RUN,
            design=DesignLineage(
                kind="DESIGN",
                design_revision_id=request.design_revision_id,
                design_revision=request.design_revision,
                design_content_sha256="a" * 64,
            ),
            artifacts=tuple(
                ArtifactPin(node_key=k, artifact_id=a, artifact_type=t, sha256="b" * 64)
                for k, (a, t) in sorted(pins.items())
            ),
        ),
        engine_request=request,
    )


def _design_spec(request: DeepResearchRequest) -> DeepResearchRunSpec:
    return DeepResearchRunSpec(
        contract_version=RUN_SPEC_CONTRACT,
        purpose=DeepResearchPurpose.DESIGN_RESEARCH,
        target=DesignRevisionTarget(
            kind="DESIGN_REVISION", design_revision_id=request.design_revision_id
        ),
        lineage=DesignLineage(
            kind="DESIGN",
            design_revision_id=request.design_revision_id,
            design_revision=request.design_revision,
            design_content_sha256="a" * 64,
        ),
        engine_request=request,
    )


def test_a_spec_researching_its_own_mission_is_admitted() -> None:
    for target in (_q(), _bo(), _am(AnalysisModuleId.OBJECTS), _sm(), _so(), _sr()):
        require_interpretation_mission(_interpretation(target, _request(_mission(target))))
    require_interpretation_mission(_design_spec(_request()))


def test_the_designs_subjects_under_an_interpretation_label_are_refused() -> None:
    """OI-88: the request frozen as a design run's, labelled as interpreting a result."""
    design_request = _request()
    assert all(not s.origin.startswith("interpretation:") for s in design_request.subjects)
    with pytest.raises(InterpretationMissionMismatch) as refused:
        require_interpretation_mission(_interpretation(_sm(), design_request))
    assert refused.value.code == "interpretation_mission_mismatch"
    # One design subject slipped in beside the mission is refused too.
    mixed = (*_mission(_sm()), design_request.subjects[0])
    with pytest.raises(InterpretationMissionMismatch):
        require_interpretation_mission(_interpretation(_sm(), _request(mixed)))


def test_another_targets_mission_and_an_empty_request_are_refused() -> None:
    # q10's mission under q1's target: the origin's prefix is not enough.
    with pytest.raises(InterpretationMissionMismatch):
        require_interpretation_mission(_interpretation(_q(), _request(_mission(_q("q10")))))
    with pytest.raises(InterpretationMissionMismatch):
        require_interpretation_mission(_interpretation(_so(), _request(_mission(_so(OATS)))))
    with pytest.raises(InterpretationMissionMismatch):
        require_interpretation_mission(_interpretation(_q(), _request(())))


def test_a_design_spec_may_not_hold_an_interpretation_subject() -> None:
    with pytest.raises(InterpretationMissionMismatch):
        require_interpretation_mission(_design_spec(_request(_mission(_sm()))))
