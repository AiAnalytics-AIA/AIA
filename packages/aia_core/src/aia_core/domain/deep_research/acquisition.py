"""The acquisition ladder's rules: what a lead is, when a capture answers it, and the gap.

Plan ``deep-research-web-search.md`` § 4 (boundaries), § 7 (the ladder) and § 8.3
(primary tracing), chunk 10. When a track needs a specific source -- the table a page
cites, the report behind a press release, the figure for a year it has not found --
it raises an :class:`AcquisitionLead`, and the ladder
(``application.acquisition_ladder``) tries eleven rungs **in order**, stopping at
the first that yields a capture answering the lead. This module is the pure half:
everything the ladder decides without sending anything.

* **The lead** names what is needed in terms code can check: a distinctive phrase
  (a table title, a document number, the figure as printed) or a title, a DOI or a
  dataset id. A need code could never recognise when it found it is refused here:
  the ladder would have nothing to stop on.
* **Answering a lead** (:func:`satisfies`) is checked by code on the capture, never
  by a model: a dataset the lead named that answered rows; else a phrase the lead
  named found in the text (when it names phrases, a page with only the title is a
  landing page, not the source); else the title found in the text or the page's
  title. A page behind a barrier or carrying instructions answers nothing.
* **Barriers** (:func:`detect_barrier`): a paywall, a login or a challenge (a
  CAPTCHA or bot check) by declared markers, Czech and English; a page with no
  marker is ``NONE`` only when it holds enough text to be the page itself
  (:data:`BARRIER_MIN_TEXT_CHARS`), else ``UNKNOWN`` -- a short stub is what a
  paywall usually serves, and unknown is never scored as open. Only ``NONE`` lets
  ``archive.decide_archive_use`` permit an archived copy of a changed page.
* **Archives and mirrors** (:func:`is_archive_url`) are reached by rung 9 alone,
  with a permit; every other rung refuses a candidate on an archive's host, so no
  search hit or link can become a way round a paywall.
* **The gap** (:class:`AcquisitionGap`): nothing worked. It names the publisher, the
  title, the need, the reason (the most telling thing the attempts met, by
  :data:`GAP_PRIORITY`), the rungs tried, and how a person could obtain the source.
* **Primary tracing** (:func:`lead_from_secondary`): a finding on a page that names
  or links another publisher as the figure's source raises a lead for that primary.

Every list here is **proposed** (:data:`LADDER_STATUS`): the barrier markers, the
aggregator hosts, the archive hosts and the caps are data the owner approves with
the register (plan chunk 1).

Pure: stdlib and Pydantic only.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable, Sequence
from enum import StrEnum
from typing import Final, Literal
from urllib.parse import unquote, urlsplit, urlunsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from ..residency import DataClass
from .archive import AccessBarrier, ArchiveBasis
from .contracts import SourceSnapshot
from .grounding import locate_quote, normalise_text
from .legacy import canonical_url
from .reputation import Publisher, ReputationRegister, normalise_name
from .web import CSV_MEDIA_TYPE, PDF_MEDIA_TYPE, XLSX_MEDIA_TYPE, FetchRefused, check_url

__all__ = [
    "AGGREGATOR_HOSTS",
    "ARCHIVE_HOSTS",
    "ARCHIVE_HOST_NOT_PERMITTED",
    "BARRIER_MIN_TEXT_CHARS",
    "GAP_PRIORITY",
    "LADDER_REQUEST_CAP",
    "LADDER_STATUS",
    "LADDER_VERSION",
    "PATH_DISCOVERY_CAP",
    "RUNG_ORDER",
    "Acquisition",
    "AcquisitionGap",
    "AcquisitionLead",
    "ArchivedFrom",
    "AttemptDecision",
    "AttemptTool",
    "DatasetRef",
    "GapReason",
    "LadderAttempt",
    "LadderRecord",
    "LadderStop",
    "LeadOrigin",
    "Match",
    "Rung",
    "SecondaryFinding",
    "TitleVariant",
    "archive_permits",
    "archived_original",
    "detect_barrier",
    "document_twins",
    "failure_reason",
    "gap_reason",
    "how_to_obtain",
    "is_archive_host",
    "is_archive_url",
    "lead_from_secondary",
    "link_matches",
    "matching_links",
    "parent_paths",
    "render_query",
    "satisfies",
]

#: The ladder's rules as a whole: rungs, matching, barriers, caps. A change is a new version.
LADDER_VERSION: Final = "aia-acquisition-ladder-1"
#: The owner has approved none of the lists or caps below (plan chunk 1).
LADDER_STATUS: Final = "proposed"
#: Requests one lead may make, across every rung (plan § 7: "default 12 requests").
LADDER_REQUEST_CAP: Final = 12
#: Of those, rung 10's same-host path discovery may make at most this many (plan § 7).
PATH_DISCOVERY_CAP: Final = 10
#: A captured page with no barrier marker is open only when it holds at least this much text.
BARRIER_MIN_TEXT_CHARS: Final = 1_500


class Rung(StrEnum):
    """The ladder's rungs, plan § 7, in the order they are tried."""

    DIRECT_LINK = "1_direct_link"
    OTHER_FORMATS = "2_other_formats"
    PUBLISHER_INDEX = "3_publisher_index"
    DATA_INTERFACE = "4_data_interface"
    EXACT_PHRASE = "5_exact_phrase"
    LANGUAGE_EDITION = "6_language_edition"
    SCHOLARLY_IDENTITY = "7_scholarly_identity"
    AGGREGATOR = "8_aggregator"
    ARCHIVED_COPY = "9_archived_copy"
    PATH_DISCOVERY = "10_path_discovery"
    GAP = "11_gap"


