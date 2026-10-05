"""The focused crawler's rules: which URLs inside one host it may take, and how many.

A crawl of an authoritative host (plan chunk 17) is bounded by data, decided by
code, and never leaves the host. This module is the part with no I/O: the limits,
the URL form a crawl requests, the host scope, and the trap rules. The crawl
itself, every request through the retrieval gate, is
``aia_core.application.site_crawl``.

**The URL a crawl requests** (:func:`crawl_url`) -- scheme and host lower-cased,
no fragment, an empty path made ``/``, known tracking parameters (``utm_*``,
``fbclid``, ``gclid``, ...) removed and the rest sorted, so that two links to the
same page are one request; its dedup key is that URL's ``canonical_url``.

**The scope** (:class:`CrawlScope`) -- ``https`` only, a URL ``check_url``
allows, and the crawl's own host exactly; its subdomains only when the caller
says so (``include_subdomains``), never a parent or a sibling.

**The trap rules** (:class:`TrapGuard`), each counted under its own reason:

* ``url_too_long`` -- longer than ``max_url_chars``;
* ``path_too_deep`` -- more than ``max_path_segments`` path segments;
* ``repeated_segment`` -- one path segment (case-insensitive) more than
  ``max_segment_repeats`` times: ``/a/b/a/b/a``, ``/kalendar/next/next/next``,
  ``/2026/10/2026/10/2026``;
* ``query_variant_cap`` -- more than ``max_query_variants`` query strings for one
  path (``?page=``, ``?sort=``, session ids);
* ``shape_cap`` -- more than ``max_per_shape`` URLs of one *shape* (every run of
  digits read as one digit, query values ignored): ``/kalendar/2026/11``,
  ``/kalendar/2026/12``, ``/kalendar/2027/1`` … are one shape, so an infinite
  calendar ends after ``max_per_shape`` pages however it is paged;
* ``prefix_cap`` -- more than ``max_per_prefix`` URLs in one directory, read to at
  most ``prefix_segments`` segments (``/publikace/2025/a`` is in
  ``/publikace/2025``), so no one section eats the budget.

Pure: stdlib only.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from typing import Final
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from .legacy import canonical_url
from .web import FetchRefused, check_url

__all__ = [
    "CrawlLimits",
    "CrawlScope",
    "TrapGuard",
    "crawl_key",
    "crawl_url",
]

#: Query parameters that track a visit and never change a page.
_TRACKING: Final = frozenset(
    {"fbclid", "gclid", "dclid", "msclkid", "mc_cid", "mc_eid", "yclid", "_ga", "_gl"}
)
_DIGITS: Final = re.compile(r"\d+")


@dataclass(frozen=True, slots=True)
class CrawlLimits:
    """Every bound a crawl keeps. Each is a cap, never a target."""

    #: Pages captured (sent or answered from the run cache), sitemap and links together.
    max_pages: int = 200
    #: Of those, at most this many from sitemaps; None: up to ``max_pages``.
    max_sitemap_pages: int | None = None
    #: Link hops from a seed; a seed is depth 0. Sitemap pages are not expanded.
    max_depth: int = 3
    #: Wall-clock seconds; no request starts after them (pacing included).
    max_seconds: float = 1800.0
    #: Sitemap documents requested (``/sitemap.xml``, robots.txt's, an index's).
    max_sitemaps: int = 20
    #: URLs waiting in the breadth-first frontier; more are skipped.
    max_frontier: int = 10_000
    #: Trap rules (module docstring).
    max_url_chars: int = 1024
    max_path_segments: int = 12
    max_segment_repeats: int = 2
    max_query_variants: int = 3
    max_per_shape: int = 100
    prefix_segments: int = 2
    max_per_prefix: int = 100
    #: Subdomains of the crawl's host are in scope (``www`` included); off by default.
    include_subdomains: bool = False

    def __post_init__(self) -> None:
        positive = {
            "max_pages": self.max_pages,
            "max_sitemaps": self.max_sitemaps,
            "max_frontier": self.max_frontier,
            "max_url_chars": self.max_url_chars,
            "max_path_segments": self.max_path_segments,
            "max_segment_repeats": self.max_segment_repeats,
            "max_per_shape": self.max_per_shape,
            "prefix_segments": self.prefix_segments,
            "max_per_prefix": self.max_per_prefix,
        }
        for name, value in positive.items():
            if value < 1:
                raise ValueError(f"{name} is at least 1")
        if self.max_depth < 0 or self.max_query_variants < 0:
            raise ValueError("max_depth and max_query_variants are not negative")
        if self.max_sitemap_pages is not None and self.max_sitemap_pages < 0:
            raise ValueError("max_sitemap_pages is not negative")
        if not 0 < self.max_seconds < float("inf"):
            raise ValueError("max_seconds is a positive, finite time")


def crawl_url(url: str) -> str:
    """The form of ``url`` a crawl requests (module docstring); raises FetchRefused."""
    check_url(url)
    parts = urlsplit(url.strip())
    query = sorted(
        (key, value)
        for key, value in parse_qsl(parts.query, keep_blank_values=True)
        if key.lower() not in _TRACKING and not key.lower().startswith("utm_")
    )
    return urlunsplit(
        (
            parts.scheme.lower(),
            parts.netloc.lower(),
            parts.path or "/",
            urlencode(query),
            "",
        )
    )


def crawl_key(url: str) -> str:
    """What two URLs share when a crawl treats them as one page."""
    return canonical_url(url) or url


@dataclass(frozen=True, slots=True)
class CrawlScope:
    """One host, and (only when asked) its subdomains."""

    host: str
    include_subdomains: bool = False

    @classmethod
    def of(cls, host: str, *, include_subdomains: bool = False) -> CrawlScope:
        """The scope of ``host`` (a bare host name), or ValueError if it is not one."""
        name = host.strip().lower().rstrip(".")
        try:
            checked = check_url(f"https://{name}/")
        except FetchRefused as exc:
            raise ValueError(f"{host!r} is not a host a crawl may visit") from exc
        if checked != name:
            raise ValueError(f"{host!r} is not a bare host name")
        return cls(host=name, include_subdomains=include_subdomains)

    def allows_host(self, host: str) -> bool:
        name = host.lower().rstrip(".")
        return name == self.host or (self.include_subdomains and name.endswith("." + self.host))

    def refusal(self, url: str) -> str | None:
        """None when ``url`` is inside this scope; otherwise why not."""
        try:
            host = check_url(url)
        except FetchRefused as exc:
            return exc.reason
        if urlsplit(url).scheme.lower() != "https":
            return "https_only"
        return None if self.allows_host(host) else "off_host"


def _segments(path: str) -> list[str]:
    return [segment for segment in path.split("/") if segment]


class TrapGuard:
    """Admits URLs into one crawl under the trap rules, counting what it admits.

    Not thread-safe: one crawl, one guard.
    """

    def __init__(self, limits: CrawlLimits) -> None:
        self._limits = limits
        self._variants: Counter[str] = Counter()
        self._shapes: Counter[str] = Counter()
        self._prefixes: Counter[str] = Counter()

    def refusal(self, url: str) -> str | None:
        """Why ``url`` would not be admitted now; counts nothing."""
        limits = self._limits
        if len(url) > limits.max_url_chars:
            return "url_too_long"
        parts = urlsplit(url)
        segments = _segments(parts.path)
        if len(segments) > limits.max_path_segments:
            return "path_too_deep"
        repeats = Counter(segment.lower() for segment in segments)
        if repeats and max(repeats.values()) > limits.max_segment_repeats:
            return "repeated_segment"
        path_key = f"{parts.netloc.lower()}{parts.path}"
        if parts.query and self._variants[path_key] >= limits.max_query_variants:
            return "query_variant_cap"
        if self._shapes[self._shape(parts.netloc, segments, parts.query)] >= limits.max_per_shape:
            return "shape_cap"
        if self._prefixes[self._prefix(parts.netloc, segments)] >= limits.max_per_prefix:
            return "prefix_cap"
        return None

    def admit(self, url: str) -> str | None:
        """Admit ``url`` and count it, or return why not (and count nothing)."""
        reason = self.refusal(url)
        if reason is not None:
            return reason
        parts = urlsplit(url)
        segments = _segments(parts.path)
        if parts.query:
            self._variants[f"{parts.netloc.lower()}{parts.path}"] += 1
        self._shapes[self._shape(parts.netloc, segments, parts.query)] += 1
        self._prefixes[self._prefix(parts.netloc, segments)] += 1
        return None

    def _shape(self, netloc: str, segments: list[str], query: str) -> str:
        path = "/".join(_DIGITS.sub("9", segment.lower()) for segment in segments)
        names = sorted({key for key, _ in parse_qsl(query, keep_blank_values=True)})
        return f"{netloc.lower()}/{path}?{'&'.join(names)}"

    def _prefix(self, netloc: str, segments: list[str]) -> str:
        # The page's directory, at most ``prefix_segments`` deep: /publikace/123 and
        # /publikace/456 share "publikace"; a page is never its own prefix.
        directory = segments[: min(self._limits.prefix_segments, max(len(segments) - 1, 0))]
        return f"{netloc.lower()}/" + "/".join(segment.lower() for segment in directory)
