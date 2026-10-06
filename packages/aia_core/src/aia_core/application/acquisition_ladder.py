"""The acquisition ladder: every lawful public way to reach a source a track needs.

Plan ``deep-research-web-search.md`` § 7, chunk 10. :func:`ladder` takes an
:class:`~aia_core.domain.deep_research.acquisition.AcquisitionLead` and climbs eleven
rungs **in order**, stopping at the first capture that answers the lead
(``acquisition.satisfies``, checked by code):

1. **Direct link** -- the lead's known URLs, then the citing page's links naming it
   (``fetch``).
2. **Other formats** -- the PDF, XLSX or CSV twins of an HTML release, on its own host
   (``fetch``, host-confined).
3. **Publisher's index** -- ``"phrase" site:<host>`` on each registered host of the
   publisher, then its sitemap's entries naming the lead (``search``,
   ``fetch_resource``, ``fetch`` host-confined).
4. **Data interface** -- each dataset the lead names, on the publisher's own connector
   (``dataset``).
5. **Exact phrase** -- each phrase, then the title, in quotes (``search``, ``fetch``).
6. **Language and edition** -- each title variant: the other language, a previous
   edition, its period recorded (``search``, ``fetch``).
7. **Scholarly identity** -- the DOI (or the title's, found by an OpenAlex search) to
   a location OpenAlex marks open access (``dataset``, ``fetch``).
8. **Official aggregators** -- a dataset on an aggregator's connector, then
   ``"phrase" site:<aggregator>`` (``dataset``, ``search``, ``fetch``).
9. **Archived copy** -- only with a permit (dead, moved, changed): Wayback, then Common
   Crawl, the capture nearest the cited date (``archive``, ``fetch`` of the replay,
   ``query_url_index``, ``fetch_archived``).
10. **Path discovery** -- a dead URL's parent paths on its own host, then their links
    naming the lead (``fetch``, host-confined).
11. **Acquisition gap** -- nothing worked: publisher, title, reason, the rungs tried and
    how a person could obtain it. No call.

**No new path out.** Every request is a :class:`~.web_retrieval.RetrievalGate` call --
classified, egress-checked, reserved and journaled -- and its transport keeps
robots.txt and pacing; this module imports no transport and no HTTP client
(``tools/layer_check.sh``). A refusal is recorded and never rerouted.

**The boundaries (plan § 4).** A paywall, a login, a challenge, a ``401/402/403/451``
or a robots.txt refusal is met, recorded and reported as the gap's reason; nothing
here works round one. Rungs 1-8 and 10 refuse any candidate on an archive's, a
cache's or a mirror's host (``acquisition.is_archive_url``). Rung 9 asks an archive
only with an :class:`~aia_core.domain.deep_research.archive.ArchivePermit` that
``decide_archive_use`` issued for that very URL from the live attempt this ladder
made -- for Wayback (whose gate call demands it) and for Common Crawl's index and
archived records (whose gate calls do not, so this module refuses them itself). A
live page behind a barrier, or a short page nobody can tell is open, gets no permit.

**The cap.** A lead may make at most ``limits.requests`` requests (plan § 7: 12,
proposed), rung 10 at most ``limits.path_discovery`` of them (10). A call counts
unless the gate says nothing left (a cache hit, a refusal before dispatch); a sitemap,
an index query or an archived read always counts (their outcomes cannot tell).
Searches and fetches are also bounded by what the track has left (``limits.searches``,
``limits.fetches``; a dataset or archive query is a fetch); the track's money
is its meter's (``ToolBudgetExhausted`` propagates and ends the track, as the gate
documents). An uncertain call ends the ladder: nothing is sent again.

**A resumed step** passes ``may_send``: a call whose journaled text an earlier attempt
already dispatched is not sent again, and the ladder stops there
(:attr:`LadderStop.EARLIER_ATTEMPT`) -- its answer is not on record.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Callable, Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from typing import Final, Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, ValidationError

from ..domain.deep_research.acquisition import (
    AGGREGATOR_HOSTS,
    LADDER_REQUEST_CAP,
    PATH_DISCOVERY_CAP,
    Acquisition,
    AcquisitionGap,
    AcquisitionLead,
    ArchivedFrom,
    AttemptDecision,
    AttemptTool,
    DatasetRef,
    GapReason,
    LadderAttempt,
    LadderRecord,
    LadderStop,
    Rung,
    TitleVariant,
    detect_barrier,
    document_twins,
    failure_reason,
    gap_reason,
    is_archive_url,
    link_matches,
    matching_links,
    parent_paths,
    render_query,
    satisfies,
)
from ..domain.deep_research.archive import (
    AccessBarrier,
    ArchivePermit,
    LiveAttempt,
    decide_archive_use,
)
from ..domain.deep_research.common_crawl import (
    IndexQueryInvalid,
    IndexRow,
    IndexTarget,
    UrlIndexQuery,
)
from ..domain.deep_research.contracts import QueryDecision, SourceSnapshot
from ..domain.deep_research.datasets import DatasetQuery, DimensionFilter
from ..domain.deep_research.legacy import canonical_url
from ..domain.deep_research.reputation import Publisher, ReputationRegister
from ..domain.deep_research.sitemaps import (
    MAX_SITEMAP_BYTES,
    SITEMAP_MEDIA_TYPES,
    SitemapKind,
    SitemapRefused,
    read_sitemap,
)
from ..domain.deep_research.web import SearchHit
from ..domain.residency import DataClass
from ..infrastructure.dataset_datastat import DATASTAT_CONNECTOR_ID
from ..infrastructure.dataset_eurostat import EUROSTAT_CONNECTOR_ID
from ..infrastructure.dataset_nkod import NKOD_CONNECTOR_ID
from ..infrastructure.dataset_openalex import OPENALEX_CONNECTOR_ID, open_access_copies
from ..infrastructure.dataset_wayback import WAYBACK_CONNECTOR_ID, nearest_capture
from .web_retrieval import (
    FetchOutcome,
    RetrievalGate,
    live_attempt,
    request_fingerprint,
    sent_archived,
    sent_search,
)

__all__ = [
    "DATA_INTERFACE_CONNECTORS",
    "RUNGS",
    "Climb",
    "LadderConfig",
    "LadderLimits",
    "LadderResult",
    "ladder",
    "rung_aggregator",
    "rung_archived_copy",
    "rung_data_interface",
    "rung_direct_link",
    "rung_exact_phrase",
    "rung_language_edition",
    "rung_other_formats",
    "rung_path_discovery",
    "rung_publisher_index",
    "rung_scholarly_identity",
]

#: A register's data interface (by name) -> the connector that queries it.
DATA_INTERFACE_CONNECTORS: Final[Mapping[str, str]] = {
    "datastat": DATASTAT_CONNECTOR_ID,
    "eurostat_api": EUROSTAT_CONNECTOR_ID,
    "nkod_sparql": NKOD_CONNECTOR_ID,
}
#: Connectors of official aggregators that republish national figures (rung 8).
AGGREGATOR_CONNECTORS: Final = frozenset({EUROSTAT_CONNECTOR_ID, NKOD_CONNECTOR_ID})
#: Where a Wayback capture table keeps each capture's replay URL.
_REPLAY_HOST: Final = "web.archive.org"


class _Closed(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


@dataclass(frozen=True, slots=True)
class LadderLimits:
    """How much one lead may ask. ``searches``/``fetches``: what the track has left."""

    requests: int = LADDER_REQUEST_CAP
    path_discovery: int = PATH_DISCOVERY_CAP
    searches: int | None = None
    fetches: int | None = None

    def __post_init__(self) -> None:
        if self.requests < 0 or self.path_discovery < 0:
            raise ValueError("a cap is not negative")


@dataclass(frozen=True, slots=True)
class LadderConfig:
    """What the composition gives the ladder beyond the gate.

    ``register`` resolves publishers (rungs 3, 4, 8); none: those rungs have nothing
    to resolve. ``crawls`` are the Common Crawl crawls rung 9 may ask (none: it asks
    only Wayback). ``opens_per_search`` bounds the hits a search may open.
    """

    register: ReputationRegister | None = None
    interfaces: Mapping[str, str] = field(default_factory=lambda: dict(DATA_INTERFACE_CONNECTORS))
    aggregator_connectors: frozenset[str] = AGGREGATOR_CONNECTORS
    aggregator_hosts: tuple[str, ...] = AGGREGATOR_HOSTS
    crawls: tuple[str, ...] = ()
    hits_per_search: int = 8
    opens_per_search: int = 2


@dataclass(frozen=True, slots=True)
class LadderResult:
    """The record, and the capture that answered (snapshot and publication date)."""

    record: LadderRecord
    capture: tuple[SourceSnapshot, date | None] | None


class _Stop(Exception):
    def __init__(self, stop: LadderStop, reason: GapReason | None) -> None:
        super().__init__(stop.value)
        self.stop = stop
        self.reason = reason


class _Found(Exception):
    def __init__(self, acquisition: Acquisition, capture: tuple[SourceSnapshot, date | None]):
        super().__init__(acquisition.rung.value)
        self.acquisition = acquisition
        self.capture = capture


def _key(url: str) -> str:
    return canonical_url(url) or url


def _host(url: str) -> str:
    return (urlsplit(url).hostname or "").lower().rstrip(".").removeprefix("www.")


class Climb:
    """One lead's climb: the gate, what it has met, and the calls it may still make.

    Every rung asks through the helpers here (:meth:`fetch`, :meth:`search`,
    :meth:`dataset`, ...), which hold the cap, record each attempt and what it met,
    and stop the climb on an uncertain call or an earlier attempt's dispatch.
    """

    def __init__(
        self,
        lead: AcquisitionLead,
        *,
        gate: RetrievalGate,
        track_id: str,
        context_class: DataClass,
        config: LadderConfig,
        limits: LadderLimits,
        citing: SourceSnapshot | None = None,
        may_send: Callable[[str], bool] | None = None,
    ) -> None:
        self.lead = lead
        self.gate = gate
        self.track_id = track_id
        self.context_class = context_class
        self.config = config
        self.limits = limits
        self.citing = citing
        self._may_send = may_send
        self.publisher: Publisher | None = (
            config.register.resolve_publisher(lead.publisher)
            if config.register is not None and lead.publisher is not None
            else None
        )
        self.attempts: list[LadderAttempt] = []
        self.met: list[GapReason] = []
        self.requests = 0
        self.searches = 0
        self.fetches = 0
        self.rung: Rung = Rung.DIRECT_LINK
        #: Every page this climb captured, in order (rung 2 reads their twins).
        self.pages: list[SourceSnapshot] = []
        #: The live attempt this climb made of each URL (rung 9 decides on it).
        self.live: dict[str, LiveAttempt] = {}
        self._fetched: dict[str, FetchOutcome] = {}
        self._published: dict[str, date | None] = {}
        self._searched: set[str] = set()
        self._datasets: set[str] = set()

    # ------------------------------------------------------------- the cap --

    def _room(self, *, search: bool = False, fetch: bool = False) -> bool:
        """Whether one more call fits; raises the cap stop when the lead's cap is spent."""
        if self.requests >= self.limits.requests:
            raise _Stop(LadderStop.GAP, GapReason.CAP_REACHED)
        if search and self.limits.searches is not None and self.searches >= self.limits.searches:
            return False
        return not (
            fetch and self.limits.fetches is not None and self.fetches >= self.limits.fetches
        )

    def _earlier(self, tool: AttemptTool, sent: str) -> None:
        """Stop before sending what an earlier attempt of the step already dispatched."""
        if self._may_send is not None and not self._may_send(sent):
            self.attempts.append(
                LadderAttempt(
                    rung=self.rung,
                    tool=tool,
                    target=sent[:4100],
                    decision=AttemptDecision.SKIPPED,
                    reason="sent_by_an_earlier_attempt",
                )
            )
            raise _Stop(LadderStop.EARLIER_ATTEMPT, None)

    def _record(
        self,
        tool: AttemptTool,
        target: str,
        *,
        sent: bool,
        cached: bool = False,
        reason: str | None,
        uncertain: bool = False,
        data_class: DataClass | None = None,
        call_id: str | None = None,
        fingerprint: str | None = None,
        snapshot_id: str | None = None,
        counted: bool,
    ) -> None:
        if counted:
            self.requests += 1
        if cached:
            decision = AttemptDecision.CACHED
        elif sent:
            decision = AttemptDecision.SENT
        else:
            decision = AttemptDecision.REFUSED
        outcome: Literal["succeeded", "failed", "uncertain"] | None = None
        if decision is AttemptDecision.SENT:
            outcome = "uncertain" if uncertain else ("failed" if reason else "succeeded")
        self.attempts.append(
            LadderAttempt(
                rung=self.rung,
                tool=tool,
                target=target[:4100],
                decision=decision,
                reason=reason,
                outcome=outcome,
                data_class=data_class,
                call_id=call_id,
                request_fingerprint=fingerprint,
                snapshot_id=snapshot_id,
                counted=counted,
            )
        )
        met = failure_reason(reason)
        if met is not None:
            self.met.append(met)
        if uncertain:
            self.met.append(GapReason.UNCERTAIN)
            raise _Stop(LadderStop.UNCERTAIN, GapReason.UNCERTAIN)

    def _skip(self, tool: AttemptTool, target: str, reason: str) -> None:
        self.attempts.append(
            LadderAttempt(
                rung=self.rung,
                tool=tool,
                target=target[:4100],
                decision=AttemptDecision.SKIPPED,
                reason=reason,
            )
        )

    # -------------------------------------------------------------- calls --

    def fetch(
        self, url: str, *, same_host: bool = False, archive_permit: ArchivePermit | None = None
    ) -> SourceSnapshot | None:
        """One page through the gate; its live attempt and any barrier it shows are kept.

        A URL on an archive's host is fetched only with a permit (rung 9's replay); a
        URL this climb already asked is answered from what came back then.
        """
        if is_archive_url(url) and archive_permit is None:
            self._skip("fetch", url, "archive_host_without_permit")
            return None
        known = self._fetched.get(_key(url))
        if known is not None:
            return known.page.snapshot if known.page is not None else None
        if not self._room(fetch=True):
            self._skip("fetch", url, "track_allowance_spent")
            return None
        self._earlier("fetch", url)
        host = _host(url)
        outcome = self.gate.fetch(
            url,
            track_id=self.track_id,
            host_allowed=(lambda h: h == host) if same_host else None,
            permit=archive_permit,
        )
        self._fetched[_key(url)] = outcome
        dispatched = outcome.call_id is not None
        if dispatched:
            self.fetches += 1
        snapshot = outcome.page.snapshot if outcome.page is not None else None
        barrier = detect_barrier(snapshot) if snapshot is not None else None
        if archive_permit is None:
            self.live[url] = live_attempt(outcome, barrier=barrier)
        if barrier in (AccessBarrier.PAYWALL, AccessBarrier.LOGIN, AccessBarrier.CHALLENGE):
            self.met.append(GapReason(barrier.value))
        self._record(
            "fetch",
            url,
            sent=dispatched,
            cached=outcome.cached,
            reason=outcome.reason,
            uncertain=outcome.uncertain,
            data_class=outcome.data_class,
            call_id=outcome.call_id,
            fingerprint=outcome.request_fingerprint,
            snapshot_id=snapshot.snapshot_id if snapshot is not None else None,
            counted=dispatched,
        )
        if snapshot is not None:
            self.pages.append(snapshot)
            self._published[snapshot.snapshot_id] = (
                outcome.page.published if outcome.page is not None else None
            )
        return snapshot

    def search(self, query: str, *, lang: str) -> tuple[SearchHit, ...]:
        """One search through the gate, at most once per climb; its hits, archives dropped."""
        sent = sent_search(query, lang)
        if sent in self._searched:
            return ()
        self._searched.add(sent)
        if not self._room(search=True):
            self._skip("search", sent, "track_allowance_spent")
            return ()
        self._earlier("search", sent)
        outcome = self.gate.search(
            query,
            context_class=self.context_class,
            track_id=self.track_id,
            max_results=self.config.hits_per_search,
            lang=lang,
        )
        record = outcome.record
        dispatched = record.call_id is not None
        if dispatched:
            self.searches += 1
        self._record(
            "search",
            sent,
            sent=dispatched,
            reason=record.refusal if record.decision is QueryDecision.REFUSED else record.failure,
            uncertain=outcome.uncertain,
            data_class=record.data_class,
            call_id=record.call_id,
            fingerprint=outcome.request_fingerprint,
            counted=dispatched,
        )
        return tuple(h for h in outcome.hits if not is_archive_url(h.url))

    def dataset(
        self, query: DatasetQuery, *, permit: ArchivePermit | None = None
    ) -> SourceSnapshot | None:
        """One connector query (an archive lookup with ``permit``), at most once per climb."""
        tool: AttemptTool = "archive_lookup" if permit is not None else "dataset"
        sent = query.text()
        if query.fingerprint() in self._datasets:
            return None
        self._datasets.add(query.fingerprint())
        has = (
            self.gate.has_archive(query.connector_id)
            if permit is not None
            else self.gate.has_dataset(query.connector_id)
        )
        if not has:
            # The composition gave the gate no such route: nothing to try, send or journal.
            return None
        if not self._room(fetch=True):
            self._skip(tool, sent, "track_allowance_spent")
            return None
        self._earlier(tool, sent)
        if permit is not None:
            outcome = self.gate.archive(
                query, permit=permit, context_class=self.context_class, track_id=self.track_id
            )
        else:
            outcome = self.gate.dataset(
                query, context_class=self.context_class, track_id=self.track_id
            )
        record = outcome.record
        dispatched = record.call_id is not None
        if dispatched:
            self.fetches += 1
        self._record(
            tool,
            f"{query.connector_id} {sent}",
            sent=dispatched,
            reason=record.refusal if record.decision is QueryDecision.REFUSED else record.failure,
            uncertain=outcome.uncertain,
            data_class=record.data_class,
            call_id=record.call_id,
            fingerprint=request_fingerprint(sent) if dispatched else None,
            snapshot_id=outcome.snapshot.snapshot_id if outcome.snapshot is not None else None,
            counted=dispatched,
        )
        if outcome.snapshot is not None:
            self._published[outcome.snapshot.snapshot_id] = None
        return outcome.snapshot

    def sitemap(self, url: str) -> tuple[str, ...]:
        """The page URLs one sitemap lists (an index is not followed), through the gate."""
        if not self._room(fetch=True):
            self._skip("resource", url, "track_allowance_spent")
            return ()
        self._earlier("resource", url)
        host = _host(url)
        outcome = self.gate.fetch_resource(
            url,
            track_id=self.track_id,
            media_types=SITEMAP_MEDIA_TYPES,
            max_bytes=MAX_SITEMAP_BYTES,
            host_allowed=lambda h: h == host,
        )
        self.fetches += 1
        self._record(
            "resource",
            url,
            sent=True,
            reason=outcome.reason,
            uncertain=outcome.uncertain,
            fingerprint=request_fingerprint(url),
            counted=True,
        )
        if outcome.resource is None:
            return ()
        try:
            read = read_sitemap(outcome.resource.body, media_type=outcome.resource.media_type)
        except SitemapRefused:
            return ()
        if read.kind is not SitemapKind.URLSET:
            return ()
        return tuple(e.url for e in read.entries)

    def url_index(self, query: UrlIndexQuery, permit: ArchivePermit) -> tuple[IndexRow, ...]:
        """Common Crawl's captures of one URL, only with that URL's permit."""
        if query.target is not IndexTarget.URL or permit.url != query.value:
            self._skip("url_index", query.value, "archive_not_permitted")
            return ()
        if not self._room(fetch=True):
            self._skip("url_index", query.value, "track_allowance_spent")
            return ()
        statement = self.gate.index_statement(query)
        self._earlier("url_index", statement)
        outcome = self.gate.query_url_index(
            query, context_class=self.context_class, track_id=self.track_id
        )
        self.fetches += 1
        self._record(
            "url_index",
            statement,
            sent=True,
            reason=outcome.reason,
            uncertain=outcome.uncertain,
            data_class=outcome.data_class,
            fingerprint=request_fingerprint(statement),
            counted=True,
        )
        return outcome.rows

    def archived(self, row: IndexRow, permit: ArchivePermit) -> SourceSnapshot | None:
        """One archived record, only with the permit for the URL it is a capture of."""
        sent = sent_archived(row)
        if permit.url != row.url:
            self._skip("archived_fetch", sent, "archive_not_permitted")
            return None
        if not self._room(fetch=True):
            self._skip("archived_fetch", sent, "track_allowance_spent")
            return None
        self._earlier("archived_fetch", sent)
        outcome = self.gate.fetch_archived(row, track_id=self.track_id)
        self.fetches += 1
        snapshot = outcome.page.snapshot if outcome.page is not None else None
        self._record(
            "archived_fetch",
            sent,
            sent=True,
            reason=outcome.reason,
            uncertain=outcome.uncertain,
            fingerprint=request_fingerprint(sent),
            snapshot_id=snapshot.snapshot_id if snapshot is not None else None,
            counted=True,
        )
        if snapshot is not None and outcome.page is not None:
            self._published[snapshot.snapshot_id] = outcome.page.published
        return snapshot

    # ----------------------------------------------------------- answering --

    def on_publisher_host(self, url: str) -> bool:
        if self.publisher is None:
            return False
        host = _host(url)
        return any(host == h or host.endswith("." + h) for h in self.publisher.hosts)

    def answer(
        self,
        snapshot: SourceSnapshot | None,
        *,
        url: str,
        variant: TitleVariant | None = None,
        identity: bool = False,
        archived: ArchivedFrom | None = None,
    ) -> None:
        """Stop the climb (by raising) when ``snapshot`` answers the lead."""
        if snapshot is None:
            return
        match = satisfies(snapshot, self.lead, variant=variant, identity=identity)
        if match is None:
            return
        raise _Found(
            Acquisition(
                rung=self.rung,
                url=url,
                snapshot_id=snapshot.snapshot_id,
                match=match,
                on_publisher_host=self.on_publisher_host(snapshot.final_url),
                archived=archived,
                edition_period=variant.period if variant is not None else None,
            ),
            (snapshot, self._published.get(snapshot.snapshot_id)),
        )

    def open_hits(self, hits: Sequence[SearchHit], *, within: Sequence[str] = ()) -> None:
        """Open the best hits of a search: on ``within`` hosts only, if given; the
        publisher's hosts and hits naming the lead first; at most ``opens_per_search``."""

        def allowed(hit: SearchHit) -> bool:
            host = _host(hit.url)
            return not within or any(host == w or host.endswith("." + w) for w in within)

        ranked = sorted(
            (h for h in hits if allowed(h)),
            key=lambda h: (
                not self.on_publisher_host(h.url),
                not link_matches(self.lead, h.url, f"{h.title} {h.snippet}"),
                h.rank,
            ),
        )
        for hit in ranked[: self.config.opens_per_search]:
            self.answer(self.fetch(hit.url), url=hit.url)

    def needles(self) -> tuple[str, ...]:
        """The texts a search for the lead quotes: its phrases, then its title."""
        return (*self.lead.phrases, *((self.lead.title,) if self.lead.title else ()))