RUNG_ORDER: Final[tuple[Rung, ...]] = tuple(Rung)


class LeadOrigin(StrEnum):
    """Who raised a lead: an investigator, a secondary finding, a verifier, a primary trace."""

    INVESTIGATOR = "investigator"
    SECONDARY_FINDING = "secondary_finding"
    VERIFIER = "verifier"
    PRIMARY_TRACE = "primary_trace"


class Match(StrEnum):
    """How code found that a capture answers a lead."""

    DATASET = "dataset"
    PHRASE = "phrase"
    TITLE = "title"
    #: A DOI-only lead: the copy is at a location the DOI's own record names.
    IDENTITY = "identity"


class GapReason(StrEnum):
    """Why a lead could not be acquired, the most telling first (see :data:`GAP_PRIORITY`)."""

    PAYWALL = "paywall"
    LOGIN = "login"
    CHALLENGE = "challenge"
    #: Answered 401, 403 or 451: the publisher does not serve it to the public.
    NOT_PUBLIC = "not_public"
    #: The host's robots.txt forbids it (or could not be read): never worked round.
    ROBOTS = "robots"
    #: A call may have been served with no answer on record; nothing more was sent.
    UNCERTAIN = "uncertain"
    #: The per-lead cap ended the ladder.
    CAP_REACHED = "cap_reached"
    #: AIA's own policy refused what would have been sent (class, egress, scope).
    POLICY_REFUSED = "policy_refused"
    NOT_FOUND = "not_found"


#: The order a gap's reason is chosen in: a barrier says more about obtaining a source
#: than a cap, and a cap more than "not found".
GAP_PRIORITY: Final[tuple[GapReason, ...]] = tuple(GapReason)

_HOW: Final[dict[GapReason, str]] = {
    GapReason.PAYWALL: (
        "Zdroj je za platební bránou. Lze ho koupit nebo požádat vydavatele o přístup "
        "a nahrát ho do Znalostí klienta, kde se stane schváleným zdrojem."
    ),
    GapReason.LOGIN: (
        "Zdroj je dostupný jen po přihlášení. Kdo k němu má přístup, může ho stáhnout "
        "a nahrát do Znalostí klienta; aplikace se nepřihlašuje."
    ),
    GapReason.CHALLENGE: (
        "Vydavatel chrání zdroj ověřením (CAPTCHA). Lze ho stáhnout ručně a nahrát do "
        "Znalostí klienta, nebo požádat vydavatele o datový soubor."
    ),
    GapReason.NOT_PUBLIC: (
        "Vydavatel zdroj veřejně neposkytuje. Lze ho požádat o přístup nebo o data "
        "a výsledek nahrát do Znalostí klienta."
    ),
    GapReason.ROBOTS: (
        "Pravidla serveru (robots.txt) automatický přístup nedovolují. Zdroj lze "
        "otevřít ručně a nahrát do Znalostí klienta."
    ),
    GapReason.UNCERTAIN: (
        "Odpověď na poslední požadavek se ztratila a aplikace ho neopakuje. Hledání "
        "lze zopakovat v dalším běhu."
    ),
    GapReason.CAP_REACHED: (
        "Limit požadavků na jeden zdroj se vyčerpal. Zdroj lze dohledat ručně, "
        "případně požádat vydavatele."
    ),
    GapReason.POLICY_REFUSED: (
        "Pravidla aplikace dotaz nedovolila odeslat (třída dat nebo cesta). Zdroj "
        "lze dohledat ručně a nahrát do Znalostí klienta."
    ),
    GapReason.NOT_FOUND: (
        "Zdroj se veřejně nepodařilo najít. Lze se obrátit přímo na vydavatele nebo "
        "zdroj nahrát do Znalostí klienta, má-li ho někdo k dispozici."
    ),
}


