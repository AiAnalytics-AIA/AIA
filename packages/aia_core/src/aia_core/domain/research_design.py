"""From a Design Revision to a research specification, and whether it can run.

ADR 0016, PR C chunk 4. Two pure functions:

* :func:`compile_design` turns the design the browser submitted -- the unit's
  research project document, ``sections`` of questions and tracked object sets --
  into a typed :class:`ResearchSpecification`: what fieldwork asks, of how many,
  and which object batteries a Sociomap can be drawn from. Content it cannot use
  is a :class:`CompileProblem`, never a guess.
* :func:`assess_readiness` says, as a list of named checks, whether the
  specification can run **in AIA today**. These are AIA's structural rules,
  labelled as such. The 18.6.6 technical preflight (study-type slots, filter
  linting, the audience sufficiency gate) stays in /classic and is not claimed.

Where a rule follows the unit it says so, with the anchor, so a later port can be
checked against it: ``legacy/npc-panel-18.6.6/app/research_project.py``
(``normalize_project``, ``_normalize_question``) and ``dotaznik.py`` (``Otazka``).
What the unit does and this does not -- conditional routing (``filtr``),
familiarity pre-questions, study-type slots -- is refused by a readiness check
rather than silently skipped, because skipping it would put answers in the data
that no respondent would have been asked for.

No I/O.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Mapping
from enum import StrEnum
from typing import Any, Final, Literal

from pydantic import BaseModel, ConfigDict, StrictInt, model_validator

from .persona_topics import dimension_topic
from .pipeline import fingerprint
from .sociomap.metrics import ObjectRole

__all__ = [
    "AIA_READINESS_V1",
    "COMPILER_VERSION",
    "DIMENSIONS_AWAIT_DRAW",
    "DIMENSIONS_NEED_POPULATION",
    "DIMENSIONS_NOT_READ",
    "DIMENSIONS_NOT_TOPICS",
    "DONT_KNOW",
    "DRAW_NOT_COMPLETED",
    "FILTERS_AWAIT_DRAW",
    "FILTERS_NEED_POPULATION",
    "SAMPLE_SIZE_BOUNDS",
    "SELECTION_NOT_APPLIED",
    "TRACKED_SET_LIMITS",
    "CheckStatus",
    "CompileProblem",
    "Readiness",
    "ReadinessCheck",
    "ReadinessSpec",
    "ResearchSpecification",
    "SampleSizeLimits",
    "SpecBattery",
    "SpecObject",
    "SpecQuestion",
    "SpecSelection",
    "TrackedSetLimits",
    "assess_readiness",
    "compile_design",
    "prepare",
    "readiness_problems",
    "readiness_values",
    "selection_receipt",
    "settle_selection",
]

#: The compiler's own version: part of the specification's fingerprint.
COMPILER_VERSION: Final = "aia-research-compile-1"

#: The unit's "don't know" option (``dotaznik.py`` ``Otazka.volby``).
DONT_KNOW: Final = "Nevím / neodpovím"

#: ``PRODUCT_POLICY.json`` ``research_design.sample_size`` (hard_min, hard_max).
SAMPLE_SIZE_BOUNDS: Final = (20, 10000)

#: ``PRODUCT_POLICY.json`` ``research_design.tracked_set`` for a position map:
#: hard (min, max) and recommended (min, max).
TRACKED_SET_LIMITS: Final = ((3, 40), (4, 15))

#: The fewest items a tracked set may ever have: fewer give no map (an object map needs
#: three objects). A version may raise the hard minimum, never lower it below this.
_TRACKED_SET_FLOOR: Final = 3


class SampleSizeLimits(BaseModel):
    """The sample sizes a run may start with, both bounds included."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    min: StrictInt
    max: StrictInt


class TrackedSetLimits(BaseModel):
    """How many items one tracked set may have: outside ``min``-``max`` the design does not
    compile; outside the recommended range readiness warns."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    min: StrictInt
    max: StrictInt
    recommended_min: StrictInt
    recommended_max: StrictInt


class ReadinessSpec(BaseModel):
    """The limits AIA's readiness checks read (plan ``methodology-tab`` V1a), declared so a
    methodologist can store a version of them. The preset :data:`AIA_READINESS_V1` is the
    18.6.6 product policy above, bit for bit.

    A run pins the limits in force when it starts; its compile and preflight steps read the
    pin. They decide whether a run may start, never what it computes, so they are not part of
    a run's identity. A missing n always blocks, whatever the limits: that is code.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    methodology_version: str
    sample_size: SampleSizeLimits
    tracked_set: TrackedSetLimits


