"""What an Interpretation Research run researches: its mission, built by code from its target.

ADR 0021 left ``INTERPRETATION_RESEARCH`` frozen, never enqueued, because its engine request
was still the design's: a run would be labelled as interpreting a result while researching the
design's subjects (OI-88). This module derives the run's **mission** -- the request's
``subjects`` -- from the exact result-side target (plan ``deep-research-web-search.md``
chunk 30). The engine stays frozen (ADR 0021 decision 7): the mission is expressed in the
request's existing ``subjects`` field; the brief, questionnaire, knowledge and client terms are
frozen from the producing run's Design Revision as before.

=========================  ===========================================================
Target                     Subjects
=========================  ===========================================================
``RESULT_QUESTION``        one ``QUESTION``: the survey question's text, framed as the
                           context and benchmarks of its result
``RESULT_BATTERY_OBJECT``  one ``OBJECT``: the object's label; one ``QUESTION``: the
                           battery's question about it, framed the same way
``ANALYSIS_MODULE``        ``research_questions``: each research question of the design;
                           ``objects``: each tracked object of the specification; any other
                           module: one ``QUESTION`` framing the study's goal for that module
``SOCIOMAP``               one ``OBJECT`` per object of the battery; one ``QUESTION``: what
                           links and separates the battery's objects in their family
``SOCIOMAP_OBJECT``        one ``OBJECT``: the object's label
``SOCIOMAP_RELATIONSHIP``  one ``QUESTION``: what connects the two objects; an ``OBJECT``
                           for each
=========================  ===========================================================

**No respondent number enters a mission.** A subject names what a result is *about*, never
what respondents answered. The mission is built from the pinned ``compile`` specification
(question texts, battery titles and families, object labels) and the Design Revision (research
questions, goal) -- never from the aggregate, the analysis outcome or the Sociomap, which hold
the shares, means, coordinates and relation strengths. The function is not given them, so it
cannot write one. Comparing external evidence with a result is code's work downstream, reading
both (the Lens, chunk 31; the report graph, chunk 32).

**Every subject says which target it researches.** Its ``origin`` is
``interpretation:<KIND>:<entity>`` (:func:`mission_origin`), the entity being the producing
research run and the target's ids, with ``#<part>`` when a target has several subjects. At the
one enqueue boundary :func:`require_interpretation_mission` refuses a spec whose request
subjects are not all this target's -- the design's subjects under an interpretation label --
without reading a store. A subject's origin is not part of any track fingerprint, so a mission
subject whose text equals a design subject's (an object's label) reuses that track.

Pure: stdlib and Pydantic only.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Final

from pydantic import ValidationError

from ..analysis.modules import AnalysisModuleId
from ..research_design import ResearchSpecification, SpecBattery
from .contracts import ResearchSubject, SubjectKind, digest, subject_key
from .integration import (
    AnalysisModuleTarget,
    DeepResearchPurpose,
    DeepResearchRunSpec,
    DesignRevisionTarget,
    ResearchTargetRef,
    ResultBatteryObjectTarget,
    ResultQuestionTarget,
    SociomapObjectTarget,
    SociomapRelationshipTarget,
    SociomapTarget,
)

__all__ = [
    "MISSION_ORIGIN",
    "InterpretationMissionMismatch",
    "MissionTargetInvalid",
    "interpretation_mission",
    "mission_origin",
    "require_interpretation_mission",
]

#: Every interpretation subject's origin starts with this.
MISSION_ORIGIN: Final = "interpretation"
#: ``ResearchSubject.origin``'s bound; an entity that would not fit is named by its digest.
_ORIGIN_MAX: Final = 300
#: Room kept for the longest ``#<part>`` suffix (``#research_questions[999]``).
_PART_ROOM: Final = 32
_TEXT_MAX: Final = 1500

#: What each analysis module answers, in Czech: how a goal-framed subject names it.
_MODULE_CS: Final[dict[AnalysisModuleId, str]] = {
    AnalysisModuleId.EXECUTIVE: "Shrnutí pro rozhodnutí",
    AnalysisModuleId.AUDIENCE: "Cílová skupina",
    AnalysisModuleId.SEGMENTS: "Segmenty cílové skupiny",
    AnalysisModuleId.HYPOTHESES: "Hypotézy",
    AnalysisModuleId.IMPLICATIONS: "Důsledky a doporučení",
    AnalysisModuleId.LIMITATIONS: "Omezení a rizika výkladu",
}


class MissionTargetInvalid(ValueError):
    """The target names nothing its specification holds, or is not a result at all."""


class InterpretationMissionMismatch(ValueError):
    """A spec's engine request does not research its own target (ADR 0021, OI-88)."""

    code = "interpretation_mission_mismatch"