# --------------------------------------------------------------------------- #
# The rungs
# --------------------------------------------------------------------------- #


def rung_direct_link(climb: Climb) -> None:
    """Rung 1: the lead's known URLs, then the links of the citing page that name it."""
    candidates = list(climb.lead.urls)
    if climb.citing is not None:
        candidates += matching_links(climb.lead, climb.citing)
    seen: set[str] = set()
    for url in candidates:
        if _key(url) in seen:
            continue
        seen.add(_key(url))
        climb.answer(climb.fetch(url), url=url)


def rung_other_formats(climb: Climb) -> None:
    """Rung 2: from an HTML release (the citing page, or a page captured so far), its
    PDF, XLSX or CSV twin on the same host."""
    releases = [*([climb.citing] if climb.citing is not None else []), *climb.pages]
    seen: set[str] = set()
    for release in releases:
        for url in document_twins(climb.lead, release):
            if _key(url) in seen:
                continue
            seen.add(_key(url))
            climb.answer(climb.fetch(url, same_host=True), url=url)


def rung_publisher_index(climb: Climb) -> None:
    """Rung 3: the registered publisher's own site -- a ``site:`` search for the
    phrase or title on each of its hosts, then its sitemap's entries naming the lead."""
    publisher = climb.publisher
    needle = next(iter(climb.needles()), None)
    if publisher is None or needle is None:
        return
    for host in publisher.hosts:
        try:
            query = render_query(words=None, phrase=needle, site=host)
        except ValueError:
            continue
        climb.open_hits(climb.search(query, lang=climb.lead.lang), within=publisher.hosts)
    for host in publisher.hosts[:1]:
        sitemaps = climb.gate.known_sitemaps(host) or (f"https://{host}/sitemap.xml",)
        for sitemap in sitemaps[:1]:
            listed = [
                url
                for url in climb.sitemap(sitemap)
                if _host(url) == host and link_matches(climb.lead, url, "")
            ]
            for url in listed[: climb.config.opens_per_search]:
                climb.answer(climb.fetch(url, same_host=True), url=url)