AIA_READINESS_V1: Final = ReadinessSpec(
    methodology_version="aia-readiness-1",
    sample_size=SampleSizeLimits(min=SAMPLE_SIZE_BOUNDS[0], max=SAMPLE_SIZE_BOUNDS[1]),
    tracked_set=TrackedSetLimits(
        min=TRACKED_SET_LIMITS[0][0],
        max=TRACKED_SET_LIMITS[0][1],
        recommended_min=TRACKED_SET_LIMITS[1][0],
        recommended_max=TRACKED_SET_LIMITS[1][1],
    ),
)


def readiness_problems(spec: ReadinessSpec) -> dict[str, str]:
    """Every rule a set of limits breaks, by the field it is read at; empty when none.

    Whole numbers of at least 1; each minimum below its maximum; a tracked set never under
    three items; the recommended range inside the hard one."""
    problems: dict[str, str] = {}
    n, s = spec.sample_size, spec.tracked_set
    for path, value in (
        ("sample_size.min", n.min),
        ("sample_size.max", n.max),
        ("tracked_set.recommended_min", s.recommended_min),
        ("tracked_set.recommended_max", s.recommended_max),
    ):
        if value < 1:
            problems[path] = "musí být celé číslo, nejméně 1"
    if s.min < _TRACKED_SET_FLOOR:
        problems["tracked_set.min"] = (
            f"sada potřebuje nejméně {_TRACKED_SET_FLOOR} položky: méně mapu nedá"
        )
    if n.max <= n.min:
        problems["sample_size.max"] = "největší vzorek musí být větší než nejmenší"
    if s.max <= s.min:
        problems["tracked_set.max"] = "nejvíce položek musí být víc než nejméně"
    if s.recommended_max < s.recommended_min:
        problems["tracked_set.recommended_max"] = (
            "doporučené nejvíce nesmí být méně než doporučené nejméně"
        )
    if not s.min <= s.recommended_min:
        problems.setdefault(
            "tracked_set.recommended_min", "doporučený rozsah musí ležet uvnitř pevného"
        )
    if not s.recommended_max <= s.max:
        problems.setdefault(
            "tracked_set.recommended_max", "doporučený rozsah musí ležet uvnitř pevného"
        )
    return problems


def readiness_values(spec: ReadinessSpec) -> dict[str, Any]:
    """The limits' values without their name: two versions with the same values check the
    same, so this, not the name, is what a step's input fingerprint carries."""
    return spec.model_dump(mode="json", exclude={"methodology_version"})


QuestionType = Literal["vyber", "multi", "skala", "otevrena"]
_QUESTION_TYPES: Final = frozenset({"vyber", "multi", "skala", "otevrena"})


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class SpecQuestion(_Frozen):
    """One question a respondent answers. ``options`` already includes "don't know"."""

    id: str
    section_id: str
    text: str
    typ: QuestionType
    options: tuple[str, ...] = ()
    scale: tuple[int, int] | None = None
    allow_dont_know: bool = False
    has_filter: bool = False
    #: The design declared this scale question a Sociomap rating item (``sociomap_rating``):
    #: it enters every person's min-max (audit F2) beside the tracked sets' items. Never
    #: inferred from the type: a numeric question is a descriptor unless declared.
    rating_item: bool = False
    #: The research questions the design says this question measures (``research_questions``),
    #: by their text as the plan states them. A link is a declaration, never inferred; one
    #: that names no stated research question is the trace's to report, not the compiler's.
    research_questions: tuple[str, ...] = ()

    @model_validator(mode="after")
    def _shape(self) -> SpecQuestion:
        if self.typ in ("vyber", "multi") and len(self.options) < 2:
            raise ValueError(f"{self.id}: a choice question needs at least two options")
        if self.typ == "skala" and self.scale is None:
            raise ValueError(f"{self.id}: a scale question needs its scale")
        if self.rating_item and self.typ != "skala":
            raise ValueError(f"{self.id}: only a scale question can be a rating item")
        return self


class SpecObject(_Frozen):
    id: str
    label: str