def how_to_obtain(reason: GapReason) -> str:
    """How a person could obtain a source the ladder could not, by why it could not."""
    return _HOW[reason]


# --------------------------------------------------------------------------- #
# Hosts: archives, aggregators
# --------------------------------------------------------------------------- #

#: Archives, caches and mirrors: reached by rung 9 alone, with a permit (plan § 4).
ARCHIVE_HOSTS: Final = frozenset(
    {
        "web.archive.org",
        "archive.org",
        "wayback.archive.org",
        "data.commoncrawl.org",
        "index.commoncrawl.org",
        "archive.today",
        "archive.ph",
        "archive.is",
        "archive.li",
        "archive.vn",
        "archive.md",
        "archive.fo",
        "webcache.googleusercontent.com",
        "cachedview.nl",
        "ghostarchive.org",
        "webarchive.nla.gov.au",
        "webarchive.org.uk",
        "webarchiv.cz",
    }
)

#: Official aggregators that republish national figures (plan § 7 rung 8), proposed.
AGGREGATOR_HOSTS: Final[tuple[str, ...]] = (
    "ec.europa.eu",
    "eur-lex.europa.eu",
    "oecd.org",
    "data.gov.cz",
)


def _host(url: str) -> str:
    return (urlsplit(url).hostname or "").lower().rstrip(".").removeprefix("www.")


def _within(host: str, declared: str) -> bool:
    return host == declared or host.endswith("." + declared)


def is_archive_url(url: str) -> bool:
    """Whether ``url`` is on an archive's, a cache's or a mirror's host (or a subdomain)."""
    return is_archive_host(_host(url))


def is_archive_host(host: str) -> bool:
    """Whether ``host`` is an archive's, a cache's or a mirror's (or a subdomain of one)."""
    host = host.lower().rstrip(".").removeprefix("www.")
    return any(_within(host, a) for a in ARCHIVE_HOSTS)


#: Why a fetch of an archive, cache or mirror was refused: no permit for the page it copies.
ARCHIVE_HOST_NOT_PERMITTED: Final = "archive_host_not_permitted"
_WAYBACK_REPLAY: Final = re.compile(r"^/web/[0-9]{1,14}(?:[a-z]{2}_)?/(https?://.+)$")


def archived_original(url: str) -> str | None:
    """The page an archive URL is a copy of, when the archive's URL names it; else None.

    Only a Wayback replay (``https://web.archive.org/web/<timestamp>/<original>``) is
    read; every other archive, cache or mirror names no original code will trust, so
    no permit can open it.
    """
    parts = urlsplit(url)
    if _host(url) != "web.archive.org" or parts.scheme != "https":
        return None
    path = parts.path + (f"?{parts.query}" if parts.query else "")
    match = _WAYBACK_REPLAY.match(path)
    return match[1] if match else None


def archive_permits(permit_url: str | None, url: str) -> bool:
    """Whether a permit for ``permit_url`` opens ``url``: a live URL always (no archive is
    involved), an archive's URL only when it is a copy of exactly that page."""
    if not is_archive_url(url):
        return True
    original = archived_original(url)
    return (
        permit_url is not None
        and original is not None
        and (canonical_url(original) or original) == (canonical_url(permit_url) or permit_url)
    )


# --------------------------------------------------------------------------- #
# The lead
# --------------------------------------------------------------------------- #


