"""Triangulation: who published a source, which sources are independent, which figures conflict.

Plan ``deep-research-web-search.md`` § 8.5, chunk 12. Three rules, each code's alone:

**Publisher identity** (:func:`publisher_identity`). A web source's publisher is the
register's publisher of its host (:mod:`.reputation`), else its registrable host --
the host's last two labels, without ``www.``. No public-suffix list is consulted, so
two publishers under one suffix of two labels (``a.co.uk``, ``b.co.uk``) read as one,
and so do two blogs on one platform. That error only ever *merges* publishers, so it
can cost a confirmation, never invent one. A Client Knowledge item is its own
publisher (``knowledge:<item>``).

**Independence** (:func:`independence_groups`). Two sources are one confirmation when
they have one publisher, or when their texts are one text: an exact or near
duplicate by the code filters (:mod:`.filters`: content key, then word-shingle
Jaccard at :class:`~.filters.NearDuplicateConfig`'s threshold). Syndicated copies of
one press release on three news sites are one group; the groups are connected
components, so a chain of copies is one group too. A finding's *independent*
confirmations are the other groups among its similar claims (``merge``), one per
group.

**Conflicts** (:func:`detect_conflicts`). Two findings state the same measure when
both name it (``measure_name``, compared as :func:`~.reputation.normalise_name`
folds it), in the same unit and the same geography, for overlapping periods
(:func:`period_span`). They conflict when their values, scaled, differ by more than
:class:`ConflictTolerance` allows: rounding (half a unit of the last stated decimal
of the coarser value, times its scale) plus an optional relative margin, zero by
default -- "beyond rounding" (§ 8.5). An attribute either side leaves unstated is
unknown, never equal: a finding without a measure name, unit, geography or a
placeable period is compared with nothing.

A conflict's likely **cause**, from the measures, first that holds:

* ``definition`` -- both state a population, or both a denominator, and they differ
  (a share of households against a share of people);
* ``basis`` -- both state a basis and they differ (preliminary against final,
  estimate or forecast against actual);
* ``period`` -- the periods overlap but are not the same (2024 against 2024/25);
* ``unexplained`` -- none of these: a true conflict until a resolve track explains it.

An explained conflict is recorded as explained; an unexplained one is ``open`` and
asks for a **resolve track** (:class:`ResolveTrackRequest`): typed data the lead
researcher's re-plan consumes, naming each value, its publisher, and what to find --
each value's primary source and the reason for the difference. When that track has
brought back primary findings, :func:`resolve_conflict` reads each side through its
primary and classifies again: ``resolved`` with a cause, or ``unresolved``, shown
as a conflict and never averaged.

Pure: stdlib and Pydantic only.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Final, Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field

from .contracts import Measure, MeasureBasis, digest
from .filters import (
    FilterCandidate,
    NearDuplicateConfig,
    exact_duplicate_clusters,
    near_duplicate_clusters,
)
from .reputation import Publisher, ReputationRegister, normalise_name

__all__ = [
    "RESOLVE_REQUEST_VERSION",
    "TRIANGULATION_VERSION",
    "Conflict",
    "ConflictCause",
    "ConflictResolution",
    "ConflictSide",
    "ConflictStatus",
    "ConflictTolerance",
    "IndependenceGroup",
    "IndependenceSource",
    "MeasuredFinding",
    "PeriodSpan",
    "PublisherIdentity",
    "ResolveSide",
    "ResolveTrackRequest",
    "basis_rank",
    "conflict_cause",
    "detect_conflicts",
    "independence_groups",
    "measure_key",
    "period_span",
    "publisher_identity",
    "register_key",
    "registrable_host",
    "resolve_conflict",
    "resolve_requests",
    "same_figure",
]

#: The rules of this module: publisher identity, independence, conflicts, causes.
TRIANGULATION_VERSION: Final = "aia-dr-triangulation-1"
#: The resolve-track request's shape, for the lead researcher's re-plan.
RESOLVE_REQUEST_VERSION: Final = "aia-dr-resolve-request-1"


class _Closed(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


# --------------------------------------------------------------------------- #
# Publisher identity
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class PublisherIdentity:
    """Who published a source, as code knows it.

    ``key`` is ``register:<name>`` for a publisher the register declares,
    ``host:<registrable host>`` for any other web host, ``knowledge:<item>`` for a
    Client Knowledge item and ``source:<ref>`` when a source has no usable host.
    """

    key: str
    name: str
    registered: bool


def register_key(publisher: Publisher) -> str:
    """The identity key of a publisher the register declares."""
    return f"register:{normalise_name(publisher.canonical_name)}"


def registrable_host(host: str) -> str:
    """The host's last two labels, lower case, without ``www.`` (no public-suffix list)."""
    labels = [label for label in host.strip().lower().rstrip(".").split(".") if label]
    if labels and labels[0] == "www":
        labels = labels[1:]
    return ".".join(labels[-2:])