class SpecBattery(_Frozen):
    """A tracked object set: every object rated on one scale by the same respondents.

    Each object's rating is one question in fieldwork, ``question_id`` below; a
    Sociomap is drawn from the respondents x objects matrix of those ratings.
    """

    id: str
    title: str
    family: str
    question_template: str
    scale: tuple[int, int]
    scale_labels: tuple[str, str]
    objects: tuple[SpecObject, ...]
    familiarity_required: bool
    output_type: str
    #: The objects the design declared context (SECONDARY, ``context_objects``): mapped and
    #: related, never in a PRIMARY score or the object terrain (audit F8). Every other
    #: object is PRIMARY.
    context_objects: tuple[str, ...] = ()
    #: Whether the design declared the roles at all; ``False`` is "every object PRIMARY
    #: because nothing was declared", which the artifact says.
    roles_declared: bool = False
    #: The research questions the design says this set measures, as :class:`SpecQuestion`'s.
    research_questions: tuple[str, ...] = ()

    @model_validator(mode="after")
    def _roles(self) -> SpecBattery:
        ids = {o.id for o in self.objects}
        unknown = sorted(set(self.context_objects) - ids)
        if unknown:
            raise ValueError(f"{self.id}: context objects that are not in the set: {unknown}")
        if self.context_objects and set(self.context_objects) == ids:
            raise ValueError(f"{self.id}: a set needs at least one PRIMARY object")
        return self

    def question_id(self, obj: SpecObject) -> str:
        return f"{self.id}_obj_{obj.id}"

    def object_roles(self) -> dict[str, str]:
        """Every object's role by id: SECONDARY if declared context, else PRIMARY."""
        context = set(self.context_objects)
        return {
            o.id: (ObjectRole.SECONDARY if o.id in context else ObjectRole.PRIMARY).value
            for o in self.objects
        }


#: Why a selection is recorded but not applied: nothing in AIA can apply it yet.
SELECTION_NOT_APPLIED: Final = (
    "no dimension materialization or population binding exists in AIA yet: the selected "
    "dimensions and audience filters are recorded with the run and are not applied to its "
    "respondents (plan sociomap-formula-corrections § 8.2, I1)"
)


class SpecSelection(_Frozen):
    """The respondent context the design selected: its dimensions and audience filters.

    Recorded so that two designs differing only here never compile to one specification,
    and so the run says what it was asked for. ``applied`` is whether the run's
    respondents were drawn under it; no source can do that yet, so it is ``False`` with
    the reason, never a claim that the selection shaped the data.
    """

    #: ``persona_dimensions.approved`` as the design stores it: ids, in order, once each.
    #: An empty approval is empty: the screen's recommended refill is not invented here.
    dimensions: tuple[str, ...]
    #: ``audience.filters`` with every empty value (``[]``, ``""``, ``null``, ``{}``) left
    #: out, keys sorted: what restricts the audience, and nothing that does not.
    audience_filters: dict[str, Any]
    applied: bool
    reason: str


class ResearchSpecification(_Frozen):
    """What a research run executes, compiled from one Design Revision."""

    compiler_version: str
    title: str
    n: int | None
    questions: tuple[SpecQuestion, ...]
    batteries: tuple[SpecBattery, ...]
    audience: dict[str, Any]
    #: What the design selected for its respondents; ``None`` when it selected nothing.
    selection: SpecSelection | None = None

    def fingerprint(self) -> str:
        """The specification's identity. A declaration a design does not make (a rating
        item, object roles) is left out, so a specification compiled before those
        declarations existed keeps the fingerprint it always had."""
        body = self.model_dump(mode="json")
        for question in body["questions"]:
            if not question["rating_item"]:
                del question["rating_item"]
            if not question["research_questions"]:
                del question["research_questions"]
        for battery in body["batteries"]:
            if not battery["roles_declared"]:
                del battery["roles_declared"]
                del battery["context_objects"]
            if not battery["research_questions"]:
                del battery["research_questions"]
        if body["selection"] is None:
            del body["selection"]
        return fingerprint(body)

    def rating_questions(self) -> tuple[SpecQuestion, ...]:
        """The standalone scale questions the design declared Sociomap rating items."""
        return tuple(q for q in self.questions if q.rating_item)

    def battery_questions(self) -> tuple[str, ...]:
        return tuple(b.question_id(o) for b in self.batteries for o in b.objects)


class CompileProblem(_Frozen):
    """Why part of the design cannot be compiled. ``where`` names the section/question."""

    code: str
    where: str
    message: str


class CheckStatus(StrEnum):
    PASS = "PASS"
    WARN = "WARN"
    FAIL = "FAIL"


class ReadinessCheck(_Frozen):
    id: str
    status: CheckStatus
    message: str


class Readiness(_Frozen):
    """Whether a specification can run in AIA, as named checks. Ready means no FAIL."""

    rules: str
    ready: bool
    checks: tuple[ReadinessCheck, ...]


# --------------------------------------------------------------------------- #
# compile
# --------------------------------------------------------------------------- #


def _text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value if value is not None else "")).strip()


def _slug(value: str, prefix: str) -> str:
    """Lower-case ASCII with underscores. AIA's rule; the unit's ``slugify`` may differ."""
    folded = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-z0-9]+", "_", folded.lower()).strip("_")
    if not slug:
        return prefix
    return f"{prefix}_{slug}" if slug[0].isdigit() else slug


def _unique(base: str, used: set[str]) -> str:
    candidate, i = base, 2
    while candidate in used:
        candidate, i = f"{base}_{i}", i + 1
    used.add(candidate)
    return candidate


