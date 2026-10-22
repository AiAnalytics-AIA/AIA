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
from collections.abc import Mapping, Sequence
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
    "SCALE_LABEL_MAX",
    "SELECTION_NOT_APPLIED",
    "TRACKED_SET_LIMITS",
    "CheckStatus",
    "CompileProblem",
    "Readiness",
    "ReadinessCheck",
    "ReadinessSpec",
    "ResearchSpecification",
    "SampleSizeLimits",
    "SampleSizeProblem",
    "SpecBattery",
    "SpecObject",
    "SpecQuestion",
    "SpecSelection",
    "TrackedSetLimits",
    "assess_readiness",
    "compile_design",
    "keep_point_labels",
    "labelled_points",
    "prepare",
    "readiness_problems",
    "readiness_values",
    "sample_size_problem",
    "scale_points",
    "selection_receipt",
    "settle_selection",
]

#: The compiler's own version: part of the specification's fingerprint. ``-2`` compiles a
#: scale's verbal labels (input-interactions 3b); a specification ``-1`` stored is read as
#: stored, held to the revision it records, never recompiled under ``-2``
#: (``application.analysis_results.native_sources``).
COMPILER_VERSION: Final = "aia-research-compile-3"

#: The unit's "don't know" option (``dotaznik.py`` ``Otazka.volby``).
DONT_KNOW: Final = "Nevím / neodpovím"

#: ``PRODUCT_POLICY.json`` ``research_design.sample_size`` (hard_min, hard_max).
SAMPLE_SIZE_BOUNDS: Final = (20, 10000)

#: ``PRODUCT_POLICY.json`` ``research_design.tracked_set`` for a position map:
#: hard (min, max) and recommended (min, max).
TRACKED_SET_LIMITS: Final = ((3, 40), (4, 15))

#: The longest verbal label one point of a scale may carry (input-interactions 3b).
SCALE_LABEL_MAX: Final = 60

#: The fewest items a tracked set may ever have: fewer give no map (an object map needs
#: three objects). A version may raise the hard minimum, never lower it below this.
_TRACKED_SET_FLOOR: Final = 3


