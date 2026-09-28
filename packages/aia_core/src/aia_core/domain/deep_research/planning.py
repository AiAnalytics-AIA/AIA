"""From a Design Revision to research tracks: subjects, fingerprints, depth, stopping.

Code, not a model, decides *what* is researched (plan decision I-1, ADR 0007):

* :func:`extract_subjects` reads the research questions and the tracked objects out
  of the design (DR-1: both drive research), plus the Client Knowledge ``ENTITY``
  items the brief already names;
* :func:`build_tracks` makes one track per subject per requested channel, in a
  fixed order, and fingerprints each from everything its result depends on
  (:func:`track_fingerprint`) -- the key a later pass reuses a track by;
* the planning model only fills the web tracks it is shown with sub-questions
  and queries, and :func:`check_plan_coverage` refuses a plan that skips a track
  or invents one;
* :func:`allocate` splits a preset's limits across the tracks, and
  :func:`stop_reason` ends a track on depth, saturation, budget or exhaustion,
  and says which.

The presets are a **proposal** (DR-5 is open): a run names one explicitly; there is
no default depth and no default budget.

Pure: stdlib and Pydantic only.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Final

from pydantic import BaseModel, ConfigDict, Field

from .classification import CLASSIFIER_VERSION, fold
from .contracts import (
    HARNESS_VERSION,
    BriefDigest,
    Channel,
    CoverageCell,
    DeepResearchRequest,
    FrozenKnowledge,
    GridCell,
    ResearchSubject,
    ResearchTrack,
    ScreenQuestion,
    StopReason,
    SubjectKind,
    TrackStatus,
    digest,
    normalise_label,
    subject_key,
    track_id,
)
from .grounding import GROUNDING_VERSION

__all__ = [
    "PRESETS",
    "PRESET_STATUS",
    "DepthPreset",
    "PlanViolation",
    "TrackAllowance",
    "TrackInputs",
    "UnknownPreset",
    "allocate",
    "brief_digest",
    "build_tracks",
    "check_plan_coverage",
    "coverage_grid",
    "extract_subjects",
    "preset",
    "screen_questions",
    "stop_reason",
    "track_fingerprint",
]

#: The presets are proposed, not decided (DR-5); the status travels with every run.
PRESET_STATUS: Final = "PROPOSED_DR5"


class DepthPreset(BaseModel):
    """How far a run goes, as numbers. Every limit is visible; none is hidden."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str
    queries_per_web_track: int = Field(ge=1, le=12)
    pages_per_query: int = Field(ge=1, le=8)
    evidence_target: int = Field(ge=1, le=40)
    knowledge_items_per_track: int = Field(ge=1, le=20)
    include_crosses: bool
    saturation_window: int = Field(ge=1, le=6)
    max_tracks: int = Field(ge=1, le=400)
    max_search_calls: int = Field(ge=0, le=2000)
    max_fetches: int = Field(ge=0, le=5000)
    #: Evidence items one verification request judges.
    verify_batch: int = Field(ge=1, le=40)


PRESETS: Final[dict[str, DepthPreset]] = {
    p.name: p
    for p in (
        DepthPreset(
            name="QUICK",
            queries_per_web_track=2,
            pages_per_query=2,
            evidence_target=4,
            knowledge_items_per_track=4,
            include_crosses=False,
            saturation_window=1,
            max_tracks=24,
            max_search_calls=48,
            max_fetches=96,
            verify_batch=12,
        ),
        DepthPreset(
            name="STANDARD",
            queries_per_web_track=4,
            pages_per_query=3,
            evidence_target=8,
            knowledge_items_per_track=6,
            include_crosses=False,
            saturation_window=2,
            max_tracks=60,
            max_search_calls=240,
            max_fetches=720,
            verify_batch=12,
        ),
        DepthPreset(
            name="DEEP",
            queries_per_web_track=6,
            pages_per_query=4,
            evidence_target=12,
            knowledge_items_per_track=8,
            include_crosses=True,
            saturation_window=2,
            max_tracks=200,
            max_search_calls=1200,
            max_fetches=4800,
            verify_batch=12,
        ),
    )
}


class UnknownPreset(LookupError):
    """A run names a depth that does not exist. There is no default depth."""


def preset(name: str) -> DepthPreset:
    try:
        return PRESETS[name]
    except KeyError as exc:
        raise UnknownPreset(f"no depth preset {name!r}; one of {sorted(PRESETS)}") from exc