def _dataset_query(ref: DatasetRef, period: str | None) -> DatasetQuery | None:
    try:
        return DatasetQuery(connector_id=ref.connector_id, dataset_id=ref.dataset_id, period=period)
    except ValidationError:
        if period is None:
            return None
        return _dataset_query(ref, None)


def _publisher_connectors(climb: Climb) -> frozenset[str]:
    publisher = climb.publisher
    if publisher is None:
        return frozenset()
    return frozenset(
        climb.config.interfaces[i]
        for i in publisher.data_interfaces
        if i in climb.config.interfaces
    )


def rung_data_interface(climb: Climb) -> None:
    """Rung 4: each dataset the lead names on the publisher's own connector (or, when
    the publisher is not registered, on any connector that is not an aggregator's)."""
    own = _publisher_connectors(climb)
    for ref in climb.lead.datasets:
        mine = ref.connector_id in own or (
            climb.publisher is None and ref.connector_id not in climb.config.aggregator_connectors
        )
        if not mine:
            continue
        query = _dataset_query(ref, climb.lead.period)
        if query is not None:
            climb.answer(climb.dataset(query), url=f"{ref.connector_id}:{ref.dataset_id}")


def rung_exact_phrase(climb: Climb) -> None:
    """Rung 5: each phrase, then the title, in quotes, anywhere on the public web."""
    for needle in climb.needles():
        try:
            query = render_query(words=None, phrase=needle, site=None)
        except ValueError:
            continue
        climb.open_hits(climb.search(query, lang=climb.lead.lang))


