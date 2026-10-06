"""Gaps and acquisition gaps: what a run could not establish, and what it could not reach.

Plan ``deep-research-web-search.md`` §§ 4, 7 and 8.8, chunk 13. A brief says what it
does not know as plainly as what it does. Two kinds, each with its reason:

**Gaps** (:class:`ResearchGap`), by code from the run's records:

* ``stated`` -- what an investigator said it could not establish: the ``finish``
  action's gaps (need, why, what it tried), or a planned-mode track's gap lines;
* ``unanswered`` -- a subject with no accepted finding, with its sub-questions and
  why each of its tracks stopped;
* ``conflict`` -- a conflict nothing has explained (``open``: a resolve track is
  requested and has not run; ``unresolved``: one ran and explained nothing).

**Acquisition gaps** (:class:`AcquisitionGap`): a source the run needed and did not
capture -- who publishes it, what it is, why it was not reached, which rungs of the
acquisition ladder (§ 7) were tried, and how a person could obtain it. The ladder
(chunk 10) is not built: it will fill ``rungs_tried`` and ``ladder_version``. What is
known now is recorded now:

* a lead nobody pursued (``not_pursued``) -- an investigator's ``leads`` (unless the
  track captured a source of the publisher it named, resolved by the register), a
  secondary finding's lead to its primary publisher, a search the verifier proposed;
* an open the investigator tried and the web refused (``investigator_open``): behind
  a paywall (HTTP 402), a login (401), not public (403), not found (404, 410), or
  forbidden to robots (``robots.txt``). A refusal of AIA's own -- a data class, an
  address -- is a boundary, not a missing source, and is not an acquisition gap.

**Numbers.** Every number a brief prints cites an evidence id (§ 8.8), and a gap has
nothing to cite. A gap's text written by an agent (a need, a reason, a result's title)
keeps only years, which name the period that is missing; a text with any other number
is withheld (``text_withheld``), and the track's transcript keeps it.

Pure: stdlib and Pydantic only.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING, Final
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field

from ..analysis.draft import uncovered_numbers
from .agents import FinishAction, TurnGap, TurnLead
from .contracts import ResearchSubject, StopReason, TrackStatus, digest
from .reputation import ReputationRegister
from .tracing import PrimaryLead
from .triangulation import Conflict, ConflictStatus
from .verification import VerifierLead

if TYPE_CHECKING:
    from .investigator import Transcript

__all__ = [
    "GAPS_VERSION",
    "WITHHELD",
    "AcquisitionGap",
    "AcquisitionReason",
    "AcquisitionRung",
    "GapKind",
    "LeadSource",
    "OpenAttempt",
    "ResearchGap",
    "RungAttempt",
    "TrackFacts",
    "acquisition_gaps",
    "acquisition_reason",
    "conflict_gaps",
    "how_to_obtain",
    "only_years",
    "research_gaps",
    "strip_ids",
    "track_facts",
]

GAPS_VERSION: Final = "aia-dr-gaps-1"

#: What a withheld text reads in the brief.
WITHHELD: Final = "[text s číslem bez citace je jen v přepisu stopy]"


class _Closed(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


#: A record id (``EV-…``, ``CNF-…``, ``DRT-W-q-…``, ``KNW-…@2``): a citation, never a number.
_RECORD_ID: Final = re.compile(
    r"(?<![\w-])[A-Za-z]{1,4}(?:-[A-Za-z]{1,4})*-[0-9a-f]{8,}(?:@\d+)?\b"
)


def strip_ids(text: str) -> str:
    """``text`` with every record id blanked: an id's digits are not a number it states."""
    return _RECORD_ID.sub(lambda m: " " * len(m.group(0)), text)


def only_years(text: str, names: Sequence[str] = ()) -> bool:
    """Whether every number ``text`` states is a year (a whole 1900-2099): a period's name.

    A range or bound one of ``names`` writes itself (a subject's ``18-29``) is a name,
    not a number, as in every other prose check (``analysis.draft.uncovered_numbers``).
    """
    return all(
        float(n).is_integer() and 1900 <= n <= 2099
        for n in uncovered_numbers(strip_ids(text), (), names)
    )


def _kept(text: str, names: Sequence[str] = ()) -> tuple[str, bool]:
    return (text, False) if only_years(text, names) else (WITHHELD, True)


