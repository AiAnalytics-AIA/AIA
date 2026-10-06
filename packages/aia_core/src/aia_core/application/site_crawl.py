"""A focused crawl of one authoritative host: sitemap first, then breadth-first.

Plan chunk 17 (``deep-research-web-search.md`` § 5.1, Discover). The caller picks
the host -- one the source tiers and the reputation register rate authoritative --
and the budget; :class:`SiteCrawl` finds pages **inside that host** and captures
them as snapshots. It is not wired into any composition and nothing calls it yet.

Every request goes through the :class:`~aia_core.application.web_retrieval.RetrievalGate`
the crawl is given -- classified, egress-checked, reserved and journaled like any
fetch -- and through whatever transport that gate's route holds, which for the
public web is ``PublicHttpsTransport``: robots.txt read once and obeyed, its crawl
delay and a per-host interval kept, one request at a time per host. The crawler
never holds a transport and has no way round either. A page this run already
captured is answered by the gate's run cache and costs nothing.

In order:

1. **Sitemaps** -- ``/sitemap.xml``, then every same-host ``Sitemap:`` line of the
   host's robots.txt (which the first request made the transport read; first, when
   this run already holds it), then the sitemaps an index names (one level: an
   index inside an index is not read), at most ``max_sitemaps`` requests. Each is a
   bounded resource fetch (``fetch_resource``), parsed by
   ``domain.deep_research.sitemaps`` (no DTD, no entity, bounded inflation). The
   pages they list (at most ``max_sitemap_entries``) are ranked -- the caller's
   relevance first, then the most recent ``lastmod``, an unknown date last -- and
   captured up to the sitemap share of the budget. Their links are not followed.
2. **Breadth-first** from the seeds (the host's root when none is given), level by
   level; a captured page's ``anchor`` links that stay in scope are the next level,
   up to ``max_depth``, each level ranked by relevance (seeds are the caller's
   choice and are not scored). A seed the sitemap phase already captured is
   expanded from its snapshot, not fetched again.

Every URL is put in the crawl's form (``crawl_url``), deduplicated by
``crawl_key``, kept in scope (``CrawlScope``: the host, its subdomains only when
asked, https only), and admitted by the trap rules (``TrapGuard``) before it can
cost a request. A redirect off the scope is refused by the gate before the hop is
requested. The crawl stops at the page cap, the time cap (checked before every
request; pacing counts) or the tool budget (``ToolBudgetExhausted`` ends the
crawl with what it has); the worker's ``StopExecution`` propagates untouched.

The result is the captured snapshots, in capture order, and a
:class:`CrawlReport` -- what was fetched, cached, refused by robots.txt, skipped
by which cap or trap rule, and failed -- for the transcript.
"""

from __future__ import annotations

import time
from collections import Counter, deque
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field
from datetime import date
from enum import StrEnum
from typing import Any, Final

from ..domain.deep_research.contracts import SourceSnapshot
from ..domain.deep_research.crawl import (
    CrawlLimits,
    CrawlScope,
    TrapGuard,
    crawl_key,
    crawl_url,
)
from ..domain.deep_research.robots import ROBOTS_DISALLOWED, ROBOTS_UNAVAILABLE
from ..domain.deep_research.sitemaps import (
    MAX_SITEMAP_BYTES,
    SITEMAP_MEDIA_TYPES,
    SitemapKind,
    SitemapRefused,
    read_sitemap,
)
from ..domain.deep_research.tooling import ToolBudgetExhausted
from ..domain.deep_research.web import FetchRefused
from .web_retrieval import RetrievalGate

__all__ = [
    "CrawlCandidate",
    "CrawlOrigin",
    "CrawlReport",
    "CrawlResult",
    "CrawledPage",
    "Relevance",
    "SiteCrawl",
    "StopReason",
]

#: Refusals that come from the host's robots.txt (counted apart from other failures).
_ROBOTS_REASONS: Final = frozenset({ROBOTS_DISALLOWED, ROBOTS_UNAVAILABLE, "robots_crawl_delay"})


class CrawlOrigin(StrEnum):
    SEED = "seed"
    SITEMAP = "sitemap"
    LINK = "link"


@dataclass(frozen=True, slots=True)
class CrawlCandidate:
    """A URL the crawl could request, with what is known about it before it is."""

    url: str
    origin: CrawlOrigin
    depth: int
    #: The anchor text of the link that named it ("" for a seed or a sitemap entry).
    anchor_text: str = ""
    #: The sitemap's ``lastmod`` for it, or None.
    lastmod: date | None = None
    #: The page that linked to it, or None.
    referrer: str | None = None