def publisher_identity(
    *, url: str | None, source_ref: str, register: ReputationRegister | None
) -> PublisherIdentity:
    """The publisher of one source: the register's, else its registrable host's."""
    if url is None:
        if source_ref.startswith("KNW-"):
            item = source_ref.split("@", 1)[0]
            return PublisherIdentity(f"knowledge:{item}", item, registered=False)
        return PublisherIdentity(f"source:{source_ref}", source_ref, registered=False)
    host = (urlsplit(url).hostname or "").lower()
    if not host or "." not in host:
        return PublisherIdentity(f"source:{source_ref}", source_ref, registered=False)
    if register is not None:
        publisher = register.publisher_for_host(host)
        if publisher is not None:
            return PublisherIdentity(
                register_key(publisher), publisher.canonical_name, registered=True
            )
    base = registrable_host(host)
    return PublisherIdentity(f"host:{base}", base, registered=False)


# --------------------------------------------------------------------------- #
# Independence
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class IndependenceSource:
    """One source a candidate cites: its ref, its publisher and its normalised text."""

    ref: str
    publisher: PublisherIdentity
    text: str


class IndependenceGroup(_Closed):
    """Sources that count once toward confirmation, and why they were joined."""

    group_id: str
    source_refs: tuple[str, ...]
    publishers: tuple[str, ...]
    #: Joined by duplicate text across more than one publisher (a syndicated release).
    syndicated: bool


def independence_groups(
    sources: Sequence[IndependenceSource], config: NearDuplicateConfig | None = None
) -> dict[str, IndependenceGroup]:
    """Each source ref -> its independence group (rule: module doc). Deterministic."""
    by_ref = {s.ref: s for s in sorted(sources, key=lambda s: s.ref)}
    parent = {ref: ref for ref in by_ref}

    def find(ref: str) -> str:
        while parent[ref] != ref:
            parent[ref] = parent[parent[ref]]
            ref = parent[ref]
        return ref

    def join(a: str, b: str) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            low, high = sorted((ra, rb))
            parent[high] = low

    first_of: dict[str, str] = {}
    for ref, source in by_ref.items():
        if source.publisher.key in first_of:
            join(first_of[source.publisher.key], ref)
        else:
            first_of[source.publisher.key] = ref
    texts = [FilterCandidate(id=ref, text=s.text) for ref, s in by_ref.items() if s.text.strip()]
    duplicate_pairs: list[tuple[str, ...]] = []
    for cluster in (*exact_duplicate_clusters(texts), *near_duplicate_clusters(texts, config)):
        duplicate_pairs.append(cluster.members)
        for member in cluster.members[1:]:
            join(cluster.members[0], member)

    members: dict[str, list[str]] = {}
    for ref in by_ref:
        members.setdefault(find(ref), []).append(ref)
    groups: dict[str, IndependenceGroup] = {}
    for refs in members.values():
        publishers = tuple(sorted({by_ref[r].publisher.key for r in refs}))
        syndicated = any(
            len({by_ref[m].publisher.key for m in pair}) > 1
            for pair in duplicate_pairs
            if set(pair) <= set(refs)
        )
        group = IndependenceGroup(
            group_id="IND-" + digest(sorted(refs))[:12],
            source_refs=tuple(sorted(refs)),
            publishers=publishers,
            syndicated=syndicated,
        )
        for ref in refs:
            groups[ref] = group
    return groups