class SampleSizeLimits(BaseModel):
    """The sample sizes a run may start with, both bounds included."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    min: StrictInt
    max: StrictInt


class SampleSizeProblem(StrEnum):
    """Why a sample size cannot start a run (:func:`sample_size_problem`)."""

    #: No whole number of respondents is set.
    MISSING = "sample_size_missing"
    #: A whole number outside ``min``-``max`` of the limits in force.
    OUT_OF_RANGE = "sample_size_out_of_range"


def sample_size_problem(n: object, limits: SampleSizeLimits) -> SampleSizeProblem | None:
    """The one rule for a valid n (plan ``run-qc-and-checkpoint`` RQC9): a whole number within
    ``limits``, both bounds included; ``None`` when it is one.

    Readiness, the Research Lead's ``set_n`` (grounded at its turn and checked again at its
    accept) and the API's ``GET …/research/limits``, which the web reads instead of a copy of
    its own, all ask this. Nothing clamps: a value out of range is refused, never moved to
    the nearest bound. A boolean is not a count, nor is a fractional or textual number.
    """
    if not isinstance(n, int) or isinstance(n, bool):
        return SampleSizeProblem.MISSING
    if not limits.min <= n <= limits.max:
        return SampleSizeProblem.OUT_OF_RANGE
    return None


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


def scale_points(scale: tuple[int, int]) -> int:
    """How many points a scale has, both ends included."""
    return scale[1] - scale[0] + 1


def labelled_points(scale: tuple[int, int], labels: Sequence[str]) -> list[tuple[int, str]]:
    """Each labelled point of a scale with its label, low to high: the two ends when two
    labels were declared, else every point (``labels`` one per point)."""
    if not labels:
        return []
    low, high = scale
    if len(labels) == 2:
        return [(low, labels[0]), (high, labels[1])]
    return list(zip(range(low, high + 1), labels, strict=True))


def _labels_fit(labels: tuple[str, ...], scale: tuple[int, int] | None, where: str) -> None:
    """A scale's verbal labels are its two ends or one per point, low to high; nothing else."""
    if not labels:
        return
    if scale is None:
        raise ValueError(f"{where}: scale labels need a scale")
    if len(labels) not in (2, scale_points(scale)):
        raise ValueError(
            f"{where}: {len(labels)} scale labels for {scale_points(scale)} points; "
            "give the two ends or one label per point"
        )


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
    #: The scale's verbal labels as the design declared them (``popisky_skaly``): the two ends,
    #: or one per point, low to high. Empty when none were declared, and then absent from the
    #: fingerprint. Only a scale question carries them.
    scale_labels: tuple[str, ...] = ()

    @model_validator(mode="after")
    def _shape(self) -> SpecQuestion:
        if self.typ in ("vyber", "multi") and len(self.options) < 2:
            raise ValueError(f"{self.id}: a choice question needs at least two options")
        if self.typ == "skala" and self.scale is None:
            raise ValueError(f"{self.id}: a scale question needs its scale")
        if self.rating_item and self.typ != "skala":
            raise ValueError(f"{self.id}: only a scale question can be a rating item")
        if self.scale_labels and self.typ != "skala":
            raise ValueError(f"{self.id}: only a scale question carries scale labels")
        _labels_fit(self.scale_labels, self.scale, self.id)
        return self

    @property
    def end_labels(self) -> tuple[str, str] | None:
        """The labels of the scale's two ends, whichever form was declared; ``None`` for none."""
        if not self.scale_labels:
            return None
        return (self.scale_labels[0], self.scale_labels[-1])


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
    #: The scale's verbal labels: the two ends (``vůbec`` / ``velmi`` when the design named
    #: none), or one per point, low to high.
    scale_labels: tuple[str, ...]
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
    #: Develop's reading of the set's ends where it differs from :attr:`end_labels` (input-
    #: interactions 3b; ``None`` otherwise, and then absent from the fingerprint): the first
    #: two labels as written, or ``vůbec`` / ``velmi``. What respondents are told while the
    #: labels stay off the prompt, so a stored design sends what it always sent.
    develop_ends: tuple[str, str] | None = None

    @model_validator(mode="after")
    def _roles(self) -> SpecBattery:
        ids = {o.id for o in self.objects}
        unknown = sorted(set(self.context_objects) - ids)
        if unknown:
            raise ValueError(f"{self.id}: context objects that are not in the set: {unknown}")
        if self.context_objects and set(self.context_objects) == ids:
            raise ValueError(f"{self.id}: a set needs at least one PRIMARY object")
        if not self.scale_labels:
            raise ValueError(f"{self.id}: a set's scale needs its labels")
        _labels_fit(self.scale_labels, self.scale, self.id)
        return self

    @property
    def end_labels(self) -> tuple[str, str]:
        """The labels of the scale's two ends, whichever form was declared."""
        return (self.scale_labels[0], self.scale_labels[-1])

    @property
    def told_ends(self) -> tuple[str, str]:
        """The two ends a respondent is told while ``AIA_AI_SCALE_LABELS_IN_PROMPT`` is off,
        and the report and the map print: develop's reading (:func:`_develop_ends`), byte for
        byte. It differs from :attr:`end_labels` only for labels the new rule leaves out or a
        set labelled point by point, and is then stored as :attr:`develop_ends`."""
        return self.develop_ends or self.end_labels

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
            if not question["scale_labels"]:
                del question["scale_labels"]
        for battery in body["batteries"]:
            if not battery["roles_declared"]:
                del battery["roles_declared"]
                del battery["context_objects"]
            if not battery["research_questions"]:
                del battery["research_questions"]
            if battery["develop_ends"] is None:
                del battery["develop_ends"]
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


def _scale_end(value: Any) -> int | None:
    """One end of a scale as a whole number, or ``None``: 2.5 is refused, never truncated to 2
    (IA-2). A whole float (``5.0``) and a numeral (``"5"``) are the number they write; a
    boolean is not a number."""
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value) if value.is_integer() else None
    if isinstance(value, str):
        try:
            return int(value.strip())
        except ValueError:
            return None
    return None