def _scale(raw: Any, default: tuple[int, int]) -> tuple[int, int] | None:
    values = list(raw) if isinstance(raw, list | tuple) else list(default)
    if len(values) < 2:
        values = list(default)
    try:
        low, high = int(values[0]), int(values[1])
    except (TypeError, ValueError):
        return None
    return (low, high) if low < high else None


def _links(
    raw: dict[str, Any], where: str, problems: list[CompileProblem]
) -> tuple[str, ...] | None:
    """The research questions an item says it measures: texts, whitespace collapsed, once
    each, in order. Absent is none; anything but a list of texts is a problem, never guessed."""
    declared = raw.get("research_questions")
    if declared is None:
        return ()
    if not isinstance(declared, list) or not all(isinstance(x, str) for x in declared):
        problems.append(
            CompileProblem(
                code="invalid_research_question_links",
                where=where,
                message=f"{where}: výzkumné otázky položky musí být seznam textů.",
            )
        )
        return None
    return tuple(dict.fromkeys(t for t in (_text(x) for x in declared) if t))


def _question(
    raw: Any, *, section_id: str, ordinal: int, used: set[str], problems: list[CompileProblem]
) -> SpecQuestion | None:
    where = f"{section_id}#{ordinal}"
    if not isinstance(raw, dict):
        problems.append(
            CompileProblem(
                code="question_not_object", where=where, message="Otázka musí být objekt."
            )
        )
        return None
    typ = _text(raw.get("typ") or "vyber")
    if typ not in _QUESTION_TYPES:
        problems.append(
            CompileProblem(
                code="unknown_question_type", where=where, message=f"Neznámý typ otázky: {typ}"
            )
        )
        return None
    text = _text(raw.get("text"))
    if not text:
        problems.append(
            CompileProblem(code="question_without_text", where=where, message="Otázka nemá text.")
        )
        return None
    qid = _unique(_slug(_text(raw.get("id")) or f"{section_id}_{ordinal}", "q"), used)
    allow_dont_know = bool(raw.get("povolit_nevim", False))  # research_project.py:155
    options: tuple[str, ...] = ()
    scale: tuple[int, int] | None = None
    if typ in ("vyber", "multi"):
        cats = [_text(x) for x in (raw.get("kategorie") or raw.get("volby") or []) if _text(x)]
        cats = list(dict.fromkeys(cats))[:24]  # research_project.py:139-143
        if len(cats) < 2:
            problems.append(
                CompileProblem(
                    code="too_few_categories",
                    where=qid,
                    message=f"{qid}: výběrová otázka potřebuje alespoň 2 kategorie.",
                )
            )
            return None
        options = tuple(cats) + ((DONT_KNOW,) if allow_dont_know else ())
    elif typ == "skala":
        scale = _scale(raw.get("skala"), (1, 10))
        if scale is None:
            problems.append(
                CompileProblem(
                    code="invalid_scale",
                    where=qid,
                    message=f"{qid}: škála musí mít dvě celá čísla, od menšího k většímu.",
                )
            )
            return None
    rating_item = raw.get("sociomap_rating") is True
    if rating_item and typ != "skala":
        problems.append(
            CompileProblem(
                code="rating_item_not_scale",
                where=qid,
                message=f"{qid}: položkou pro Sociomapu může být jen škálová otázka.",
            )
        )
        return None
    links = _links(raw, qid, problems)
    if links is None:
        return None
    return SpecQuestion(
        id=qid,
        section_id=section_id,
        text=text,
        typ=typ,
        options=options,
        scale=scale,
        allow_dont_know=allow_dont_know,
        has_filter=bool(_text(raw.get("filtr"))),
        rating_item=rating_item,
        research_questions=links,
    )