# --------------------------------------------------------------------------- #
# Gaps
# --------------------------------------------------------------------------- #


class GapKind(StrEnum):
    STATED = "stated"
    UNANSWERED = "unanswered"
    CONFLICT = "conflict"


class ResearchGap(_Closed):
    """One thing the run could not establish, and why."""

    gap_id: str
    kind: GapKind
    subject_key: str | None
    track_id: str | None
    need: str = Field(max_length=2000)
    reason: str = Field(max_length=2000)
    tried: str | None = Field(max_length=2000)
    conflict_id: str | None
    #: An agent's text held a number other than a year and is in the transcript only.
    text_withheld: bool


@dataclass(frozen=True, slots=True)
class OpenAttempt:
    """An ``open`` the web refused or failed: the page, and the reason code it gave."""

    turn: int
    index: int
    ref: str | None
    url: str | None
    title: str
    reason: str


@dataclass(frozen=True, slots=True)
class TrackFacts:
    """What gaps are read from, for one track: its stop, and its transcript's parts."""

    track_id: str
    subject_key: str
    status: TrackStatus
    stop_reason: StopReason
    detail: str
    sub_questions: tuple[str, ...]
    #: The ``finish`` action's gaps (agent-directed).
    finish_gaps: tuple[TurnGap, ...] = ()
    #: A planned-mode (or internal) track's gap lines.
    gap_lines: tuple[str, ...] = ()
    #: The investigator's leads, with the turn that raised each.
    leads: tuple[tuple[int, TurnLead], ...] = ()
    opens: tuple[OpenAttempt, ...] = ()
    #: Hosts of every source the track captured.
    captured_hosts: frozenset[str] = field(default_factory=frozenset)


def track_facts(
    *,
    track_id: str,
    subject_key: str,
    status: TrackStatus,
    stop_reason: StopReason,
    detail: str,
    sub_questions: Sequence[str],
    gap_lines: Sequence[str],
    transcript: Transcript | None,
) -> TrackFacts:
    """A track's facts; an agent-directed track's from its transcript, every turn of it.

    Without a transcript (a planned-mode or internal track) the gap lines are its gaps.
    """
    if transcript is None:
        return TrackFacts(
            track_id=track_id,
            subject_key=subject_key,
            status=status,
            stop_reason=stop_reason,
            detail=detail,
            sub_questions=tuple(sub_questions),
            gap_lines=tuple(gap_lines),
        )
    titles = {r.ref: r.title for r in transcript.results} | {
        link.ref: link.text for link in transcript.links
    }
    finish = [
        gap
        for t in transcript.turns
        for action in t.output.next
        if isinstance(action, FinishAction)
        for gap in action.gaps
    ]
    opens = [
        OpenAttempt(
            turn=t.turn,
            index=a.index,
            ref=a.ref,
            url=a.url,
            title=titles.get(a.ref or "", ""),
            reason=a.reason,
        )
        for t in transcript.turns
        for a in t.actions
        if a.kind == "open" and a.reason is not None and acquisition_reason(a.reason) is not None
    ]
    return TrackFacts(
        track_id=track_id,
        subject_key=subject_key,
        status=status,
        stop_reason=stop_reason,
        detail=detail,
        sub_questions=tuple(sub_questions),
        finish_gaps=tuple(finish),
        leads=tuple((t.turn, lead) for t in transcript.turns for lead in t.output.leads),
        opens=tuple(opens),
        captured_hosts=frozenset(s.host for s in transcript.sources),
    )


def _gap_id(*parts: object) -> str:
    return "GAP-" + digest(list(parts))[:12]


def _stop_words(t: TrackFacts) -> str:
    return f"{t.track_id}: {t.status.value}, {t.stop_reason.value}"