def rung_language_edition(climb: Climb) -> None:
    """Rung 6: each title variant -- the other language, a previous edition -- in quotes."""
    for variant in climb.lead.variants:
        query = render_query(words=None, phrase=variant.title, site=None)
        hits = climb.search(query, lang=variant.lang)
        ranked = sorted(hits, key=lambda h: (not climb.on_publisher_host(h.url), h.rank))
        for hit in ranked[: climb.config.opens_per_search]:
            climb.answer(climb.fetch(hit.url), url=hit.url, variant=variant)


def _doi_of(value: str | None) -> str | None:
    if not value:
        return None
    for prefix in ("https://doi.org/", "http://doi.org/", "doi:"):
        if value.casefold().startswith(prefix):
            return value[len(prefix) :]
    return value if value.startswith("10.") else None


def _title_words(title: str) -> tuple[str, ...]:
    """Up to ten distinct words of a title, as an OpenAlex search takes them: ASCII,
    lower case, three letters or more (diacritics folded, so no word is split)."""
    folded = unicodedata.normalize("NFKD", title)
    plain = "".join(c for c in folded if not unicodedata.combining(c)).lower()
    words = [w for w in re.findall(r"[a-z0-9-]+", plain) if len(w.strip("-")) >= 3]
    return tuple(dict.fromkeys(w.strip("-") for w in words))[:10]