def _battery(
    raw: dict[str, Any],
    *,
    section_id: str,
    title: str,
    problems: list[CompileProblem],
    limits: TrackedSetLimits,
) -> SpecBattery | None:
    family = _text(raw.get("object_family") or raw.get("object_type"))  # research_project.py:318
    if not family:
        problems.append(
            CompileProblem(
                code="battery_without_family",
                where=section_id,
                message=f"{title}: pojmenuj typ sledovaných položek (např. média, emoce, značky).",
            )
        )
        return None
    labels = list(dict.fromkeys(_text(x) for x in (raw.get("objects") or []) if _text(x)))
    hard_min, hard_max = limits.min, limits.max
    if not hard_min <= len(labels) <= hard_max:
        problems.append(
            CompileProblem(
                code="battery_size",
                where=section_id,
                message=(
                    f"{title}: sada potřebuje {hard_min}\u2013{hard_max} srovnatelných položek, "
                    f"má {len(labels)}."
                ),
            )
        )
        return None
    scale = _scale(raw.get("scale"), (1, 10))
    if scale is None:
        problems.append(
            CompileProblem(
                code="invalid_scale", where=section_id, message=f"{title}: neplatná škála."
            )
        )
        return None
    template = _text(raw.get("object_question") or "Jak hodnotíte položku {object}?")
    if "{object}" not in template:  # research_project.py:330-332
        template = template.rstrip(" ?") + " {object}?"
    scale_labels = [_text(x) for x in (raw.get("scale_labels") or [])][:2]
    if len(scale_labels) != 2 or not all(scale_labels):
        scale_labels = ["vůbec", "velmi"]
    used: set[str] = set()
    objects = tuple(
        SpecObject(id=_unique(_slug(label, "o"), used), label=label) for label in labels
    )
    output_type = _text(raw.get("output_type") or "pozicni_mapa")
    roles_declared = "context_objects" in raw
    declared = raw.get("context_objects") if roles_declared else []
    context_labels = [
        _text(x) for x in (declared if isinstance(declared, list) else []) if _text(x)
    ]
    by_label = {o.label: o.id for o in objects}
    unknown = [label for label in context_labels if label not in by_label]
    if roles_declared and not isinstance(declared, list):
        unknown = [str(declared)]
    if unknown:
        problems.append(
            CompileProblem(
                code="unknown_context_object",
                where=section_id,
                message=f"{title}: kontextové položky nejsou v sadě: {', '.join(unknown)}.",
            )
        )
        return None
    context = tuple(dict.fromkeys(by_label[label] for label in context_labels))
    if context and len(context) == len(objects):
        problems.append(
            CompileProblem(
                code="no_primary_object",
                where=section_id,
                message=f"{title}: sada potřebuje alespoň jednu hlavní (ne kontextovou) položku.",
            )
        )
        return None
    links = _links(raw, section_id, problems)
    if links is None:
        return None
    return SpecBattery(
        id=section_id,
        title=title,
        family=family,
        question_template=template,
        scale=scale,
        scale_labels=(scale_labels[0], scale_labels[1]),
        objects=objects,
        familiarity_required=bool(raw.get("familiarity_required", False)),
        output_type=output_type
        if output_type in {"pozicni_mapa", "segmentace", "lovebrand", "test_konceptu"}
        else "pozicni_mapa",
        context_objects=context,
        roles_declared=roles_declared,
        research_questions=links,
    )


def compile_design(
    content: dict[str, Any], *, limits: ReadinessSpec = AIA_READINESS_V1
) -> tuple[ResearchSpecification | None, tuple[CompileProblem, ...]]:
    """Compile a design, or say exactly what stops it. Never both a spec and a problem.

    ``limits`` gives the hard size of a tracked set: a run compiles under the limits it
    pinned. The default, the preset, is the code's; a caller compiling for a run passes the
    run's pin."""
    problems: list[CompileProblem] = []
    questions: list[SpecQuestion] = []
    batteries: list[SpecBattery] = []
    section_ids: set[str] = set()
    question_ids: set[str] = set()
    for i, sec in enumerate(content.get("sections") or [], start=1):
        if not isinstance(sec, dict):
            continue
        kind = _text(sec.get("type") or "questions")
        if kind not in ("questions", "object_battery"):
            continue  # research_project.py:301-303: unknown section types are not part of the study
        sid = _unique(
            _slug(_text(sec.get("id") or sec.get("title")) or f"sekce_{i}", "sec"), section_ids
        )
        title = _text(sec.get("title")) or (
            "Sledovaná sada" if kind == "object_battery" else f"Blok {i}"
        )
        if kind == "questions":
            for qi, q in enumerate(sec.get("questions") or [], start=1):
                compiled = _question(
                    q, section_id=sid, ordinal=qi, used=question_ids, problems=problems
                )
                if compiled is not None:
                    questions.append(compiled)
        else:
            battery = _battery(
                sec, section_id=sid, title=title, problems=problems, limits=limits.tracked_set
            )
            if battery is not None:
                batteries.append(battery)
    # A respondent's answers are kept by item id, a set's objects under
    # "<set>_obj_<object>": a question whose id is one of those would share its column.
    item_ids = {b.question_id(o) for b in batteries for o in b.objects}
    for q in questions:
        if q.id in item_ids:
            problems.append(
                CompileProblem(
                    code="item_id_collision",
                    where=q.id,
                    message=(
                        f"{q.id}: otázka má stejné id jako položka sledované sady; "
                        "přejmenujte ji, jinak by se jejich odpovědi slily."
                    ),
                )
            )
    if not questions and not batteries and not problems:
        problems.append(
            CompileProblem(
                code="empty_questionnaire",
                where="sections",
                message="Dotazník je prázdný. Přidejte alespoň jednu otázku nebo sledovanou sadu.",
            )
        )
    if problems:
        return None, tuple(problems)
    raw_n = content.get("n")
    n = raw_n if isinstance(raw_n, int) and not isinstance(raw_n, bool) else None
    raw_audience = content.get("audience")
    audience: dict[str, Any] = raw_audience if isinstance(raw_audience, dict) else {}
    selection = _selection(content, audience)
    spec = ResearchSpecification(
        compiler_version=COMPILER_VERSION,
        title=_text(content.get("title")) or "Výzkum",
        n=n,
        questions=tuple(questions),
        batteries=tuple(batteries),
        audience={
            "source_mode": _text(audience.get("source_mode")) or "population",
            "strategy": _text(audience.get("strategy")) or "population",
            "has_filters": bool(audience.get("filters")),
        },
        selection=selection,
    )
    return spec, ()