#: The caller's relevance hook: a score (higher is fetched first) or None to skip
#: the candidate. It sees only the candidate; it sends nothing.
Relevance = Callable[[CrawlCandidate], float | None]


class StopReason(StrEnum):
    COMPLETE = "complete"
    PAGE_CAP = "page_cap"
    TIME_CAP = "time_cap"
    TOOL_BUDGET = "tool_budget"


@dataclass(frozen=True, slots=True)
class CrawledPage:
    url: str
    snapshot_id: str
    origin: CrawlOrigin
    depth: int
    #: Answered from the run cache: nothing was sent for it.
    cached: bool


@dataclass(slots=True)
class CrawlReport:
    """What one crawl did, in counts; JSON-ready through :meth:`as_dict`."""

    host: str
    stopped: StopReason = StopReason.COMPLETE
    #: Page requests the gate sent (each dispatched and journaled).
    pages_fetched: int = 0
    #: Pages answered from the run cache.
    pages_cached: int = 0
    sitemaps_fetched: int = 0
    sitemap_entries: int = 0
    #: Requests (pages or sitemaps) robots.txt refused.
    refused_by_robots: int = 0
    #: Requests whose outcome is unknown (charged at the ceiling, never resent).
    uncertain: int = 0
    #: Candidates never requested, by rule ("duplicate", "off_host", "shape_cap", ...).
    skipped: Counter[str] = field(default_factory=Counter)
    #: Requests that failed or were refused for another reason, by reason.
    errors: Counter[str] = field(default_factory=Counter)
    elapsed_s: float = 0.0

    def as_dict(self) -> dict[str, Any]:
        return {
            "host": self.host,
            "stopped": self.stopped.value,
            "pages_fetched": self.pages_fetched,
            "pages_cached": self.pages_cached,
            "sitemaps_fetched": self.sitemaps_fetched,
            "sitemap_entries": self.sitemap_entries,
            "refused_by_robots": self.refused_by_robots,
            "uncertain": self.uncertain,
            "skipped": dict(sorted(self.skipped.items())),
            "errors": dict(sorted(self.errors.items())),
            "elapsed_s": round(self.elapsed_s, 3),
        }


@dataclass(frozen=True, slots=True)
class CrawlResult:
    pages: tuple[CrawledPage, ...]
    snapshots: tuple[SourceSnapshot, ...]
    report: CrawlReport

    @property
    def snapshot_ids(self) -> tuple[str, ...]:
        return tuple(page.snapshot_id for page in self.pages)


class _Stop(Exception):
    def __init__(self, reason: StopReason) -> None:
        super().__init__(reason.value)
        self.reason = reason