def _scale(raw: Any, default: tuple[int, int]) -> tuple[int, int] | None:
    values = list(raw) if isinstance(raw, list | tuple) else list(default)
    if len(values) < 2:
        values = list(default)
    low, high = _scale_end(values[0]), _scale_end(values[1])
    if low is None or high is None:
        return None
    return (low, high) if low < high else None


def _develop_ends(raw: Any) -> tuple[str, str]:
    """A set's two ends exactly as develop compiled them before scale labels were read
    (``aia-research-compile-1``): the first two entries as text, ``vůbec`` / ``velmi`` unless
    both are there and not blank. Kept so that, with the labels off the prompt, a stored set
    sends its respondents what it always sent."""
    try:
        ends = [_text(x) for x in (raw or [])][:2]
    except TypeError:  # not iterable: develop's compile failed here; no design holds one
        ends = []
    if len(ends) != 2 or not all(ends):
        return ("vůbec", "velmi")
    return (ends[0], ends[1])


def _scale_labels(
    raw: Any, scale: tuple[int, int], *, where: str, instead: str, notes: list[CompileProblem]
) -> tuple[str, ...]:
    """A scale's verbal labels as declared: the two ends or one per point, low to high.

    ``()`` when none were declared (absent, an empty list, or every label blank), and also
    when they break the rule: a list of any other length, a blank, repeated or over-long
    label, anything but a list of texts. Such labels are left out -- nothing is padded, cut
    or guessed -- and a ``scale_labels_ignored`` note names why and what is used ``instead``
    (readiness WARNs with it). They never stop a design from compiling: one that compiled
    before the labels were read still does (input-interactions 3b; the editor refuses them
    at the field, ``scale-labels.ts`` ``labelProblem``)."""
    if raw is None:
        return ()
    why: str | None = None
    labels: list[str] = []
    if not isinstance(raw, list | tuple) or not all(isinstance(x, str) for x in raw):
        why = "popisky škály nejsou seznam textů"
    else:
        labels = [_text(x) for x in raw]
        if not any(labels):
            return ()
        points = scale_points(scale)
        if len(labels) not in (2, points):
            why = (
                f"škála {scale[0]}\u2013{scale[1]} má {points} bodů a popisků je "
                f"{len(labels)}; popište oba konce, nebo každý bod"
            )
        elif not all(labels):
            why = "popisek bodu škály je prázdný"
        elif len({label.casefold() for label in labels}) != len(labels):
            why = "dva body škály mají stejný popisek"
        elif any(len(label) > SCALE_LABEL_MAX for label in labels):
            why = f"popisek bodu škály má víc než {SCALE_LABEL_MAX} znaků"
    if why is not None:
        notes.append(
            CompileProblem(
                code="scale_labels_ignored",
                where=where,
                message=f"{where}: popisky škály se nepoužijí, protože {why}. {instead}",
            )
        )
        return ()
    return tuple(labels)


def _stored_range(raw: Any) -> tuple[int, int] | None:
    """A question's range as the editor reads it (``scale-labels.ts`` ``readRange``): two whole
    numbers, 0 <= low < high <= 100; ``None`` otherwise, never rounded or swapped."""
    if not isinstance(raw, list | tuple) or len(raw) != 2:
        return None
    low, high = raw
    if not all(type(x) is int for x in (low, high)):
        return None
    if low < 0 or high > 100 or low >= high:
        return None
    return (low, high)


def _point_labels(question: Mapping[str, Any]) -> tuple[tuple[int, int], list[str]] | None:
    """A scale question's labels when they are a valid label on every point of its range."""
    scale = _stored_range(question.get("skala"))
    raw = question.get("popisky_skaly")
    if question.get("typ") != "skala" or scale is None or scale_points(scale) <= 2:
        return None
    if not isinstance(raw, list) or len(raw) != scale_points(scale):
        return None
    notes: list[CompileProblem] = []
    if not _scale_labels(raw, scale, where="", instead="", notes=notes) or notes:
        return None
    return scale, list(raw)


def _fold(value: Any) -> str:
    return _text(value).casefold()