def _filter_value(value: Any) -> Any:
    """A filter value with its empty parts left out; ``None`` when nothing is left."""
    if isinstance(value, dict):
        kept = {
            str(k): v for k, raw in sorted(value.items()) if (v := _filter_value(raw)) is not None
        }
        return kept or None
    if isinstance(value, list | tuple):
        kept_items = [v for raw in value if (v := _filter_value(raw)) is not None]
        return kept_items or None
    if isinstance(value, str):
        return value.strip() or None
    if value is None or isinstance(value, bool | int | float):
        return value
    return str(value)


def _selection(content: dict[str, Any], audience: dict[str, Any]) -> SpecSelection | None:
    """The design's selected dimensions and audience filters, or ``None`` for neither."""
    persona = content.get("persona_dimensions")
    approved = persona.get("approved") if isinstance(persona, dict) else None
    dimensions = tuple(
        dict.fromkeys(
            _text(d) for d in (approved if isinstance(approved, list) else []) if _text(d)
        )
    )
    raw_filters = audience.get("filters")
    filters = _filter_value(raw_filters) if isinstance(raw_filters, dict) else None
    if not dimensions and not filters:
        return None
    return SpecSelection(
        dimensions=dimensions,
        audience_filters=filters or {},
        applied=False,
        reason=SELECTION_NOT_APPLIED,
    )


#: Why a run started before 5c applied none of its design's dimensions: no persona read them
#: then. Kept so that such a run's record still reads as what it was.
DIMENSIONS_NOT_READ: Final = "dimensions_not_read_by_personas"
#: Why a run's selected dimensions are not applied: they are a panel persona's topic allowlist
#: (``panel_persona.persona_allowlist``, 5c), and this run's respondents are the fictional roster.
DIMENSIONS_NEED_POPULATION: Final = "dimensions_need_population_draw"
#: Why a panel run's dimensions are not applied yet: its personas are built when fieldwork draws
#: its sample, after the run records its selection (settled from the fieldwork step, as filters).
DIMENSIONS_AWAIT_DRAW: Final = "dimensions_await_population_draw"
#: Why a drawn run applied none of its dimensions: no selected id is a persona topic
#: (``persona_topics.dimension_topic``), so the allowlist let no topic through (18.6.6's set test).
DIMENSIONS_NOT_TOPICS: Final = "dimensions_not_persona_topics"
#: Why a run did not apply its design's audience filters: only a draw from the population does,
#: and this run's respondents are the fictional roster.
FILTERS_NEED_POPULATION: Final = "filters_need_population_draw"
#: Why a panel run's filters are not applied yet: they apply when fieldwork draws its sample,
#: and a run records its selection at start, before that (the reader settles it from the
#: fieldwork step: ``routers/research.py`` ``_selection``).
FILTERS_AWAIT_DRAW: Final = "filters_await_population_draw"


#: A panel run that ended before its population draw succeeded: no respondent was drawn under
#: the filters, and no persona read the dimensions.
DRAW_NOT_COMPLETED: Final = "population_draw_not_completed"


def settle_selection(selection: Mapping[str, Any], *, drawn: bool, ended: bool) -> dict[str, Any]:
    """A run's recorded selection (:func:`selection_receipt`), its filters and dimensions settled
    by its fieldwork (5b, 5c): a panel run's await the draw until fieldwork has drawn respondents
    from the population, the step that applies both; a run that ended without it never drew
    anyone, and says so. ``drawn``: the fieldwork step succeeded with data drawn from the
    population. One rule for every reader -- the run screen and the report's method chapter."""
    out = dict(selection)
    for part, awaiting in (("filters", FILTERS_AWAIT_DRAW), ("dimensions", DIMENSIONS_AWAIT_DRAW)):
        if out.get(f"{part}_reason") != awaiting:
            continue
        if (
            drawn
            and part == "dimensions"
            and set(out.get("dimensions_unmatched") or ()) >= set(out.get("dimensions") or ())
        ):
            # No selected id is a persona topic: the allowlist let nothing through (5c).
            out["dimensions_reason"] = DIMENSIONS_NOT_TOPICS
        elif drawn:
            out[f"{part}_applied"] = True
            out[f"{part}_reason"] = None
        elif ended:
            out[f"{part}_reason"] = DRAW_NOT_COMPLETED
    return out