class SiteCrawl:
    """One crawl of one host through one gate. Build one per crawl; not thread-safe."""

    def __init__(
        self,
        *,
        gate: RetrievalGate,
        host: str,
        limits: CrawlLimits | None = None,
        relevance: Relevance | None = None,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        self._limits = limits or CrawlLimits()
        self._scope = CrawlScope.of(host, include_subdomains=self._limits.include_subdomains)
        self._gate = gate
        self._relevance = relevance
        self._monotonic = monotonic
        self._guard = TrapGuard(self._limits)
        self._report = CrawlReport(host=self._scope.host)
        #: Keys a request was made (or refused) for: never asked twice.
        self._attempted: set[str] = set()
        #: Keys admitted to a phase's queue: never queued twice.
        self._queued: set[str] = set()
        #: Captured snapshots by key (requested and final URL).
        self._captured: dict[str, SourceSnapshot] = {}
        self._pages: list[CrawledPage] = []
        self._snapshots: dict[str, SourceSnapshot] = {}
        self._deadline = 0.0
        self._started = 0.0
        self._ran = False

    @property
    def host(self) -> str:
        return self._scope.host

    # ------------------------------------------------------------------ public --

    def run(
        self, *, track_id: str, seeds: Sequence[str] = (), use_sitemaps: bool = True
    ) -> CrawlResult:
        """Crawl the host once; returns what was captured and the report."""
        if self._ran:
            raise RuntimeError("a SiteCrawl runs once")
        self._ran = True
        self._started = self._monotonic()
        self._deadline = self._started + self._limits.max_seconds
        try:
            if use_sitemaps:
                self._sitemap_phase(track_id)
            self._breadth_first(track_id, seeds or (f"https://{self.host}/",))
        except _Stop as stop:
            self._report.stopped = stop.reason
        except ToolBudgetExhausted:
            self._report.stopped = StopReason.TOOL_BUDGET
        self._report.elapsed_s = max(0.0, self._monotonic() - self._started)
        return CrawlResult(
            pages=tuple(self._pages),
            snapshots=tuple(self._snapshots[p.snapshot_id] for p in self._pages),
            report=self._report,
        )

    # ------------------------------------------------------------------ shared --

    def _skip(self, reason: str) -> None:
        self._report.skipped[reason] += 1

    def _before_request(self) -> None:
        if self._monotonic() >= self._deadline:
            raise _Stop(StopReason.TIME_CAP)

    def _page_room(self) -> bool:
        return len(self._pages) < self._limits.max_pages

    def _normalise(self, url: str) -> str | None:
        """The crawl form of an in-scope URL, or None (counted as skipped)."""
        try:
            form = crawl_url(url)
        except FetchRefused as exc:
            self._skip(exc.reason)
            return None
        reason = self._scope.refusal(form)
        if reason is not None:
            self._skip(reason)
            return None
        return form

    def _score(self, candidate: CrawlCandidate) -> float | None:
        if self._relevance is None:
            return 0.0
        score = self._relevance(candidate)
        if score is None:
            self._skip("irrelevant")
        return score

    def _failed(self, reason: str | None, uncertain: bool) -> None:
        if uncertain:
            self._report.uncertain += 1
        if reason in _ROBOTS_REASONS:
            self._report.refused_by_robots += 1
        else:
            self._report.errors[reason or "unknown"] += 1

    def _capture(self, candidate: CrawlCandidate, track_id: str) -> SourceSnapshot | None:
        """Request one admitted page through the gate; None when nothing was kept."""
        if not self._page_room():
            raise _Stop(StopReason.PAGE_CAP)
        self._before_request()
        key = crawl_key(candidate.url)
        self._attempted.add(key)
        outcome = self._gate.fetch(
            candidate.url, track_id=track_id, host_allowed=self._scope.allows_host
        )
        if outcome.page is None:
            self._failed(outcome.reason, outcome.uncertain)
            return None
        snapshot = outcome.page.snapshot
        if outcome.cached:
            self._report.pages_cached += 1
        else:
            self._report.pages_fetched += 1
        final_key = crawl_key(snapshot.final_url)
        self._attempted.add(final_key)
        if final_key in self._captured and final_key != key:
            # Two URLs, one page (a redirect to a page already captured): kept once.
            self._captured[key] = self._captured[final_key]
            self._skip("duplicate")
            return self._captured[final_key]
        self._captured[key] = self._captured[final_key] = snapshot
        self._snapshots.setdefault(snapshot.snapshot_id, snapshot)
        self._pages.append(
            CrawledPage(
                url=candidate.url,
                snapshot_id=snapshot.snapshot_id,
                origin=candidate.origin,
                depth=candidate.depth,
                cached=outcome.cached,
            )
        )
        return snapshot

    # ---------------------------------------------------------------- sitemaps --

    def _sitemap_phase(self, track_id: str) -> None:
        limits = self._limits
        queue: deque[tuple[str, int]] = deque()
        listed: set[str] = set()
        entries: list[CrawlCandidate] = []

        def offer(url: str, level: int) -> None:
            form = self._normalise(url)
            if form is None:
                return
            key = crawl_key(form)
            if key not in listed:
                listed.add(key)
                queue.append((form, level))

        held = self._gate.known_sitemaps(self.host)
        for url in held or ():
            offer(url, 0)
        offer(f"https://{self.host}/sitemap.xml", 0)
        robots_read = held is not None
        fetched = 0
        while queue:
            url, level = queue.popleft()
            if fetched >= limits.max_sitemaps:
                self._skip("sitemap_cap")
                continue
            self._before_request()
            fetched += 1
            outcome = self._gate.fetch_resource(
                url,
                track_id=track_id,
                media_types=SITEMAP_MEDIA_TYPES,
                max_bytes=MAX_SITEMAP_BYTES,
                host_allowed=self._scope.allows_host,
            )
            if not robots_read:
                # The first request made the transport read robots.txt: its lines now.
                robots_read = True
                for declared in self._gate.known_sitemaps(self.host) or ():
                    offer(declared, 0)
            if outcome.resource is None:
                self._failed(outcome.reason, outcome.uncertain)
                continue
            self._report.sitemaps_fetched += 1
            try:
                sitemap = read_sitemap(
                    outcome.resource.body, media_type=outcome.resource.media_type
                )
            except SitemapRefused as exc:
                self._report.errors[exc.reason] += 1
                continue
            self._report.sitemap_entries += len(sitemap.entries)
            if sitemap.dropped:
                self._report.skipped["sitemap_entry_invalid"] += sitemap.dropped
            if sitemap.overflow:
                self._report.skipped["sitemap_overflow"] += sitemap.overflow
            if sitemap.kind is SitemapKind.INDEX:
                if level >= 1:
                    self._report.skipped["sitemap_nesting"] += len(sitemap.entries)
                    continue
                for entry in sitemap.entries:
                    offer(entry.url, level + 1)
                continue
            for entry in sitemap.entries:
                form = self._normalise(entry.url)
                if form is None:
                    continue
                if len(entries) >= limits.max_sitemap_entries:
                    self._skip("sitemap_entry_cap")
                    continue
                entries.append(
                    CrawlCandidate(
                        url=form, origin=CrawlOrigin.SITEMAP, depth=0, lastmod=entry.lastmod
                    )
                )
        share = limits.max_pages if limits.max_sitemap_pages is None else limits.max_sitemap_pages
        taken = 0
        for candidate in self._ranked(entries, by_date=True):
            if taken >= share:
                self._skip("sitemap_page_share")
                continue
            if not self._admit(candidate):
                continue
            if self._capture(candidate, track_id) is not None:
                taken += 1

    # ------------------------------------------------------------ breadth-first --

    def _admit(self, candidate: CrawlCandidate) -> bool:
        """Dedup and the trap rules; True when the candidate may cost a request."""
        key = crawl_key(candidate.url)
        if key in self._queued or key in self._attempted:
            self._skip("duplicate")
            return False
        reason = self._guard.admit(candidate.url)
        if reason is not None:
            self._skip(reason)
            return False
        self._queued.add(key)
        return True

    def _ranked(
        self, candidates: Iterable[CrawlCandidate], *, by_date: bool = False
    ) -> list[CrawlCandidate]:
        scored: list[tuple[float, int, int, CrawlCandidate]] = []
        for index, candidate in enumerate(candidates):
            score = self._score(candidate)
            if score is None:
                continue
            recency = candidate.lastmod.toordinal() if by_date and candidate.lastmod else 0
            scored.append((score, recency, -index, candidate))
        scored.sort(key=lambda item: item[:3], reverse=True)
        return [item[3] for item in scored]

    def _breadth_first(self, track_id: str, seeds: Sequence[str]) -> None:
        # Seeds are the caller's choice: no relevance asked, the trap rules kept. A
        # seed the sitemap phase captured is expanded from its snapshot.
        level: list[tuple[float, CrawlCandidate]] = []
        for seed in seeds:
            form = self._normalise(seed)
            if form is None:
                continue
            candidate = CrawlCandidate(url=form, origin=CrawlOrigin.SEED, depth=0)
            if crawl_key(form) in self._captured or self._admit(candidate):
                level.append((0.0, candidate))
        depth = 0
        while level:
            following: list[tuple[float, CrawlCandidate]] = []
            # Highest score first; equal scores keep the order the links were found in.
            for _score, candidate in sorted(level, key=lambda item: -item[0]):
                key = crawl_key(candidate.url)
                snapshot = self._captured.get(key)
                if snapshot is None:
                    if candidate.origin is CrawlOrigin.LINK and key in self._attempted:
                        self._skip("duplicate")  # reached by another path meanwhile
                        continue
                    snapshot = self._capture(candidate, track_id)
                    if snapshot is None:
                        continue
                if depth >= self._limits.max_depth:
                    continue
                following.extend(self._children(snapshot, candidate, depth + 1, len(following)))
            level = following
            depth += 1

    def _children(
        self, snapshot: SourceSnapshot, parent: CrawlCandidate, depth: int, queued: int
    ) -> list[tuple[float, CrawlCandidate]]:
        """The in-scope, admitted anchor links of one captured page, scored."""
        children: list[tuple[float, CrawlCandidate]] = []
        for link in snapshot.links:
            if link.kind != "anchor":
                continue
            form = self._normalise(link.url)
            if form is None:
                continue
            child = CrawlCandidate(
                url=form,
                origin=CrawlOrigin.LINK,
                depth=depth,
                anchor_text=link.text,
                referrer=parent.url,
            )
            key = crawl_key(form)
            if key in self._queued or key in self._attempted:
                self._skip("duplicate")
                continue
            score = self._score(child)
            if score is None:
                continue
            if queued + len(children) >= self._limits.max_frontier:
                self._skip("frontier_full")
                continue
            if self._admit(child):
                children.append((score, child))
        return children