# --------------------------------------------------------------------------- #
# Subjects
# --------------------------------------------------------------------------- #


def _text(value: Any) -> str:
    return " ".join(str(value).split()) if isinstance(value, str) else ""


def brief_digest(design: Mapping[str, Any]) -> BriefDigest:
    """The brief every track depends on: title, goal, decision use, briefing."""
    return BriefDigest(
        title=_text(design.get("title"))[:500],
        goal=_text(design.get("goal"))[:4000],
        decision_use=_text(design.get("decision_use"))[:4000],
        briefing=_text(design.get("briefing"))[:16000],
    )


def extract_subjects(
    design: Mapping[str, Any], knowledge: FrozenKnowledge
) -> tuple[ResearchSubject, ...]:
    """Research questions, then tracked objects, deduplicated by their normalised text.

    Questions come from ``research_plan.research_questions``; with none yet (a brief
    not analysed), the goal is the one question, and its origin says so. Objects come
    from ``research_plan.tracked_sets[].objects``, ``tracked_objects`` and the
    object batteries in ``sections`` -- the places the unit keeps them -- and from
    approved ``ENTITY`` knowledge items whose name the brief contains.
    """
    subjects: list[ResearchSubject] = []
    seen: set[str] = set()

    def add(kind: SubjectKind, text: str, origin: str) -> None:
        text = text.strip()
        if not text:
            return
        key = subject_key(kind, text)
        if key in seen:
            return
        seen.add(key)
        subjects.append(ResearchSubject(key=key, kind=kind, text=text[:1500], origin=origin))

    plan = design.get("research_plan")
    plan = plan if isinstance(plan, Mapping) else {}
    questions = plan.get("research_questions")
    for i, q in enumerate(questions if isinstance(questions, list) else []):
        add(SubjectKind.QUESTION, _text(q), f"research_plan.research_questions[{i}]")
    if not any(s.kind is SubjectKind.QUESTION for s in subjects):
        add(SubjectKind.QUESTION, _text(design.get("goal")), "goal (no research questions yet)")

    tracked_sets = plan.get("tracked_sets")
    for i, tracked in enumerate(tracked_sets if isinstance(tracked_sets, list) else []):
        objects = tracked.get("objects") if isinstance(tracked, Mapping) else None
        for j, obj in enumerate(objects if isinstance(objects, list) else []):
            add(SubjectKind.OBJECT, _text(obj), f"research_plan.tracked_sets[{i}].objects[{j}]")
    tracked_objects = design.get("tracked_objects")
    for i, obj in enumerate(tracked_objects if isinstance(tracked_objects, list) else []):
        add(SubjectKind.OBJECT, _text(obj), f"tracked_objects[{i}]")
    sections = design.get("sections")
    for i, section in enumerate(sections if isinstance(sections, list) else []):
        if not isinstance(section, Mapping) or section.get("type") != "object_battery":
            continue
        objects = section.get("objects")
        for j, obj in enumerate(objects if isinstance(objects, list) else []):
            add(SubjectKind.OBJECT, _text(obj), f"sections[{i}].objects[{j}]")

    brief = fold(" ".join(_text(design.get(k)) for k in ("title", "goal", "briefing")))
    for item in knowledge.items:
        if item.kind != "ENTITY":
            continue
        name = fold(item.title)
        if name and f" {name} " in f" {brief} ":
            add(SubjectKind.OBJECT, item.title, f"knowledge:{item.ref} (named in the brief)")
    return tuple(subjects)


def screen_questions(design: Mapping[str, Any]) -> tuple[ScreenQuestion, ...]:
    """The survey questions a design holds, as the leakage screen reads them.

    Each question's text and categories; each battery object as the question its
    respondents are asked (the template with ``{object}`` filled in). Research
    questions are not survey questions, and are not screened against.
    """
    out: list[ScreenQuestion] = []
    sections = design.get("sections")
    for i, section in enumerate(sections if isinstance(sections, list) else []):
        if not isinstance(section, Mapping):
            continue
        sid = _text(section.get("id")) or f"section_{i + 1}"
        if section.get("type") == "object_battery":
            template = _text(section.get("object_question")) or "Jak hodnotíte položku {object}?"
            objects = section.get("objects")
            for j, obj in enumerate(objects if isinstance(objects, list) else []):
                label = _text(obj)
                if label:
                    text = template.replace("{object}", label)
                    out.append(ScreenQuestion(id=f"{sid}_obj_{j + 1}", text=text))
            continue
        questions = section.get("questions")
        for j, q in enumerate(questions if isinstance(questions, list) else []):
            if not isinstance(q, Mapping) or not _text(q.get("text")):
                continue
            cats = q.get("kategorie") or q.get("volby") or []
            kategorie = tuple(_text(c) for c in cats if _text(c)) if isinstance(cats, list) else ()
            out.append(
                ScreenQuestion(
                    id=_text(q.get("id")) or f"{sid}_{j + 1}",
                    text=_text(q.get("text")),
                    kategorie=kategorie,
                )
            )
    return tuple(out)