def _text(value: Any) -> str:
    return " ".join(value.split()) if isinstance(value, str) else ""


def _bounded(text: str) -> str:
    return text if len(text) <= _TEXT_MAX else text[: _TEXT_MAX - 1].rstrip() + "…"


def _entity(target: ResearchTargetRef) -> str:
    if isinstance(target, ResultQuestionTarget):
        parts = [target.question_id]
    elif isinstance(target, ResultBatteryObjectTarget | SociomapObjectTarget):
        parts = [target.battery_id, target.object_id]
    elif isinstance(target, AnalysisModuleTarget):
        parts = [target.module_id.value]
    elif isinstance(target, SociomapTarget):
        parts = [target.battery_id]
    elif isinstance(target, SociomapRelationshipTarget):
        parts = [target.battery_id, f"{target.source_object_id}+{target.target_object_id}"]
    else:
        raise MissionTargetInvalid("Interpretation Research targets a result, not a design")
    return "/".join([target.research_run_id, *parts])


def mission_origin(target: ResearchTargetRef) -> str:
    """``interpretation:<KIND>:<entity>``: what every subject of this target's mission names.

    The entity is the research run and the target's ids; when that would not fit an origin
    (ids are up to 200 characters each) it is the run and the ids' digest, deterministically.
    """
    entity = _entity(target)
    base = f"{MISSION_ORIGIN}:{target.kind}:{entity}"
    if len(base) > _ORIGIN_MAX - _PART_ROOM:
        assert not isinstance(target, DesignRevisionTarget)
        base = f"{MISSION_ORIGIN}:{target.kind}:{target.research_run_id}/sha256-{digest(entity)}"
    return base


def _specification(payload: Mapping[str, Any] | ResearchSpecification) -> ResearchSpecification:
    if isinstance(payload, ResearchSpecification):
        return payload
    try:
        return ResearchSpecification.model_validate(payload)
    except ValidationError as exc:
        raise MissionTargetInvalid("the pinned specification does not validate") from exc


def _battery(spec: ResearchSpecification, battery_id: str) -> SpecBattery:
    battery = next((b for b in spec.batteries if b.id == battery_id), None)
    if battery is None:
        raise MissionTargetInvalid(f"the specification has no battery {battery_id!r}")
    return battery


def _label(battery: SpecBattery, object_id: str) -> str:
    obj = next((o for o in battery.objects if o.id == object_id), None)
    if obj is None:
        raise MissionTargetInvalid(f"the battery {battery.id!r} has no object {object_id!r}")
    return obj.label


def _result_framing(question: str) -> str:
    return _bounded(
        f"Kontext a srovnání pro výsledek otázky „{question}“: srovnatelná měření, "
        "vývoj v čase a možná vysvětlení z veřejných zdrojů"
    )