def keep_point_labels(rewritten: Any, stored: Any) -> Any:
    """A rewritten questionnaire with its scale questions' per-point labels kept.

    A rewrite whose contract carries a scale's two ends only (an agent's ``Question``, the
    classic optimiser's schema) would otherwise drop the inner labels a person gave every point,
    without a word (#559). A rewritten scale question with at most two labels and the same range
    as a stored question labelled validly on every point keeps the stored labels, when exactly
    one such stored question matches it: by id, else by wording, else by its two ends (folded).
    Anything else stays as the rewrite wrote it; nothing is guessed. ``rewritten`` and
    ``stored`` are lists of sections as stored; a value that is not one is returned as it is.
    The web keeps them by the same rule (``scale-labels.ts`` ``keepPointLabels``).
    """
    if not isinstance(rewritten, list):
        return rewritten
    kept: list[tuple[Mapping[str, Any], tuple[int, int], list[str]]] = []
    for section in stored if isinstance(stored, list) else []:
        questions = section.get("questions") if isinstance(section, Mapping) else None
        for q in questions if isinstance(questions, list) else []:
            point = _point_labels(q) if isinstance(q, Mapping) else None
            if point is not None:
                kept.append((q, *point))
    if not kept:
        return rewritten

    def kept_for(q: Mapping[str, Any]) -> list[str] | None:
        scale = _stored_range(q.get("skala"))
        raw = q.get("popisky_skaly")
        labels = [] if raw is None else raw
        if q.get("typ") != "skala" or scale is None or not isinstance(labels, list):
            return None
        if len(labels) > 2:
            return None
        same = [(s, lb) for s, sc, lb in kept if sc == scale]
        ends = [_fold(x) for x in labels] if len(labels) == 2 else None
        tiers = (
            lambda s, lb: q.get("id") is not None and s.get("id") == q.get("id"),
            lambda s, lb: (
                _fold(q.get("text")) != "" and _fold(s.get("text")) == _fold(q.get("text"))
            ),
            lambda s, lb: ends is not None and ends == [_fold(lb[0]), _fold(lb[-1])],
        )
        for tier in tiers:
            found = [lb for s, lb in same if tier(s, lb)]
            if len(found) == 1:
                return list(found[0])
            if found:
                return None
        return None

    out: list[Any] = []
    for section in rewritten:
        questions = section.get("questions") if isinstance(section, Mapping) else None
        if not isinstance(section, Mapping) or not isinstance(questions, list):
            out.append(section)
            continue
        changed = False
        new_questions: list[Any] = []
        for q in questions:
            labels = kept_for(q) if isinstance(q, Mapping) else None
            if labels is None:
                new_questions.append(q)
            else:
                changed = True
                new_questions.append({**q, "popisky_skaly": labels})
        out.append({**section, "questions": new_questions} if changed else section)
    return out


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
    raw: Any,
    *,
    section_id: str,
    ordinal: int,
    used: set[str],
    problems: list[CompileProblem],
    notes: list[CompileProblem],
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
    scale_labels: tuple[str, ...] = ()
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
        scale_labels = _scale_labels(
            raw.get("popisky_skaly"),
            scale,
            where=qid,
            instead="Respondenti uvidí jen čísla škály a zpráva popisky neuvede.",
            notes=notes,
        )
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
        scale_labels=scale_labels,
    )