def rung_scholarly_identity(climb: Climb) -> None:
    """Rung 7: the DOI -- or the title's, by an OpenAlex search -- to a lawful open copy.

    Only a location OpenAlex marks open access is opened (``open_access_copies``):
    a publisher's free copy, a repository, a preprint. Never an archive or a mirror.
    """
    connector = OPENALEX_CONNECTOR_ID
    doi = climb.lead.doi
    if doi is None and climb.lead.title is not None:
        words = _title_words(climb.lead.title)
        if not words:
            return
        found = climb.dataset(
            DatasetQuery(
                connector_id=connector,
                dataset_id="works",
                filters=(DimensionFilter(dimension="search", values=words),),
            )
        )
        if found is None or found.dataset is None:
            return
        at = {c.key: i for i, c in enumerate(found.dataset.columns)}
        if "doi" not in at or "title" not in at:
            return
        want = " ".join(climb.lead.title.casefold().split())
        for row in found.dataset.rows:
            title = row.values[at["title"]] or ""
            if " ".join(title.casefold().split()) == want:
                doi = _doi_of(row.values[at["doi"]])
                break
    if doi is None:
        return
    lookup = climb.dataset(DatasetQuery(connector_id=connector, dataset_id=f"doi:{doi}"))
    if lookup is None or lookup.dataset is None:
        return
    for copy in open_access_copies(lookup.dataset):
        climb.answer(climb.fetch(copy.url), url=copy.url, identity=True)