def selection_receipt(spec: ResearchSpecification, *, population_draw: bool) -> dict[str, Any]:
    """What a run records about its design's selection (plan run-recovery-and-truth 5b): the
    dimensions and audience filters it selected, and whether each reached the respondents.

    ``population_draw``: the run's respondents will be drawn from its population (the panel
    source), which is the only thing that applies the filters (``panel_source.panel_plans``).
    It is recorded at start, before any draw, so a panel run's filters await the draw
    (``FILTERS_AWAIT_DRAW``), and so do its dimensions, which its personas read as their topic
    allowlist (5c, ``DIMENSIONS_AWAIT_DRAW``); none is ever recorded applied here. An applied
    flag is never true without the code that applies it having run, and a reason accompanies
    every one that is false. ``dimensions_unmatched`` names each selected id that is no persona
    topic: the allowlist lets none of its topics through, so it never reaches a respondent.
    """
    selection = spec.selection
    dimensions = list(selection.dimensions) if selection is not None else []
    filters = dict(selection.audience_filters) if selection is not None else {}
    reason = (
        (FILTERS_AWAIT_DRAW if population_draw else FILTERS_NEED_POPULATION) if filters else None
    )
    return {
        "dimensions": dimensions,
        "dimensions_unmatched": [d for d in dimensions if dimension_topic(d) is None],
        "dimensions_applied": False,
        "dimensions_reason": (
            (DIMENSIONS_AWAIT_DRAW if population_draw else DIMENSIONS_NEED_POPULATION)
            if dimensions
            else None
        ),
        "audience_filters": filters,
        "filters_applied": False,
        "filters_reason": reason,
    }


# --------------------------------------------------------------------------- #
# readiness
# --------------------------------------------------------------------------- #

READINESS_RULES: Final = "aia-structural-readiness-1"