def interpretation_mission(
    target: ResearchTargetRef,
    *,
    specification: Mapping[str, Any] | ResearchSpecification,
    design: Mapping[str, Any],
) -> tuple[ResearchSubject, ...]:
    """The subjects an Interpretation Research run of ``target`` researches.

    ``specification`` is the producing run's pinned ``compile`` output (its ``specification``
    payload); ``design`` the content of the Design Revision that run executed. Deterministic:
    the same target over the same pins is always the same subjects, in the same order. Empty
    when there is nothing to research (an ``objects`` module over a specification with no
    tracked set; a goal-framed module over a design with no goal or title).

    Raises :class:`MissionTargetInvalid` for a design target, a specification that does not
    validate, or an entity the specification does not hold.
    """
    if isinstance(target, DesignRevisionTarget):
        raise MissionTargetInvalid("Interpretation Research targets a result, not a design")
    spec = _specification(specification)
    origin = mission_origin(target)
    subjects: list[ResearchSubject] = []
    seen: set[str] = set()

    def add(kind: SubjectKind, text: str, part: str | None = None) -> None:
        text = _bounded(_text(text))
        if not text:
            return
        key = subject_key(kind, text)
        if key in seen:
            return
        seen.add(key)
        subjects.append(
            ResearchSubject(
                key=key,
                kind=kind,
                text=text,
                origin=origin if part is None else f"{origin}#{part}",
            )
        )

    if isinstance(target, ResultQuestionTarget):
        question = next((q for q in spec.questions if q.id == target.question_id), None)
        if question is None:
            raise MissionTargetInvalid(f"the specification has no question {target.question_id!r}")
        add(SubjectKind.QUESTION, _result_framing(question.text))
    elif isinstance(target, ResultBatteryObjectTarget):
        battery = _battery(spec, target.battery_id)
        label = _label(battery, target.object_id)
        add(SubjectKind.OBJECT, label, "object")
        add(
            SubjectKind.QUESTION,
            _result_framing(battery.question_template.replace("{object}", label)),
            "question",
        )
    elif isinstance(target, AnalysisModuleTarget):
        for kind, text, part in _analysis_module(target.module_id, spec, design):
            add(kind, text, part)
    elif isinstance(target, SociomapTarget):
        battery = _battery(spec, target.battery_id)
        labels = [o.label for o in battery.objects]
        for i, label in enumerate(labels):
            add(SubjectKind.OBJECT, label, f"objects[{i}]")
        add(
            SubjectKind.QUESTION,
            f"Co spojuje a odlišuje položky kategorie „{battery.family}“: "
            + ", ".join(f"„{label}“" for label in labels),
            "question",
        )
    elif isinstance(target, SociomapObjectTarget):
        add(SubjectKind.OBJECT, _label(_battery(spec, target.battery_id), target.object_id))
    elif isinstance(target, SociomapRelationshipTarget):
        battery = _battery(spec, target.battery_id)
        a = _label(battery, target.source_object_id)
        b = _label(battery, target.target_object_id)
        add(
            SubjectKind.QUESTION,
            f"Co spojuje a odlišuje položky „{a}“ a „{b}“ v kategorii „{battery.family}“",
            "question",
        )
        add(SubjectKind.OBJECT, a, "source")
        add(SubjectKind.OBJECT, b, "target")
    return tuple(subjects)


def _analysis_module(
    module: AnalysisModuleId, spec: ResearchSpecification, design: Mapping[str, Any]
) -> list[tuple[SubjectKind, str, str]]:
    """An analysis module's subjects as (kind, text, part)."""
    if module is AnalysisModuleId.OBJECTS:
        labels = [o.label for b in spec.batteries for o in b.objects]
        return [(SubjectKind.OBJECT, label, f"objects[{i}]") for i, label in enumerate(labels)]
    goal = _text(design.get("goal")) or _text(design.get("title"))
    if module is AnalysisModuleId.RESEARCH_QUESTIONS:
        plan = design.get("research_plan")
        questions = plan.get("research_questions") if isinstance(plan, Mapping) else None
        texts = [_text(q) for q in (questions if isinstance(questions, list) else [])]
        if any(texts):
            return [
                (
                    SubjectKind.QUESTION,
                    f"Kontext a srovnání pro odpověď na výzkumnou otázku „{text}“",
                    f"research_questions[{i}]",
                )
                for i, text in enumerate(texts)
                if text
            ]
        if not goal:
            return []
        return [
            (SubjectKind.QUESTION, f"Kontext a srovnání pro odpověď na cíl studie „{goal}“", "goal")
        ]
    if not goal:
        return []
    return [
        (
            SubjectKind.QUESTION,
            f"{_MODULE_CS[module]} k cíli studie „{goal}“: kontext, srovnání "
            "a možná vysvětlení z veřejných zdrojů",
            "goal",
        )
    ]


def require_interpretation_mission(spec: DeepResearchRunSpec) -> None:
    """Refuse a spec whose engine request does not research its own purpose's subjects.

    ``INTERPRETATION_RESEARCH``: the request has subjects, and every one carries this target's
    origin (:func:`mission_origin`, exactly or with a ``#<part>``). ``DESIGN_RESEARCH``: no
    subject carries an interpretation origin. Reads no store: it holds what the spec says of
    itself, so a request frozen any other way -- the design's subjects under an interpretation
    label -- is never enqueued (:class:`InterpretationMissionMismatch`).
    """
    subjects = spec.engine_request.subjects
    if spec.purpose is DeepResearchPurpose.DESIGN_RESEARCH:
        if any(s.origin.startswith(f"{MISSION_ORIGIN}:") for s in subjects):
            raise InterpretationMissionMismatch(
                "a Design Research request holds an interpretation subject"
            )
        return
    origin = mission_origin(spec.target)
    foreign = [
        s.key for s in subjects if s.origin != origin and not s.origin.startswith(origin + "#")
    ]
    if not subjects or foreign:
        raise InterpretationMissionMismatch(
            "the request does not research this target's mission"
            + (f": {', '.join(foreign)}" if foreign else ": it has no subject")
        )