def rung_aggregator(climb: Climb) -> None:
    """Rung 8: an official aggregator republishing the figure -- a dataset the lead
    names on an aggregator's connector, then a ``site:`` search on each aggregator."""
    own = _publisher_connectors(climb)
    for ref in climb.lead.datasets:
        if ref.connector_id in climb.config.aggregator_connectors and ref.connector_id not in own:
            query = _dataset_query(ref, climb.lead.period)
            if query is not None:
                climb.answer(climb.dataset(query), url=f"{ref.connector_id}:{ref.dataset_id}")
    needle = next(iter(climb.needles()), None)
    if needle is None:
        return
    for host in climb.config.aggregator_hosts:
        if climb.on_publisher_host(f"https://{host}/"):
            continue  # the publisher's own site was rung 3's
        text = render_query(words=None, phrase=needle, site=host)
        climb.open_hits(climb.search(text, lang=climb.lead.lang), within=(host,))


def _archive_candidates(climb: Climb) -> list[str]:
    """The URLs an archived copy may stand in for: the lead's, and the links rung 1 tried."""
    urls = list(climb.lead.urls)
    if climb.citing is not None:
        urls += matching_links(climb.lead, climb.citing)
    seen: set[str] = set()
    out: list[str] = []
    for url in urls:
        if _key(url) not in seen and not is_archive_url(url):
            seen.add(_key(url))
            out.append(url)
    return out