def assess_readiness(
    spec: ResearchSpecification,
    *,
    pair_n_min: int,
    filters_applied: bool = False,
    limits: ReadinessSpec = AIA_READINESS_V1,
) -> Readiness:
    """AIA's structural readiness checks. Ready means no check FAILed.

    ``limits`` are the sample size and recommended set size the checks hold the design to
    (plan ``methodology-tab`` V1a): a run's pin, the version in force for a check now, the
    preset by default.

    ``pair_n_min`` is how many respondents each pair of a tracked set needs, as the run
    will compute it: the side tables' ``n_min`` of the methods it pins
    (``research_sociomap.side_tables_for``; plan ``methodology-tab`` S2c). It has no
    default: a warning that read the code's value would contradict the methodology in force.
    """
    checks: list[ReadinessCheck] = []

    def check(check_id: str, status: CheckStatus, message: str) -> None:
        checks.append(ReadinessCheck(id=check_id, status=status, message=message))

    low, high = limits.sample_size.min, limits.sample_size.max
    if spec.n is None:
        check("sample_size", CheckStatus.FAIL, "Velikost vzorku (n) není zadaná.")
    elif not low <= spec.n <= high:
        check(
            "sample_size",
            CheckStatus.FAIL,
            f"Velikost vzorku {spec.n} je mimo rozsah {low}\u2013{high}.",
        )
    else:
        check("sample_size", CheckStatus.PASS, f"n = {spec.n}.")

    asked = len(spec.questions) + len(spec.battery_questions())
    check(
        "questionnaire",
        CheckStatus.PASS,
        f"{len(spec.questions)} otázek, {len(spec.batteries)} sledovaných sad "
        f"({asked} položek k zodpovězení).",
    )

    filtered = [q.id for q in spec.questions if q.has_filter]
    if filtered:
        check(
            "conditional_questions",
            CheckStatus.FAIL,
            "Podmíněné otázky (filtr) AIA zatím neumí položit jen těm, kdo mají odpovídat: "
            + ", ".join(filtered)
            + ". Spusťte tento návrh v klasickém rozhraní.",
        )
    else:
        check("conditional_questions", CheckStatus.PASS, "Žádná podmíněná otázka.")

    familiarity = [b.id for b in spec.batteries if b.familiarity_required]
    if familiarity:
        check(
            "battery_familiarity",
            CheckStatus.FAIL,
            "Sady s povinnou znalostí položek AIA zatím neumí: " + ", ".join(familiarity) + ".",
        )
    rec_min, rec_max = limits.tracked_set.recommended_min, limits.tracked_set.recommended_max
    for b in spec.batteries:
        if not rec_min <= len(b.objects) <= rec_max:
            check(
                f"battery_size:{b.id}",
                CheckStatus.WARN,
                f"{b.title}: {len(b.objects)} položek; doporučeno {rec_min}\u2013{rec_max}.",
            )
    if spec.batteries:
        check(
            "sociomap_input",
            CheckStatus.PASS,
            # Whether a map may reach a client is the Sociomap register's, for the method that
            # computed it, read when the map is read (domain/sociomap_register.py), never here.
            f"{len(spec.batteries)} sad pro Sociomapu.",
        )
        # Structural readiness to collect answers is not support for a map: a pair needs
        # n_min respondents who rated both (audit F3), counted after missing answers and
        # straight-liners. Below it every pair is UNKNOWN and the object map says
        # NOT_MAPPABLE; this says so before anything is paid for (plan § 8.2, I3).
        if spec.n is not None and spec.n < pair_n_min:
            check(
                "sociomap_support",
                CheckStatus.WARN,
                f"n = {spec.n} je pod {pair_n_min} respondenty, které podle platné metodiky "
                "potřebuje každý pár položek: žádný vztah nebude známý a mapa položek nevznikne.",
            )
        else:
            check(
                "sociomap_support",
                CheckStatus.PASS,
                f"n stačí na {pair_n_min} respondentů na pár, pokud odpovědi "
                "nechybějí; skutečnou oporu každého páru uvádí mapa.",
            )
    else:
        check("sociomap_input", CheckStatus.WARN, "Bez sledované sady nevznikne Sociomapa.")

    # Dimensions are a panel persona's topic allowlist (5c): applied only when the run draws its
    # respondents from the population, the same pin that applies the filters below.
    if spec.selection is not None and spec.selection.dimensions:
        dims = spec.selection.dimensions
        unknown = [d for d in dims if dimension_topic(d) is None]
        if filters_applied:
            check(
                "dimensions",
                CheckStatus.WARN if unknown else CheckStatus.PASS,
                "Vybrané dimenze ("
                + ", ".join(dims)
                + ") určí témata, o kterých AI respondenti z populace mluví ve svém profilu."
                + (
                    " Tyto nejsou tématem persony a žádné téma nepropustí: "
                    + ", ".join(unknown)
                    + "."
                    if unknown
                    else ""
                ),
            )
        else:
            check(
                "dimensions",
                CheckStatus.WARN,
                "Vybrané dimenze ("
                + ", ".join(dims)
                + ") se uplatní jen u AI respondentů z populace;"
                " fiktivní respondenti je nepoužijí.",
            )
    # ``filters_applied``: the run is pinned to draw its respondents from the population, and
    # draws them under the design's filters (plan panel-grounded-respondents 6d). Otherwise
    # nothing applies them, and the check says so.
    if spec.audience.get("source_mode") != "population":
        check(
            "audience",
            CheckStatus.WARN,
            (
                "AIA nemá vlastní publikum ani speciální panel; běh vybere respondenty z "
                "populace" + (" pod uloženými filtry." if spec.audience.get("has_filters") else ".")
            )
            if filters_applied
            else "AIA zatím nepoužije filtry ani vlastní publikum; běh počítá s celou populací.",
        )
    elif spec.audience.get("has_filters"):
        if filters_applied:
            check(
                "audience",
                CheckStatus.PASS,
                "Filtry se uplatní při výběru respondentů z populace.",
            )
        else:
            check(
                "audience",
                CheckStatus.WARN,
                "AIA zatím nepoužije filtry ani vlastní publikum; běh počítá s celou populací.",
            )
    else:
        check("audience", CheckStatus.PASS, "Celá populace.")

    return Readiness(
        rules=READINESS_RULES,
        ready=not any(c.status is CheckStatus.FAIL for c in checks),
        checks=tuple(checks),
    )


def prepare(
    content: dict[str, Any],
    *,
    pair_n_min: int,
    filters_applied: bool = False,
    limits: ReadinessSpec = AIA_READINESS_V1,
) -> tuple[ResearchSpecification | None, Readiness]:
    """Compile and assess in one call. A design that does not compile is not ready.
    ``pair_n_min``, ``filters_applied`` and ``limits`` as :func:`assess_readiness` takes
    them; the design compiles under the same ``limits``."""
    spec, problems = compile_design(content, limits=limits)
    if spec is None:
        return None, Readiness(
            rules=READINESS_RULES,
            ready=False,
            checks=tuple(
                ReadinessCheck(
                    id=f"compile:{p.code}:{p.where}", status=CheckStatus.FAIL, message=p.message
                )
                for p in problems
            ),
        )
    return spec, assess_readiness(
        spec, pair_n_min=pair_n_min, filters_applied=filters_applied, limits=limits
    )