def research_gaps(
    subjects: Sequence[ResearchSubject],
    tracks: Sequence[TrackFacts],
    *,
    answered: frozenset[str],
) -> tuple[ResearchGap, ...]:
    """Stated and unanswered gaps, subject by subject in the run's order.

    ``answered`` names the subjects with at least one accepted finding.
    """
    by_subject: dict[str, list[TrackFacts]] = {}
    for t in tracks:
        by_subject.setdefault(t.subject_key, []).append(t)
    gaps: list[ResearchGap] = []
    for subject in subjects:
        own = by_subject.get(subject.key, [])
        if subject.key not in answered:
            questions = [q for t in own for q in t.sub_questions]
            need, withheld = _kept(
                subject.text + ("; " + "; ".join(dict.fromkeys(questions)) if questions else ""),
                [subject.text],
            )
            stops = "; ".join(_stop_words(t) for t in own) or "no track researched it"
            gaps.append(
                ResearchGap(
                    gap_id=_gap_id("unanswered", subject.key),
                    kind=GapKind.UNANSWERED,
                    subject_key=subject.key,
                    track_id=None,
                    need=need[:2000],
                    reason=f"no accepted finding; {stops}"[:2000],
                    tried=None,
                    conflict_id=None,
                    text_withheld=withheld,
                )
            )
        for t in own:
            for gap in t.finish_gaps:
                texts = [_kept(gap.need), _kept(gap.why), _kept(gap.tried)]
                gaps.append(
                    ResearchGap(
                        gap_id=_gap_id("stated", t.track_id, gap.need, gap.why, gap.tried),
                        kind=GapKind.STATED,
                        subject_key=subject.key,
                        track_id=t.track_id,
                        need=texts[0][0],
                        reason=texts[1][0],
                        tried=texts[2][0],
                        conflict_id=None,
                        text_withheld=any(w for _, w in texts),
                    )
                )
            for line in t.gap_lines:
                text, withheld = _kept(line)
                gaps.append(
                    ResearchGap(
                        gap_id=_gap_id("stated", t.track_id, line),
                        kind=GapKind.STATED,
                        subject_key=subject.key,
                        track_id=t.track_id,
                        need=text[:2000],
                        reason="stated by the track's investigator",
                        tried=None,
                        conflict_id=None,
                        text_withheld=withheld,
                    )
                )
    unique: dict[str, ResearchGap] = {}
    for found in gaps:
        unique.setdefault(found.gap_id, found)
    return tuple(unique.values())


def conflict_gaps(conflicts: Iterable[Conflict]) -> tuple[ResearchGap, ...]:
    """A gap for every conflict nothing explains: shown as a conflict, never averaged."""
    gaps = []
    for c in conflicts:
        if c.status not in (ConflictStatus.OPEN, ConflictStatus.UNRESOLVED):
            continue
        reason = (
            "unresolved: a resolve track is requested and has not run"
            if c.status is ConflictStatus.OPEN
            else "unresolved: the resolve track's primary sources explain nothing"
        )
        need, withheld = _kept(f"„{c.measure_name}“ ({c.geography})")
        gaps.append(
            ResearchGap(
                gap_id=_gap_id("conflict", c.conflict_id),
                kind=GapKind.CONFLICT,
                subject_key=None,
                track_id=None,
                need=need,
                reason=reason,
                tried=None,
                conflict_id=c.conflict_id,
                text_withheld=withheld,
            )
        )
    return tuple(gaps)


# --------------------------------------------------------------------------- #
# Acquisition gaps
# --------------------------------------------------------------------------- #


class AcquisitionReason(StrEnum):
    """Why a needed source was not captured (plan § 7, rung 11)."""

    PAYWALL = "paywall"
    LOGIN = "login"
    NOT_PUBLIC = "not_public"
    NOT_FOUND = "not_found"
    #: The host's robots.txt forbids it, or could not be read.
    ROBOTS = "robots"
    #: Needed and recorded; no lawful route was tried yet (the ladder did not run).
    NOT_PURSUED = "not_pursued"


class AcquisitionRung(StrEnum):
    """The ladder's rungs (plan § 7, 1-10), and an investigator's own open."""

    DIRECT_LINK = "direct_link"
    OTHER_FORMATS = "other_formats"
    PUBLISHER_INDEX = "publisher_index"
    DATA_INTERFACE = "data_interface"
    EXACT_PHRASE = "exact_phrase"
    LANGUAGE_EDITION = "language_edition"
    SCHOLARLY_IDENTITY = "scholarly_identity"
    OFFICIAL_AGGREGATOR = "official_aggregator"
    ARCHIVED_COPY = "archived_copy"
    PATH_DISCOVERY = "path_discovery"
    #: Not a rung: the investigator opened the page itself, outside any ladder.
    INVESTIGATOR_OPEN = "investigator_open"