def _permit(climb: Climb, url: str, needle: str) -> ArchivePermit | None:
    """The live attempt first (made now if this climb has none), then the policy's word."""
    if url not in climb.live:
        climb.fetch(url)
    attempt = climb.live.get(url)
    if attempt is None:
        return None
    decision = decide_archive_use(attempt, needed_quote=needle)
    climb.attempts.append(
        LadderAttempt(
            rung=climb.rung,
            tool="archive_permit",
            target=url,
            decision=AttemptDecision.SENT if decision.permit else AttemptDecision.REFUSED,
            reason=decision.permit.basis.value if decision.permit else decision.refusal,
        )
    )
    return decision.permit


def rung_archived_copy(climb: Climb) -> None:
    """Rung 9: for a dead, moved or changed page only, its archived capture nearest the
    cited date -- Wayback first, then Common Crawl -- each only with the URL's permit.

    A page live behind a paywall, a login or a challenge, a page whose barrier nobody
    can tell, a refusal by AIA's own rules and a transient failure all get no permit:
    the archive is never asked for them.
    """
    needle = climb.lead.needle
    if needle is None:
        return
    for url in _archive_candidates(climb):
        permit = _permit(climb, url, needle)
        if permit is None:
            continue
        lookup = climb.dataset(
            DatasetQuery(
                connector_id=WAYBACK_CONNECTOR_ID, dataset_id=url, period=climb.lead.cited_date
            ),
            permit=permit,
        )
        if lookup is not None and lookup.dataset is not None:
            cited = climb.lead.cited_date or lookup.dataset.retrieved_at.strftime("%Y%m%d%H%M%S")
            key = nearest_capture(lookup.dataset, cited)
            at = {c.key: i for i, c in enumerate(lookup.dataset.columns)}
            row = next((r for r in lookup.dataset.rows if r.key == key), None)
            replay = row.values[at["archived_url"]] if row is not None else None
            if row is not None and replay and _host(replay) == _REPLAY_HOST:
                climb.answer(
                    climb.fetch(replay, archive_permit=permit),
                    url=url,
                    archived=ArchivedFrom(
                        archive="wayback",
                        basis=permit.basis,
                        captured=row.values[at["timestamp"]] or "",
                    ),
                )
        if climb.config.crawls and climb.gate.has_common_crawl:
            try:
                index_query = UrlIndexQuery(
                    target=IndexTarget.URL, value=url, crawls=climb.config.crawls[:6], limit=20
                )
            except IndexQueryInvalid:
                continue
            rows = [r for r in climb.url_index(index_query, permit) if 200 <= r.status < 300]
            for capture in _nearest_rows(rows, climb.lead.cited_date)[:1]:
                climb.answer(
                    climb.archived(capture, permit),
                    url=url,
                    archived=ArchivedFrom(
                        archive="common_crawl",
                        basis=permit.basis,
                        captured=capture.captured_at.isoformat(),
                    ),
                )