def _battery(
    raw: dict[str, Any],
    *,
    section_id: str,
    title: str,
    problems: list[CompileProblem],
    notes: list[CompileProblem],
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
    told = _develop_ends(raw.get("scale_labels"))
    stated = _scale_labels(
        raw.get("scale_labels"),
        scale,
        where=section_id,
        instead=(
            f"Respondentům se konce škály posílají jako dosud („{told[0]}“ a „{told[1]}“); "
            "až se začnou posílat popisky bodů, popíší se jako „vůbec“ a „velmi“."
        ),
        notes=notes,
    )
    scale_labels = stated or ("vůbec", "velmi")
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
        scale_labels=scale_labels,
        develop_ends=None if told == (scale_labels[0], scale_labels[-1]) else told,
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
    content: dict[str, Any],
    *,
    limits: ReadinessSpec = AIA_READINESS_V1,
    notes: list[CompileProblem] | None = None,
) -> tuple[ResearchSpecification | None, tuple[CompileProblem, ...]]:
    """Compile a design, or say exactly what stops it. Never both a spec and a problem.

    ``limits`` gives the hard size of a tracked set: a run compiles under the limits it
    pinned. The default, the preset, is the code's; a caller compiling for a run passes the
    run's pin. ``notes``, when given, collects what was compiled around rather than refused
    (scale labels that break the rule: ``scale_labels_ignored``); readiness WARNs with them."""
    problems: list[CompileProblem] = []
    if notes is None:
        notes = []
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
                    q,
                    section_id=sid,
                    ordinal=qi,
                    used=question_ids,
                    problems=problems,
                    notes=notes,
                )
                if compiled is not None:
                    questions.append(compiled)
        else:
            battery = _battery(
                sec,
                section_id=sid,
                title=title,
                problems=problems,
                notes=notes,
                limits=limits.tracked_set,
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
        audience=_audience(audience),
        selection=selection,
    )
    return spec, ()


def _audience(audience: dict[str, Any]) -> dict[str, Any]:
    """The audience as the design stated it: its source and strategy, whether it narrowed, and
    (compiler 3, artifact-chain CHN5) the description and built-in subpanel a person gave, each
    only when given (the subpanel only on a population audience), so a design that states
    neither keeps the body it always had."""
    out: dict[str, Any] = {
        "source_mode": _text(audience.get("source_mode")) or "population",
        "strategy": _text(audience.get("strategy")) or "population",
        "has_filters": bool(audience.get("filters")),
    }
    if description := _text(audience.get("description")):
        out["description"] = description
    # A subpanel is a part of AIA's population. The audience step keeps the last one chosen
    # when the source moves outside it (OI-51), so it is the audience's only on a population.
    if out["source_mode"] == "population" and (subpanel := _text(audience.get("builtin_subpanel"))):
        out["builtin_subpanel"] = subpanel
    return out


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
    # Here, not at the top: report.numbers reaches evidence, which reaches this module.
    from .report.numbers import counted

    checks: list[ReadinessCheck] = []

    def check(check_id: str, status: CheckStatus, message: str) -> None:
        checks.append(ReadinessCheck(id=check_id, status=status, message=message))

    low, high = limits.sample_size.min, limits.sample_size.max
    problem = sample_size_problem(spec.n, limits.sample_size)
    if problem is SampleSizeProblem.MISSING:
        check("sample_size", CheckStatus.FAIL, "Velikost vzorku (n) není zadaná.")
    elif problem is SampleSizeProblem.OUT_OF_RANGE:
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
        f"{counted(len(spec.questions), 'otázka', 'otázky', 'otázek')}, "
        f"{counted(len(spec.batteries), 'sledovaná sada', 'sledované sady', 'sledovaných sad')} "
        f"({counted(asked, 'položka', 'položky', 'položek')} k zodpovězení).",
    )

    filtered = [q.id for q in spec.questions if q.has_filter]
    if filtered:
        check(
            "conditional_questions",
            CheckStatus.FAIL,
            "Podmíněné otázky (filtr) AIA zatím neumí položit jen těm, kdo mají odpovídat: "
            + ", ".join(filtered)
            + ". V Dotazníku u nich podmínku odeberte (otázku pak dostane každý), nebo je smažte.",
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
            f"{counted(len(spec.batteries), 'sada', 'sady', 'sad')} pro Sociomapu.",
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
    them; the design compiles under the same ``limits``. Labels compiled around are a WARN
    each, in words, never a FAIL."""
    notes: list[CompileProblem] = []
    spec, problems = compile_design(content, limits=limits, notes=notes)
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
    readiness = assess_readiness(
        spec, pair_n_min=pair_n_min, filters_applied=filters_applied, limits=limits
    )
    if not notes:
        return spec, readiness
    warned = tuple(
        ReadinessCheck(id=f"compile:{n.code}:{n.where}", status=CheckStatus.WARN, message=n.message)
        for n in notes
    )
    return spec, readiness.model_copy(update={"checks": (*readiness.checks, *warned)})