class RungAttempt(_Closed):
    """One attempt to reach a source: the rung, the reason code it ended on, the page."""

    rung: AcquisitionRung
    outcome: str = Field(max_length=100)
    url: str | None
    detail: str = Field(max_length=500)


class AcquisitionGap(_Closed):
    """A source the run needed and did not capture, and how a person could obtain it."""

    gap_id: str
    publisher: str | None
    title: str = Field(max_length=500)
    reason: AcquisitionReason
    rungs_tried: tuple[RungAttempt, ...]
    #: The ladder's version once one ran (chunk 10); None: no ladder ran.
    ladder_version: str | None
    how_to_obtain: str = Field(max_length=500)
    #: What raised it: ``investigator_lead``, ``primary_lead``, ``verifier_lead``,
    #: ``refused_open``; and the record it came from (a lead id, track:turn:action).
    raised_by: str
    origin: str
    subject_key: str | None
    track_id: str | None
    url: str | None
    #: An agent's text held a number other than a year and is in the transcript only.
    text_withheld: bool


_HTTP: Final[dict[str, AcquisitionReason]] = {
    "http_401": AcquisitionReason.LOGIN,
    "http_402": AcquisitionReason.PAYWALL,
    "http_403": AcquisitionReason.NOT_PUBLIC,
    "http_404": AcquisitionReason.NOT_FOUND,
    "http_407": AcquisitionReason.LOGIN,
    "http_410": AcquisitionReason.NOT_FOUND,
    "http_451": AcquisitionReason.NOT_PUBLIC,
    "robots_disallowed": AcquisitionReason.ROBOTS,
    "robots_unavailable": AcquisitionReason.ROBOTS,
}


def acquisition_reason(code: str) -> AcquisitionReason | None:
    """The acquisition reason a fetch's refusal or failure code means, or None.

    None for anything that is not about the source: AIA's own boundaries (a data
    class, an address, a content type), the network, the budget.
    """
    return _HTTP.get(code)


_HOW: Final[dict[AcquisitionReason, str]] = {
    AcquisitionReason.PAYWALL: (
        "Zdroj je za platební bránou: lze ho koupit, nebo o něj požádat vydavatele, a nahrát "
        "do Znalostí klienta."
    ),
    AcquisitionReason.LOGIN: (
        "Zdroj vyžaduje přihlášení: oprávněná osoba ho může stáhnout a nahrát do Znalostí "
        "klienta; AIA se nikam nepřihlašuje."
    ),
    AcquisitionReason.NOT_PUBLIC: (
        "Vydavatel zdroj veřejně nezpřístupňuje: požádejte ho o něj a nahrajte ho do Znalostí "
        "klienta."
    ),
    AcquisitionReason.NOT_FOUND: (
        "Zdroj na uvedené adrese není: dohledejte ho u vydavatele, nebo ho nahrajte do Znalostí "
        "klienta."
    ),
    AcquisitionReason.ROBOTS: (
        "Pravidla serveru (robots.txt) automatický přístup nedovolují: zdroj může získat "
        "člověk a nahrát ho do Znalostí klienta."
    ),
    AcquisitionReason.NOT_PURSUED: (
        "Zdroj zatím nikdo nehledal: cesta k jeho získání v tomto běhu neběžela. Lze ho "
        "dohledat ručně a nahrát do Znalostí klienta."
    ),
}


def how_to_obtain(reason: AcquisitionReason) -> str:
    """How a person could obtain a source unreachable for ``reason``. Written by code."""
    return _HOW[reason]


@dataclass(frozen=True, slots=True)
class LeadSource:
    """The leads the verify step recorded: secondary findings' and the verifier's."""

    primary: tuple[PrimaryLead, ...] = ()
    verifier: tuple[VerifierLead, ...] = ()
    #: Evidence id -> its subject, for the leads that name a finding.
    subjects: Mapping[str, str] = field(default_factory=dict)


def _reached(named: str | None, hosts: frozenset[str], register: ReputationRegister | None) -> bool:
    """Whether a track captured a source of the publisher a lead names, by the register."""
    if named is None or register is None:
        return False
    publisher = register.resolve_publisher(named)
    if publisher is None:
        return False
    return any(
        (p := register.publisher_for_host(h)) is not None
        and p.canonical_name == publisher.canonical_name
        for h in hosts
    )