def _nearest_rows(rows: Sequence[IndexRow], cited: str | None) -> list[IndexRow]:
    """Rows nearest the cited date (earlier first on a tie); newest first when undated."""
    if cited is None:
        return sorted(rows, key=lambda r: r.captured_at, reverse=True)
    padded = cited + "0101000000"[len(cited) - 4 :]
    target = datetime.strptime(padded, "%Y%m%d%H%M%S").replace(tzinfo=UTC)
    return sorted(
        rows, key=lambda r: (abs((r.captured_at - target).total_seconds()), r.captured_at)
    )


_DEAD: Final = frozenset({"http_404", "http_410"})


def rung_path_discovery(climb: Climb) -> None:
    """Rung 10: a document gone from its URL may have moved on its own host -- its parent
    paths, then their links naming the lead, at most ``limits.path_discovery`` requests.

    Confined to the URL's host; robots.txt is the gate's transport's to keep, and a
    refusal is recorded like any other.
    """
    start = climb.requests
    budget = climb.limits.path_discovery

    def room() -> bool:
        return climb.requests - start < budget

    for url, attempt in list(climb.live.items()):
        if attempt.failure not in _DEAD:
            continue
        host = _host(url)
        for parent in parent_paths(url, limit=budget):
            if not room():
                return
            listing = climb.fetch(parent, same_host=True)
            climb.answer(listing, url=parent)
            if listing is None:
                continue
            for link in matching_links(climb.lead, listing, host=host):
                if not room():
                    return
                climb.answer(climb.fetch(link, same_host=True), url=link)


#: The rungs in plan § 7's order; rung 11 is the gap :func:`ladder` writes.
RUNGS: Final[tuple[tuple[Rung, Callable[[Climb], None]], ...]] = (
    (Rung.DIRECT_LINK, rung_direct_link),
    (Rung.OTHER_FORMATS, rung_other_formats),
    (Rung.PUBLISHER_INDEX, rung_publisher_index),
    (Rung.DATA_INTERFACE, rung_data_interface),
    (Rung.EXACT_PHRASE, rung_exact_phrase),
    (Rung.LANGUAGE_EDITION, rung_language_edition),
    (Rung.SCHOLARLY_IDENTITY, rung_scholarly_identity),
    (Rung.AGGREGATOR, rung_aggregator),
    (Rung.ARCHIVED_COPY, rung_archived_copy),
    (Rung.PATH_DISCOVERY, rung_path_discovery),
)


def _tried(attempts: Sequence[LadderAttempt]) -> Iterator[Rung]:
    seen: set[Rung] = set()
    for attempt in attempts:
        if attempt.rung not in seen:
            seen.add(attempt.rung)
            yield attempt.rung


def ladder(
    lead: AcquisitionLead,
    *,
    gate: RetrievalGate,
    track_id: str,
    context_class: DataClass,
    config: LadderConfig | None = None,
    limits: LadderLimits | None = None,
    citing: SourceSnapshot | None = None,
    may_send: Callable[[str], bool] | None = None,
) -> LadderResult:
    """Climb the rungs in order for ``lead``; the first capture that answers it, or the gap.

    ``citing`` is the captured page that cites the source (its links feed rungs 1-2).
    ``context_class`` is the class of what the lead was written from: its searches and
    dataset queries are classified in it. See the module's description for the cap,
    the boundaries and ``may_send``.
    """
    climb = Climb(
        lead,
        gate=gate,
        track_id=track_id,
        context_class=context_class,
        config=config or LadderConfig(),
        limits=limits or LadderLimits(),
        citing=citing,
        may_send=may_send,
    )
    stop, reason = LadderStop.GAP, None
    acquisition: Acquisition | None = None
    capture: tuple[SourceSnapshot, date | None] | None = None
    try:
        for rung, climb_rung in RUNGS:
            climb.rung = rung
            climb_rung(climb)
    except _Found as found:
        stop, acquisition, capture = LadderStop.ACQUIRED, found.acquisition, found.capture
    except _Stop as stopped:
        stop, reason = stopped.stop, stopped.reason
        if reason is not None:
            climb.met.append(reason)
    rungs = tuple(_tried(climb.attempts))
    gap = None
    if stop in (LadderStop.GAP, LadderStop.UNCERTAIN):
        gap = AcquisitionGap.of(
            lead,
            reason=gap_reason(climb.met),
            rungs_tried=rungs,
            detail=f"{climb.requests} requests; stopped at rung {climb.rung.value}",
        )
    return LadderResult(
        record=LadderRecord(
            lead=lead,
            stop=stop,
            acquisition=acquisition,
            gap=gap,
            rungs_tried=rungs,
            attempts=tuple(climb.attempts),
            requests=climb.requests,
            searches=climb.searches,
            fetches=climb.fetches,
        ),
        capture=capture,
    )