# --------------------------------------------------------------------------- #
# Tracks
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class TrackInputs:
    """What a track's result depends on beyond the request: the composition's facts.

    ``web_retrieval`` identifies the retrieval a web track would use -- route ids,
    recorded or live, adapter ids and prices -- or ``None`` when this composition
    has none; a recorded result is then never reused as a live one.
    """

    policy_version: str
    prompt_versions: Mapping[Channel, str]
    web_retrieval: Mapping[str, Any] | None


def track_fingerprint(
    subject: ResearchSubject,
    channel: Channel,
    *,
    request: DeepResearchRequest,
    depth: DepthPreset,
    inputs: TrackInputs,
) -> str:
    """Everything a track's result depends on; the key a later pass reuses it by.

    A web track depends on its subject, the brief, the depth, the model policy and
    prompt, the grounding and classifier rules, and the retrieval it runs on. An
    internal track depends on the same, with the frozen knowledge instead of the
    retrieval. Neither depends on the *other* subjects, so adding an object in a
    later pass leaves every existing track's fingerprint where it was.
    """
    material: dict[str, Any] = {
        "harness": HARNESS_VERSION,
        "subject": [subject.key, subject.kind.value, normalise_label(subject.text)],
        "channel": channel.value,
        "depth": depth.model_dump(mode="json"),
        "brief": request.brief.fingerprint(),
        "policy": inputs.policy_version,
        "prompt": inputs.prompt_versions.get(channel, ""),
        "rules": [GROUNDING_VERSION, CLASSIFIER_VERSION],
    }
    if channel is Channel.WEB:
        material["retrieval"] = dict(inputs.web_retrieval) if inputs.web_retrieval else None
    else:
        material["knowledge"] = request.knowledge.fingerprint()
    return digest(material)


def _crosses(subjects: Sequence[ResearchSubject]) -> list[ResearchSubject]:
    questions = [s for s in subjects if s.kind is SubjectKind.QUESTION]
    objects = [s for s in subjects if s.kind is SubjectKind.OBJECT]
    crosses = []
    for q in questions:
        for o in objects:
            text = f"{q.text} \u2014 {o.text}"
            crosses.append(
                ResearchSubject(
                    key="x-" + digest([q.key, o.key])[:12],
                    kind=SubjectKind.CROSS,
                    text=text[:1500],
                    origin=f"cross:{q.key}|{o.key}",
                    question_key=q.key,
                    object_key=o.key,
                )
            )
    return crosses


def build_tracks(
    request: DeepResearchRequest, depth: DepthPreset, *, inputs: TrackInputs
) -> tuple[tuple[ResearchTrack, ...], tuple[ResearchTrack, ...]]:
    """(tracks to run, tracks beyond the preset's limit), in a fixed order.

    Order: questions, objects, then crosses when the preset opens them; within a
    subject, internal before web. Tracks beyond ``max_tracks`` are returned, not
    dropped: the run records them as skipped (``track_limit``).
    """
    subjects = list(request.subjects)
    if depth.include_crosses:
        subjects += _crosses(request.subjects)
    channels = [c for c in (Channel.INTERNAL, Channel.WEB) if c in request.channels]
    tracks = [
        ResearchTrack(
            track_id=track_id(subject.key, channel),
            subject=subject,
            channel=channel,
            fingerprint=track_fingerprint(
                subject, channel, request=request, depth=depth, inputs=inputs
            ),
        )
        for subject in subjects
        for channel in channels
    ]
    return tuple(tracks[: depth.max_tracks]), tuple(tracks[depth.max_tracks :])


# --------------------------------------------------------------------------- #
# The plan the model fills in
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class PlanViolation:
    track_id: str
    problem: str