def _publisher(
    named: str | None, url: str | None, register: ReputationRegister | None
) -> str | None:
    if register is not None and named:
        resolved = register.resolve_publisher(named)
        if resolved is not None:
            return resolved.canonical_name
    if register is not None and url:
        found = register.publisher_for_host(urlsplit(url).hostname or "")
        if found is not None:
            return found.canonical_name
    if named:
        return named
    host = (urlsplit(url).hostname or "") if url else ""
    return host or None


def acquisition_gaps(
    tracks: Sequence[TrackFacts],
    leads: LeadSource,
    *,
    register: ReputationRegister | None,
) -> tuple[AcquisitionGap, ...]:
    """Every source the run needed and did not capture (module doc), once each.

    Refused opens first (the web said why), then investigators' leads, then the
    verify step's leads. Two records naming one publisher and one title are one gap.
    """
    found: list[AcquisitionGap] = []
    for t in tracks:
        for o in t.opens:
            reason = acquisition_reason(o.reason)
            assert reason is not None
            title, withheld = _kept(o.title or (o.url or ""))
            found.append(
                AcquisitionGap(
                    gap_id=_gap_id("open", t.track_id, o.url),
                    publisher=_publisher(None, o.url, register),
                    title=title[:500],
                    reason=reason,
                    rungs_tried=(
                        RungAttempt(
                            rung=AcquisitionRung.INVESTIGATOR_OPEN,
                            outcome=o.reason,
                            url=o.url,
                            detail=f"turn {o.turn}, action {o.index}, {o.ref or 'no ref'}",
                        ),
                    ),
                    ladder_version=None,
                    how_to_obtain=how_to_obtain(reason),
                    raised_by="refused_open",
                    origin=f"{t.track_id}:{o.turn}:{o.index}",
                    subject_key=t.subject_key,
                    track_id=t.track_id,
                    url=o.url,
                    text_withheld=withheld,
                )
            )
        for turn, lead in t.leads:
            if _reached(lead.publisher, t.captured_hosts, register):
                continue
            title, withheld = _kept(lead.need)
            found.append(
                AcquisitionGap(
                    gap_id=_gap_id("lead", t.track_id, lead.need, lead.publisher),
                    publisher=_publisher(lead.publisher, None, register),
                    title=title[:500],
                    reason=AcquisitionReason.NOT_PURSUED,
                    rungs_tried=(),
                    ladder_version=None,
                    how_to_obtain=how_to_obtain(AcquisitionReason.NOT_PURSUED),
                    raised_by="investigator_lead",
                    origin=f"{t.track_id}:{turn}",
                    subject_key=t.subject_key,
                    track_id=t.track_id,
                    url=None,
                    text_withheld=withheld,
                )
            )
    for p in leads.primary:
        title, withheld = _kept(p.need)
        found.append(
            AcquisitionGap(
                gap_id=_gap_id("primary", p.lead_id),
                publisher=p.publisher,
                title=title[:500],
                reason=AcquisitionReason.NOT_PURSUED,
                rungs_tried=(),
                ladder_version=None,
                how_to_obtain=how_to_obtain(AcquisitionReason.NOT_PURSUED),
                raised_by="primary_lead",
                origin=p.lead_id,
                subject_key=leads.subjects.get(p.evidence_id),
                track_id=None,
                url=p.link,
                text_withheld=withheld,
            )
        )
    for v in leads.verifier:
        title, withheld = _kept(v.query)
        found.append(
            AcquisitionGap(
                gap_id=_gap_id("verifier", v.lead_id),
                publisher=v.publisher or v.publisher_named,
                title=title[:500],
                reason=AcquisitionReason.NOT_PURSUED,
                rungs_tried=(),
                ladder_version=None,
                how_to_obtain=how_to_obtain(AcquisitionReason.NOT_PURSUED),
                raised_by="verifier_lead",
                origin=v.lead_id,
                subject_key=leads.subjects.get(v.evidence_id),
                track_id=None,
                url=None,
                text_withheld=withheld,
            )
        )
    unique: dict[tuple[str | None, str, str | None], AcquisitionGap] = {}
    for gap in found:
        key = (gap.publisher, gap.title if not gap.text_withheld else gap.gap_id, gap.url)
        unique.setdefault(key, gap)
    return tuple(unique.values())