# --------------------------------------------------------------------------- #
# Periods
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class PeriodSpan:
    """A period as the months it covers, inclusive (months counted from year 0)."""

    start: int
    end: int

    def overlaps(self, other: PeriodSpan) -> bool:
        return self.start <= other.end and other.start <= self.end

    def after(self, other: PeriodSpan) -> bool:
        """Entirely later than ``other``."""
        return self.start > other.end


_YEAR = r"(?:19|20)\d{2}"
_PERIODS: Final = (
    (re.compile(rf"^Y?({_YEAR})$"), "year"),
    (re.compile(rf"^Y?({_YEAR})\s*/\s*(\d{{2}}|{_YEAR})$"), "season"),
    (re.compile(rf"^Y?({_YEAR})\s*-?\s*Q([1-4])$"), "quarter"),
    (re.compile(rf"^Y?({_YEAR})\s*-?\s*H([12])$"), "half"),
    (re.compile(rf"^Y?({_YEAR})-(0[1-9]|1[0-2])$"), "month"),
)


def period_span(period: str | None) -> PeriodSpan | None:
    """The months a stated period covers, or ``None`` when it cannot be placed.

    Reads the measure vocabulary's year keys (``Y2025``, ``Y2024/2025``) and the
    forms a source writes (``2025``, ``2024/25``, ``2025-Q2``, ``2025-H1``,
    ``2025-03``). A season covers both its years. A quarter, half or month without
    a year (``Q2``, ``M03``) cannot be placed and is ``None``: unknown, never a guess.
    """
    if period is None:
        return None
    text = period.strip().upper()
    for pattern, kind in _PERIODS:
        match = pattern.match(text)
        if match is None:
            continue
        year = int(match[1])
        base = year * 12
        if kind == "year":
            return PeriodSpan(base, base + 11)
        if kind == "season":
            tail = match[2]
            end_year = int(tail) if len(tail) == 4 else (year // 100) * 100 + int(tail)
            if end_year < year:
                return None
            return PeriodSpan(base, end_year * 12 + 11)
        if kind == "quarter":
            q = int(match[2])
            return PeriodSpan(base + 3 * (q - 1), base + 3 * q - 1)
        if kind == "half":
            h = int(match[2])
            return PeriodSpan(base + 6 * (h - 1), base + 6 * h - 1)
        month = int(match[2])
        return PeriodSpan(base + month - 1, base + month - 1)
    return None


# --------------------------------------------------------------------------- #
# Figures
# --------------------------------------------------------------------------- #


def measure_key(measure: Measure) -> tuple[str, str, str] | None:
    """What makes two figures the same measure: its name, unit and place, all stated."""
    if measure.measure_name is None or measure.unit is None or measure.geography is None:
        return None
    name = normalise_name(measure.measure_name)
    return (name, measure.unit, measure.geography) if name else None


def _decimals(value: float) -> int:
    if float(value).is_integer():
        return 0
    text = repr(float(value))
    if "e" in text or "E" in text:
        return 6
    return min(6, len(text.split(".", 1)[1]))


def _scaled(measure: Measure) -> float:
    return measure.value * measure.scale


@dataclass(frozen=True, slots=True)
class ConflictTolerance:
    """How far two scaled values may differ and still be one figure.

    Rounding always: half a unit of the last decimal each states, times its scale,
    the coarser of the two. ``relative`` adds a share of the larger value; it is 0
    by default, so only rounding separates "the same" from "a conflict".
    """

    relative: float = 0.0

    def __post_init__(self) -> None:
        if not 0.0 <= self.relative < 1.0:
            raise ValueError("a relative tolerance is in [0, 1)")

    def allowed(self, a: Measure, b: Measure) -> float:
        rounding = max(0.5 * 10.0 ** -_decimals(m.value) * m.scale for m in (a, b))
        return rounding + self.relative * max(abs(_scaled(a)), abs(_scaled(b)))

    def agree(self, a: Measure, b: Measure) -> bool:
        return abs(_scaled(a) - _scaled(b)) <= self.allowed(a, b) + 1e-9


def _both_differ(a: str | None, b: str | None) -> bool:
    return a is not None and b is not None and a != b


def same_figure(a: Measure, b: Measure, tolerance: ConflictTolerance | None = None) -> bool:
    """Whether two measures state one figure: the value within rounding, and no stated
    attribute -- unit, place, population, denominator, period -- that differs."""
    tolerance = tolerance or ConflictTolerance()
    if not tolerance.agree(a, b):
        return False
    for x, y in (
        (a.unit, b.unit),
        (a.geography, b.geography),
        (a.population, b.population),
        (a.denominator, b.denominator),
    ):
        if _both_differ(x, y):
            return False
    span_a, span_b = period_span(a.period), period_span(b.period)
    if span_a is not None and span_b is not None:
        return span_a == span_b
    return not _both_differ(a.period, b.period)


# --------------------------------------------------------------------------- #
# Conflicts
# --------------------------------------------------------------------------- #


class ConflictCause(StrEnum):
    DEFINITION = "definition"
    BASIS = "basis"
    PERIOD = "period"
    UNEXPLAINED = "unexplained"


class ConflictStatus(StrEnum):
    #: The measures explain the difference: no resolve track is needed.
    EXPLAINED = "explained"
    #: Nothing explains it yet: a resolve track is requested.
    OPEN = "open"
    #: A resolve track's primary sources explained it.
    RESOLVED = "resolved"
    #: A resolve track ran and nothing explains it: shown as a conflict, never averaged.
    UNRESOLVED = "unresolved"


class MeasuredFinding(_Closed):
    """One measure of one finding, with what code knows of its source."""

    evidence_id: str
    publisher: str
    publisher_name: str
    primary: bool
    source_url: str | None
    measure: Measure


class ConflictSide(_Closed):
    evidence_id: str
    publisher: str
    publisher_name: str
    primary: bool
    source_url: str | None
    measure: Measure

    @classmethod
    def of(cls, finding: MeasuredFinding) -> ConflictSide:
        return cls(**finding.model_dump())


class Conflict(_Closed):
    """Two findings stating one measure for overlapping periods, with different values."""

    conflict_id: str
    measure_name: str
    unit: str
    geography: str
    sides: tuple[ConflictSide, ConflictSide]
    #: The scaled values' difference and what the tolerance allowed.
    difference: float
    allowed: float
    cause: ConflictCause
    status: ConflictStatus
    detail: str = Field(max_length=2000)


def conflict_cause(a: Measure, b: Measure) -> tuple[ConflictCause, str]:
    """The likely cause of two values' difference, from their measures (module doc)."""
    if _both_differ(a.population, b.population):
        return ConflictCause.DEFINITION, f"population {a.population} against {b.population}"
    if _both_differ(a.denominator, b.denominator):
        return ConflictCause.DEFINITION, f"denominator {a.denominator} against {b.denominator}"
    if a.basis is not None and b.basis is not None and a.basis is not b.basis:
        return ConflictCause.BASIS, f"basis {a.basis.value} against {b.basis.value}"
    span_a, span_b = period_span(a.period), period_span(b.period)
    if span_a is not None and span_b is not None and span_a != span_b:
        return ConflictCause.PERIOD, f"period {a.period} against {b.period}"
    return ConflictCause.UNEXPLAINED, "the measures state nothing that explains the difference"


def _conflict(
    a: MeasuredFinding, b: MeasuredFinding, tolerance: ConflictTolerance
) -> Conflict | None:
    key = measure_key(a.measure)
    if key is None or key != measure_key(b.measure):
        return None
    span_a, span_b = period_span(a.measure.period), period_span(b.measure.period)
    if span_a is None or span_b is None or not span_a.overlaps(span_b):
        return None
    if tolerance.agree(a.measure, b.measure):
        return None
    left, right = sorted((a, b), key=lambda f: (f.evidence_id, _scaled(f.measure)))
    cause, why = conflict_cause(left.measure, right.measure)
    status = ConflictStatus.OPEN if cause is ConflictCause.UNEXPLAINED else ConflictStatus.EXPLAINED
    difference = abs(_scaled(left.measure) - _scaled(right.measure))
    allowed = tolerance.allowed(left.measure, right.measure)
    return Conflict(
        conflict_id="CNF-"
        + digest(
            [
                [left.evidence_id, left.measure.model_dump(mode="json")],
                [right.evidence_id, right.measure.model_dump(mode="json")],
            ]
        )[:16],
        measure_name=str(left.measure.measure_name),
        unit=key[1],
        geography=key[2],
        sides=(ConflictSide.of(left), ConflictSide.of(right)),
        difference=round(difference, 9),
        allowed=round(allowed, 9),
        cause=cause,
        status=status,
        detail=(
            f"{_scaled(left.measure):g} ({left.publisher_name}) against "
            f"{_scaled(right.measure):g} ({right.publisher_name}) differ by "
            f"{difference:g}, more than {allowed:g}; {cause.value}: {why}"
        )[:2000],
    )


def detect_conflicts(
    findings: Iterable[MeasuredFinding], tolerance: ConflictTolerance | None = None
) -> tuple[Conflict, ...]:
    """Every pair of findings that conflicts (rule: module doc), in a fixed order."""
    tolerance = tolerance or ConflictTolerance()
    ordered = sorted(findings, key=lambda f: (f.evidence_id, _scaled(f.measure)))
    found: dict[str, Conflict] = {}
    for i, a in enumerate(ordered):
        for b in ordered[i + 1 :]:
            if a.evidence_id == b.evidence_id:
                continue
            conflict = _conflict(a, b, tolerance)
            if conflict is not None:
                found.setdefault(conflict.conflict_id, conflict)
    return tuple(found[k] for k in sorted(found))


# --------------------------------------------------------------------------- #
# Resolve tracks
# --------------------------------------------------------------------------- #


class ResolveSide(_Closed):
    evidence_id: str
    value: float
    scale: int
    period: str | None
    publisher_name: str
    primary: bool
    source_url: str | None


class ResolveTrackRequest(_Closed):
    """A conflict that needs a resolve track: typed data for the lead's re-plan (§ 8.5).

    ``objective`` and ``wanted`` are written by code from the conflict, in Czech, the
    language of every task brief; nothing here is a model's text.
    """

    version: Literal["aia-dr-resolve-request-1"]
    conflict_id: str
    measure_name: str
    unit: str
    geography: str
    sides: tuple[ResolveSide, ...]
    #: The publishers named on either side, to look at first.
    prefer_publishers: tuple[str, ...]
    objective: str = Field(max_length=1500)
    wanted: str = Field(max_length=1500)


def _side_text(side: ConflictSide) -> str:
    m = side.measure
    parts = [f"{_scaled(m):g}", m.unit or "", f"za {m.period}" if m.period else ""]
    return " ".join(p for p in parts if p) + f" ({side.publisher_name})"


def resolve_requests(conflicts: Iterable[Conflict]) -> tuple[ResolveTrackRequest, ...]:
    """A resolve-track request for every ``open`` conflict, in the conflicts' order."""
    requests = []
    for c in conflicts:
        if c.status is not ConflictStatus.OPEN:
            continue
        values = " a ".join(_side_text(s) for s in c.sides)
        requests.append(
            ResolveTrackRequest(
                version=RESOLVE_REQUEST_VERSION,
                conflict_id=c.conflict_id,
                measure_name=c.measure_name,
                unit=c.unit,
                geography=c.geography,
                sides=tuple(
                    ResolveSide(
                        evidence_id=s.evidence_id,
                        value=s.measure.value,
                        scale=s.measure.scale,
                        period=s.measure.period,
                        publisher_name=s.publisher_name,
                        primary=s.primary,
                        source_url=s.source_url,
                    )
                    for s in c.sides
                ),
                prefer_publishers=tuple(dict.fromkeys(s.publisher_name for s in c.sides)),
                objective=(
                    f"Vysvětli rozpor v ukazateli „{c.measure_name}“ ({c.geography}): {values}."
                )[:1500],
                wanted=(
                    "Pro každou hodnotu primární zdroj (vydavatele čísla) s celou mírou -- "
                    "jednotkou, obdobím, územím, populací, jmenovatelem a povahou údaje -- a "
                    "důvod rozdílu: definice, revize, nebo období. Hodnoty neprůměruj."
                ),
            )
        )
    return tuple(requests)


class ConflictResolution(_Closed):
    """What a resolve track's primary findings say about one conflict."""

    conflict_id: str
    status: Literal[ConflictStatus.RESOLVED, ConflictStatus.UNRESOLVED]
    cause: ConflictCause
    #: Each side's primary finding, by the side's order; None where none was found.
    primaries: tuple[str | None, str | None]
    detail: str = Field(max_length=2000)


def _filled(measure: Measure, primary: Measure) -> Measure:
    """``measure`` with what it left unstated taken from its primary's measure."""
    update = {
        field: getattr(primary, field)
        for field in ("period", "population", "denominator", "basis", "measure_name")
        if getattr(measure, field) is None and getattr(primary, field) is not None
    }
    return measure.model_copy(update=update)


def _primary_for(
    side: ConflictSide,
    findings: Sequence[MeasuredFinding],
    tolerance: ConflictTolerance,
) -> MeasuredFinding | None:
    if side.primary:
        return MeasuredFinding(**side.model_dump())
    key = measure_key(side.measure)
    span = period_span(side.measure.period)
    for f in sorted(findings, key=lambda f: f.evidence_id):
        if (
            not f.primary
            or measure_key(f.measure) != key
            or not tolerance.agree(f.measure, side.measure)
        ):
            continue
        other = period_span(f.measure.period)
        if span is not None and other is not None and not span.overlaps(other):
            continue
        return f
    return None


def resolve_conflict(
    conflict: Conflict,
    findings: Sequence[MeasuredFinding],
    tolerance: ConflictTolerance | None = None,
) -> ConflictResolution:
    """Each side read through its primary source; the conflict classified again.

    ``findings`` are what a resolve track brought back (with any the run already had).
    A side's primary is a primary finding of the same measure whose value is the
    side's within rounding, for an overlapping period. What the side left unstated
    is taken from it; nothing it stated is overwritten. ``resolved`` needs a cause
    the measures now show; anything else stays ``unresolved``.
    """
    tolerance = tolerance or ConflictTolerance()
    left, right = conflict.sides
    found = (_primary_for(left, findings, tolerance), _primary_for(right, findings, tolerance))
    a = _filled(left.measure, found[0].measure) if found[0] is not None else left.measure
    b = _filled(right.measure, found[1].measure) if found[1] is not None else right.measure
    cause, why = conflict_cause(a, b)
    primaries = (
        found[0].evidence_id if found[0] is not None else None,
        found[1].evidence_id if found[1] is not None else None,
    )
    if cause is ConflictCause.UNEXPLAINED:
        missing = [s.evidence_id for s, p in zip(conflict.sides, found, strict=True) if p is None]
        detail = why + (
            "; no primary source was found for " + ", ".join(missing) if missing else ""
        )
        return ConflictResolution(
            conflict_id=conflict.conflict_id,
            status=ConflictStatus.UNRESOLVED,
            cause=cause,
            primaries=primaries,
            detail=detail[:2000],
        )
    return ConflictResolution(
        conflict_id=conflict.conflict_id,
        status=ConflictStatus.RESOLVED,
        cause=cause,
        primaries=primaries,
        detail=f"{cause.value}: {why}"[:2000],
    )


def basis_rank(basis: MeasureBasis | None) -> int | None:
    """How final a figure is: actual 2, preliminary or estimate 1, forecast 0, unstated None."""
    if basis is None:
        return None
    return {
        MeasureBasis.ACTUAL: 2,
        MeasureBasis.PRELIMINARY: 1,
        MeasureBasis.ESTIMATE: 1,
        MeasureBasis.FORECAST: 0,
    }[basis]