def check_plan_coverage(
    requested: Sequence[str], planned: Mapping[str, Sequence[str]]
) -> tuple[PlanViolation, ...]:
    """Every requested track planned exactly once with a query, and nothing else.

    ``planned`` maps each track id the model returned to its queries. A missing
    track is a hole in the coverage matrix; an invented one is a track nobody
    asked for; a track without a query cannot search. Each refuses the plan.
    """
    violations = [PlanViolation(t, "no plan for this track") for t in requested if t not in planned]
    violations += [
        PlanViolation(t, "the plan names a track that was not requested")
        for t in planned
        if t not in set(requested)
    ]
    violations += [
        PlanViolation(t, "the plan gives this track no query")
        for t, queries in planned.items()
        if t in set(requested) and not [q for q in queries if q.strip()]
    ]
    return tuple(violations)


# --------------------------------------------------------------------------- #
# Allowances and stopping
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class TrackAllowance:
    """One web track's share of a run's search and fetch limits."""

    search_calls: int
    fetches: int


def allocate(web_tracks: Sequence[str], depth: DepthPreset) -> dict[str, TrackAllowance]:
    """Split the run's search and fetch limits across its web tracks, deterministically.

    Each track gets at most what its preset allows one track, and an equal share of
    the run's limits; the remainder of a division goes to the earlier tracks. A
    track whose share is zero stops at once with ``budget_exhausted``: visible,
    never skipped in silence.
    """
    n = len(web_tracks)
    if n == 0:
        return {}
    searches, extra_s = divmod(depth.max_search_calls, n)
    fetches, extra_f = divmod(depth.max_fetches, n)
    per_track_fetches = depth.queries_per_web_track * depth.pages_per_query
    return {
        t: TrackAllowance(
            search_calls=min(depth.queries_per_web_track, searches + (1 if i < extra_s else 0)),
            fetches=min(per_track_fetches, fetches + (1 if i < extra_f else 0)),
        )
        for i, t in enumerate(web_tracks)
    }


def stop_reason(
    *,
    grounded: int,
    new_by_round: Sequence[int],
    queries_left: int,
    searches_left: int,
    depth: DepthPreset,
) -> StopReason | None:
    """Why a web track stops after the rounds so far, or ``None`` to go on.

    "Go ham" means: keep searching while the depth target is unmet, the last
    ``saturation_window`` rounds still produced newly grounded evidence, the track's
    budget has room, and the plan has queries left. Whichever ends first ends the
    track, and the reason is recorded.
    """
    if grounded >= depth.evidence_target:
        return StopReason.DEPTH_TARGET_MET
    window = depth.saturation_window
    if len(new_by_round) >= window and not any(new_by_round[-window:]):
        return StopReason.SATURATED
    if searches_left <= 0:
        return StopReason.BUDGET_EXHAUSTED
    if queries_left <= 0:
        return StopReason.QUERIES_EXHAUSTED
    return None


# --------------------------------------------------------------------------- #
# Coverage
# --------------------------------------------------------------------------- #


def coverage_grid(
    subjects: Sequence[ResearchSubject], cells: Sequence[CoverageCell]
) -> tuple[GridCell, ...]:
    """Every research question x tracked object cell, and what covers it.

    A cell is covered by a completed cross track, or by completed tracks on both its
    question and its object; a blocked or incomplete track covers nothing.
    """
    done: dict[str, list[str]] = {c.subject_key: [] for c in cells}
    for cell in cells:
        if cell.status is TrackStatus.COMPLETED:
            done[cell.subject_key].append(cell.track_id)
    crosses = {
        (s.question_key, s.object_key): s.key for s in subjects if s.kind is SubjectKind.CROSS
    }
    grid = []
    for q in (s for s in subjects if s.kind is SubjectKind.QUESTION):
        for o in (s for s in subjects if s.kind is SubjectKind.OBJECT):
            cross = crosses.get((q.key, o.key))
            cross_tracks = done.get(cross, []) if cross else []
            q_tracks, o_tracks = done.get(q.key, []), done.get(o.key, [])
            grid.append(
                GridCell(
                    question_key=q.key,
                    object_key=o.key,
                    cross_track=cross_tracks[0] if cross_tracks else None,
                    question_tracks=tuple(q_tracks),
                    object_tracks=tuple(o_tracks),
                    covered=bool(cross_tracks) or bool(q_tracks and o_tracks),
                )
            )
    return tuple(grid)