class _Closed(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


_DOI: Final = re.compile(r"^10\.[0-9]{4,9}/[^\s,&\"<>]{1,200}$")
_PERIOD: Final = re.compile(r"^[0-9]{4}(?:[0-9]{2}){0,5}$")
_CONTROL: Final = re.compile(r"[\x00-\x1f\x7f\"]")


def _phrase(value: str) -> str:
    text = " ".join(value.split())
    if not text or _CONTROL.search(text):
        raise ValueError("a phrase is one line of text without a double quote")
    return text


class DatasetRef(_Closed):
    """A dataset a lead names: a connector (by its id) and the dataset's id there."""

    connector_id: str = Field(pattern=r"^[a-z0-9][a-z0-9.-]{1,62}$")
    dataset_id: str = Field(min_length=1, max_length=300)


class TitleVariant(_Closed):
    """The same publication under another title: another language, or another edition.

    ``period`` is the edition's period when it is not the one wanted (the previous
    edition, while the wanted one is not out); a capture by it says so.
    """

    title: str = Field(min_length=3, max_length=300)
    lang: Literal["cs", "en"]
    period: str | None = Field(default=None, max_length=20)

    @field_validator("title")
    @classmethod
    def _title(cls, value: str) -> str:
        return _phrase(value)


class AcquisitionLead(_Closed):
    """A source a track needs, in terms code can check (plan § 7).

    ``urls`` and ``cited_on`` come from code (a link a captured page carries, the
    page that cites the source), never from a model. ``phrases`` are distinctive
    text the source itself must contain -- a table title, a document number, the
    figure as printed; when there are any, only a capture holding one answers.
    ``cited_date`` (4 to 14 digits, as an archive takes it) is when the source was
    cited, for choosing an archived capture near it.
    """

    need: str = Field(min_length=1, max_length=300)
    publisher: str | None = Field(default=None, max_length=200)
    title: str | None = Field(default=None, min_length=3, max_length=300)
    phrases: tuple[str, ...] = Field(default=(), max_length=5)
    urls: tuple[str, ...] = Field(default=(), max_length=10)
    doi: str | None = Field(default=None, max_length=210)
    datasets: tuple[DatasetRef, ...] = Field(default=(), max_length=5)
    period: str | None = Field(default=None, max_length=20)
    variants: tuple[TitleVariant, ...] = Field(default=(), max_length=4)
    cited_on: str | None = Field(default=None, max_length=2048)
    cited_date: str | None = Field(default=None, pattern=_PERIOD.pattern)
    lang: Literal["cs", "en"] = "cs"
    origin: LeadOrigin

    @field_validator("title")
    @classmethod
    def _title(cls, value: str | None) -> str | None:
        return None if value is None else _phrase(value)

    @field_validator("phrases")
    @classmethod
    def _phrases(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        cleaned = tuple(_phrase(v) for v in value)
        if any(len(p) < 3 for p in cleaned):
            raise ValueError("a phrase has at least three characters")
        return cleaned

    @field_validator("doi")
    @classmethod
    def _doi(cls, value: str | None) -> str | None:
        if value is not None and not _DOI.fullmatch(value):
            raise ValueError("a DOI is 10.<registrant>/<suffix>")
        return value

    @field_validator("urls")
    @classmethod
    def _urls(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        for url in value:
            try:
                check_url(url)
            except FetchRefused as exc:
                raise ValueError(f"a lead's URL is a public web URL ({exc.reason})") from exc
        return value

    @model_validator(mode="after")
    def _checkable(self) -> AcquisitionLead:
        if not (self.phrases or self.title or self.doi or self.datasets or self.variants):
            raise ValueError(
                "a lead names a phrase, a title, a DOI or a dataset: code must be able "
                "to tell when it has found it"
            )
        return self

    @property
    def needle(self) -> str | None:
        """The text an archived copy must show the live page has lost (rung 9)."""
        if self.phrases:
            return self.phrases[0]
        return self.title


# --------------------------------------------------------------------------- #
# Barriers
# --------------------------------------------------------------------------- #

#: Markers by barrier, matched case-insensitively on the normalised text. Proposed.
_BARRIER_MARKERS: Final[tuple[tuple[AccessBarrier, re.Pattern[str]], ...]] = (
    (
        AccessBarrier.CHALLENGE,
        re.compile(
            r"captcha|verify (that )?you are (a )?human|are you a robot|checking your browser"
            r"|ověř(te)?,? že nejste robot|nejste robot|bot protection|cf-challenge",
            re.I,
        ),
    ),
    (
        AccessBarrier.PAYWALL,
        re.compile(
            r"subscribe to (continue|read)|subscribers only|for subscribers|paywall"
            r"|purchase (this|the) (report|article|study)|buy (this|the) (report|article|study)"
            r"|pro předplatitele|jen pro předplatitele|předplaťte si|zakupte si"
            r"|obsah je dostupný (pouze|jen) (pro )?předplatitel|placený obsah"
            r"|cena (zprávy|studie|reportu)",
            re.I,
        ),
    ),
    (
        AccessBarrier.LOGIN,
        re.compile(
            r"(log|sign) in to (continue|read|view|download)|please (log|sign) in"
            r"|members only|login required|přihlaste se|pro pokračování se přihlas"
            r"|obsah je dostupný (pouze|jen) po přihlášení|pouze pro (členy|registrované)",
            re.I,
        ),
    ),
)


def detect_barrier(snapshot: SourceSnapshot) -> AccessBarrier:
    """What stands between a reader and this capture's text, by declared markers.

    A dataset table is never behind a barrier. A page with no marker is ``NONE``
    only when it holds :data:`BARRIER_MIN_TEXT_CHARS` of text; a short page is
    ``UNKNOWN`` (a stub is what a paywall serves), and unknown permits nothing.
    """
    if snapshot.dataset is not None:
        return AccessBarrier.NONE
    text = normalise_text(f"{snapshot.title} {snapshot.text}")
    for barrier, pattern in _BARRIER_MARKERS:
        if pattern.search(text):
            return barrier
    return (
        AccessBarrier.NONE
        if len(snapshot.text) >= BARRIER_MIN_TEXT_CHARS
        else (AccessBarrier.UNKNOWN)
    )


# --------------------------------------------------------------------------- #
# Does a capture answer the lead?
# --------------------------------------------------------------------------- #


def _contains(text: str, needle: str) -> bool:
    return locate_quote(text, needle) is not None or (
        normalise_text(needle).casefold() in normalise_text(text).casefold()
    )


def satisfies(
    snapshot: SourceSnapshot,
    lead: AcquisitionLead,
    *,
    variant: TitleVariant | None = None,
    identity: bool = False,
) -> Match | None:
    """How ``snapshot`` answers ``lead``, or None (checked by code, never by a model).

    A table answers when it is a dataset the lead named and has rows. A page behind
    a barrier, or one carrying instructions, answers nothing. When the lead names
    phrases, a page answers only by holding one (case-insensitive, normalised);
    otherwise by holding the title in its text or its title. A ``variant`` (another
    language or edition, rung 6) is answered by its own title: the lead's phrases
    are printed in the wanted edition's language and period.
    ``identity`` is the DOI rung's: a DOI-only lead is answered by a location the
    DOI's own record names.
    """
    dataset = snapshot.dataset
    if dataset is not None:
        named = any(
            ref.connector_id == dataset.connector_id and ref.dataset_id == dataset.dataset_id
            for ref in lead.datasets
        )
        return Match.DATASET if named and dataset.rows else None
    if snapshot.instructions_detected or detect_barrier(snapshot) in (
        AccessBarrier.PAYWALL,
        AccessBarrier.LOGIN,
        AccessBarrier.CHALLENGE,
    ):
        return None
    if variant is None and lead.phrases:
        return Match.PHRASE if any(_contains(snapshot.text, p) for p in lead.phrases) else None
    title = variant.title if variant is not None else lead.title
    if title is not None and (_contains(snapshot.text, title) or _contains(snapshot.title, title)):
        return Match.TITLE
    if identity and lead.doi is not None and lead.title is None and not lead.variants:
        return Match.IDENTITY
    return None


# --------------------------------------------------------------------------- #
# Candidates: links, twins, paths, queries
# --------------------------------------------------------------------------- #

_WORD: Final = re.compile(r"[a-z0-9]+")
_DOC_SUFFIX: Final = {".pdf": PDF_MEDIA_TYPE, ".xlsx": XLSX_MEDIA_TYPE, ".csv": CSV_MEDIA_TYPE}
_DOC_TYPES: Final = frozenset(_DOC_SUFFIX.values())


def _ascii_words(text: str) -> list[str]:
    folded = unicodedata.normalize("NFKD", text)
    plain = "".join(c for c in folded if not unicodedata.combining(c)).casefold()
    return _WORD.findall(plain)


def _significant(text: str) -> set[str]:
    return {w for w in _ascii_words(text) if len(w) >= 4 or w.isdigit()}


def link_matches(lead: AcquisitionLead, url: str, text: str) -> bool:
    """Whether a link (its anchor text and its URL's path) names what the lead needs.

    Its text holds a phrase or the title; or at least two thirds of the title's
    significant words (four letters or more, or a number), and at least two, are
    in its text or its path.
    """
    for needle in (*lead.phrases, *([lead.title] if lead.title else [])):
        if text and normalise_text(needle).casefold() in normalise_text(text).casefold():
            return True
    titles = [lead.title] if lead.title else []
    titles += [v.title for v in lead.variants]
    have = _significant(f"{text} {unquote(urlsplit(url).path)}")
    for title in titles:
        want = _significant(title)
        if len(want) >= 2 and len(want & have) * 3 >= len(want) * 2:
            return True
    return False


def _key(url: str) -> str:
    return canonical_url(url) or url


def _unique(urls: Iterable[str]) -> tuple[str, ...]:
    seen: set[str] = set()
    out: list[str] = []
    for url in urls:
        key = _key(url)
        if key in seen:
            continue
        seen.add(key)
        out.append(url)
    return tuple(out)


def _public(url: str) -> bool:
    try:
        check_url(url)
    except FetchRefused:
        return False
    return not is_archive_url(url)


def matching_links(
    lead: AcquisitionLead, snapshot: SourceSnapshot, *, host: str | None = None
) -> tuple[str, ...]:
    """The anchor links of ``snapshot`` that name what the lead needs (on ``host`` only, if given).

    Never a link to an archive's host, never the page itself.
    """
    own = _key(snapshot.final_url)
    out = [
        link.url
        for link in snapshot.links
        if link.kind == "anchor"
        and _key(link.url) != own
        and _public(link.url)
        and (host is None or _host(link.url) == host)
        and link_matches(lead, link.url, link.text)
    ]
    return _unique(out)


def _doc_type(url: str, media_type: str | None) -> str | None:
    if media_type is not None:
        media = media_type.split(";", 1)[0].strip().lower()
        return media if media in _DOC_TYPES else None
    path = urlsplit(url).path.lower()
    return next((t for s, t in _DOC_SUFFIX.items() if path.endswith(s)), None)


def document_twins(lead: AcquisitionLead, snapshot: SourceSnapshot) -> tuple[str, ...]:
    """The PDF, XLSX or CSV twins of an HTML release, on its own host (rung 2).

    Its ``alternate`` links of a document type, then its anchor links to a document
    on the same host; those naming the lead first. A document is no release with
    twins: nothing for a capture that is itself a document or a table.
    """
    if snapshot.document is not None or snapshot.dataset is not None:
        return ()
    host = _host(snapshot.final_url)
    own = _key(snapshot.final_url)
    alternates: list[str] = []
    naming: list[str] = []
    others: list[str] = []
    for link in snapshot.links:
        if _key(link.url) == own or not _public(link.url) or _host(link.url) != host:
            continue
        if _doc_type(link.url, link.media_type) is None:
            continue
        if link.kind == "alternate":
            alternates.append(link.url)
        elif link_matches(lead, link.url, link.text):
            naming.append(link.url)
        else:
            others.append(link.url)
    return _unique([*alternates, *naming, *others])


def parent_paths(url: str, *, limit: int) -> tuple[str, ...]:
    """The URL's parent directories on its own host, nearest first, the root last (rung 10)."""
    parts = urlsplit(url)
    segments = [s for s in parts.path.split("/") if s]
    out: list[str] = []
    for depth in range(len(segments) - 1, -1, -1):
        path = "/" + "/".join(segments[:depth]) + ("/" if depth else "")
        out.append(urlunsplit((parts.scheme, parts.netloc, path, "", "")))
        if len(out) >= limit:
            break
    return _unique(out)


_SITE: Final = re.compile(
    r"(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z](?:[a-z0-9-]{0,61}[a-z0-9])?"
)


def render_query(*, words: str | None, phrase: str | None, site: str | None) -> str:
    """A search the ladder writes: plain words, then a "phrase", then site:host.

    Code writes every operator; a site is a bare public host. Raises ValueError for
    anything else (nothing is sent).
    """
    parts: list[str] = []
    if words:
        parts.append(" ".join(_phrase(words).split()))
    if phrase:
        parts.append(f'"{_phrase(phrase)}"')
    if site is not None:
        if not _SITE.fullmatch(site):
            raise ValueError("a site is a bare lower-case host")
        check_url(f"https://{site}/")
        parts.append(f"site:{site}")
    if not parts:
        raise ValueError("a query says something")
    return " ".join(parts)


# --------------------------------------------------------------------------- #
# Why nothing worked
# --------------------------------------------------------------------------- #

_POLICY_PREFIXES: Final = ("egress_", "class_a", "url_", "address_", "dataset_class")
_POLICY: Final = frozenset(
    {
        "host_out_of_scope",
        "redirect_out_of_scope",
        "tool_metering_unavailable",
        "archive_not_permitted",
        "archive_host_not_permitted",
        "dataset_connector_unavailable",
    }
)


def failure_reason(reason: str | None) -> GapReason | None:
    """What one failed or refused call says about reaching the source; None: nothing."""
    if reason is None:
        return None
    if reason == "http_402":
        return GapReason.PAYWALL
    if reason in ("http_401", "http_403", "http_451"):
        return GapReason.NOT_PUBLIC
    if reason.startswith("robots_"):
        return GapReason.ROBOTS
    if reason in _POLICY or reason.startswith(_POLICY_PREFIXES):
        return GapReason.POLICY_REFUSED
    return None


def gap_reason(met: Iterable[GapReason]) -> GapReason:
    """The most telling reason among those the attempts met; ``NOT_FOUND`` when none."""
    seen = set(met)
    return next((r for r in GAP_PRIORITY if r in seen), GapReason.NOT_FOUND)


class AcquisitionGap(_Closed):
    """A source the ladder could not reach by any lawful public route (plan §§ 4, 7, 8.6).

    Shaped to be unified with the brief's acquisition gap (plan chunk 13): publisher,
    title, url, need, reason and the rungs tried, plus how a person could obtain it.
    """

    kind: Literal["acquisition_gap"] = "acquisition_gap"
    publisher: str | None
    title: str | None
    url: str | None
    need: str
    reason: GapReason
    rungs_tried: tuple[Rung, ...]
    how_to_obtain: str
    detail: str = Field(default="", max_length=1000)

    @classmethod
    def of(
        cls,
        lead: AcquisitionLead,
        *,
        reason: GapReason,
        rungs_tried: Sequence[Rung],
        detail: str = "",
    ) -> AcquisitionGap:
        """The gap a lead leaves: its publisher, title and first known URL, and why."""
        return cls(
            publisher=lead.publisher,
            title=lead.title or (lead.variants[0].title if lead.variants else None),
            url=lead.urls[0] if lead.urls else None,
            need=lead.need,
            reason=reason,
            rungs_tried=(*rungs_tried, Rung.GAP),
            how_to_obtain=how_to_obtain(reason),
            detail=detail[:1000],
        )


# --------------------------------------------------------------------------- #
# What one climb did (the ladder's record, stored with the turn that asked)
# --------------------------------------------------------------------------- #


class AttemptDecision(StrEnum):
    SENT = "sent"
    CACHED = "cached"
    REFUSED = "refused"
    #: Not sent by this ladder: the track allowance is spent, or the candidate is barred.
    SKIPPED = "skipped"


AttemptTool = Literal[
    "search",
    "fetch",
    "resource",
    "dataset",
    "archive_lookup",
    "url_index",
    "archived_fetch",
    "archive_permit",
]


class LadderAttempt(_Closed):
    """One step of the climb: a gate call, or a decision code made without one."""

    rung: Rung
    tool: AttemptTool
    #: What was asked: a URL, a query as sent, a dataset query's text.
    target: str = Field(max_length=4100)
    decision: AttemptDecision
    reason: str | None = None
    outcome: Literal["succeeded", "failed", "uncertain"] | None = None
    data_class: DataClass | None = None
    call_id: str | None = None
    #: SHA256 of what the gate journaled as sent; None when nothing was dispatched.
    request_fingerprint: str | None = None
    snapshot_id: str | None = None
    #: Counted against the lead's cap.
    counted: bool = False


class ArchivedFrom(_Closed):
    """An acquisition read from an archive: which, why it was allowed, and when captured."""

    archive: Literal["wayback", "common_crawl"]
    basis: ArchiveBasis
    #: The capture's time as the archive states it (a 14-digit timestamp or ISO time).
    captured: str


class Acquisition(_Closed):
    """The capture that answered a lead, the rung that reached it, and how it answered."""

    rung: Rung
    url: str
    snapshot_id: str
    match: Match
    #: On one of the resolved publisher's registered hosts (a primary source by host).
    on_publisher_host: bool
    archived: ArchivedFrom | None = None
    #: The edition's period, when a previous edition answered (rung 6).
    edition_period: str | None = None


class LadderStop(StrEnum):
    ACQUIRED = "acquired"
    GAP = "gap"
    #: A call may have been served with no answer on record: nothing more is sent.
    UNCERTAIN = "uncertain"
    #: An earlier attempt of the step dispatched a call this ladder would send.
    EARLIER_ATTEMPT = "earlier_attempt"


class LadderRecord(_Closed):
    """What one climb did, for the transcript: every attempt, and how it ended."""

    version: Literal["aia-acquisition-ladder-1"] = LADDER_VERSION
    lead: AcquisitionLead
    stop: LadderStop
    acquisition: Acquisition | None
    gap: AcquisitionGap | None
    rungs_tried: tuple[Rung, ...]
    attempts: tuple[LadderAttempt, ...]
    requests: int = Field(ge=0)
    searches: int = Field(ge=0)
    fetches: int = Field(ge=0)


# --------------------------------------------------------------------------- #
# Secondary findings raise primary leads (plan § 8.3)
# --------------------------------------------------------------------------- #

#: Characters either side of a quote read for who it cites.
_CONTEXT_CHARS: Final = 400
#: A name this short is too likely to be an ordinary word to be read as a citation.
_MIN_CITED_NAME: Final = 3
_NUMBER: Final = re.compile(r"\d+(?:[ \u00a0]\d{3})*(?:[,.]\d+)?(?:\s?(?:%|‰|p\. ?b\.))?")


class SecondaryFinding(_Closed):
    """A grounded finding as primary tracing reads it: its quote, claim, page, period."""

    quote: str = Field(min_length=1, max_length=800)
    claim: str = Field(min_length=1, max_length=1200)
    period: str | None = Field(default=None, max_length=40)
    origin: LeadOrigin = LeadOrigin.SECONDARY_FINDING


def _names_in(text: str, register: ReputationRegister) -> list[Publisher]:
    """The publishers whose declared names occur, as whole words, in ``text``."""
    haystack = f" {normalise_name(text)} "
    found: list[Publisher] = []
    for publisher in register.publishers:
        for name in publisher.all_names:
            key = normalise_name(name)
            if len(key) >= _MIN_CITED_NAME and f" {key} " in haystack:
                found.append(publisher)
                break
    return found


def lead_from_secondary(
    finding: SecondaryFinding, *, citing: SourceSnapshot, register: ReputationRegister
) -> AcquisitionLead | None:
    """The lead a secondary finding raises for its primary, or None when there is none.

    The finding is secondary when the text around its quote names, or the page links
    to, a registered publisher other than the page's own. The lead names that
    publisher; its URLs are the page's links to the publisher's hosts (the primary
    itself, often); its phrases are the figures the quote states, as printed (the
    primary must hold one); its title is the anchor text of a link naming one of them.
    A page that names no other publisher, or a publisher it is itself, raises nothing:
    an untraceable figure is left secondary, never guessed at.
    """
    own = register.publisher_for_host(_host(citing.final_url))
    span = locate_quote(citing.text, finding.quote)
    text = normalise_text(citing.text)
    if span is None:
        return None
    window = text[max(0, span[0] - _CONTEXT_CHARS) : span[1] + _CONTEXT_CHARS]
    cited = [p for p in _names_in(window, register) if p is not own]
    linked: dict[str, list[tuple[str, str]]] = {}
    for link in citing.links:
        if link.kind != "anchor" or not _public(link.url):
            continue
        publisher = register.publisher_for_host(_host(link.url))
        if publisher is not None and publisher is not own:
            linked.setdefault(publisher.canonical_name, []).append((link.url, link.text))
    target = cited[0] if cited else None
    if target is None and len(linked) == 1:
        target = register.resolve_publisher(next(iter(linked)))
    if target is None:
        return None
    numbers = _unique(n.strip() for n in _NUMBER.findall(finding.quote))
    phrases = tuple(n for n in numbers if len(n) >= 3)[:5]
    links = linked.get(target.canonical_name, [])
    title = next((t for _, t in links if len(t) >= 3 and _CONTROL.search(t) is None), None)
    if not phrases and title is None:
        return None
    return AcquisitionLead(
        need=f"Primární zdroj údaje: {finding.claim}"[:300],
        publisher=target.canonical_name,
        title=title[:300] if title else None,
        phrases=phrases,
        urls=_unique(u for u, _ in links)[:10],
        period=finding.period[:20] if finding.period else None,
        cited_on=citing.final_url,
        origin=finding.origin,
    )
