"""robots.txt as AIA obeys it: RFC 9309, read conservatively.

A public-web fetch asks a host's ``robots.txt`` first (plan § 4: never ignore it).
This module turns what that request returned into a :class:`RobotsPolicy` and
answers, for one URL, whether AIA may request it and how long it must wait between
requests to the host. The fetching itself, once per host, is the transport's
(``aia_core.infrastructure.web_retrieval_live.PublicHttpsTransport``).

How an answer becomes a policy (the conservative reading, recorded in the plan's
chunk 5):

* **2xx** -- the file is parsed (at most :data:`MAX_ROBOTS_BYTES` of it);
* **401, 403** -- disallow everything (the long-standing convention; RFC 9309
  would allow, AIA does not read an access refusal as consent);
* **404, 410 and other 4xx** -- allow everything (no file, no rules);
* **429, 5xx, a timeout, a lost or refused answer, too many redirects** -- the
  file is *unreachable*, so everything is disallowed until it is asked again
  (RFC 9309 § 2.3.1.4).

Two readings of a parsed file must both allow a URL, and the longer crawl delay
of the two is kept:

1. RFC 9309 -- the group for AIA's product token (case-insensitive, exact), or
   the ``*`` group; groups for the same agent merged; the most specific matching
   rule wins, ``allow`` on a tie; ``*`` and ``$`` patterns; paths compared after
   percent-encoding normalisation; ``/robots.txt`` always allowed.
2. The first-match reading -- the original robots exclusion draft
   (robotstxt.org, 1996) as Python 3.12's ``urllib.robotparser`` reads it, kept
   here as AIA's own code. It is the second opinion the plan names, but alone
   it is *more permissive* than the RFC where it differs: it takes the
   first matching rule rather than the longest (``Allow: /`` before ``Disallow:
   /private`` allows ``/private``), ignores ``*`` and ``$`` (``Disallow:
   /*.pdf`` disallows nothing) and drops a second ``User-agent: *`` group. Where
   it is stricter (``Disallow: /`` before ``Allow: /public`` refuses
   ``/public``, and a tie goes to the first rule; a group whose agent is a
   substring of AIA's token applies), the stricter answer stands: AIA never
   requests what either reading forbids. A group's agent is read as its product
   token (``AIA-research/2.0`` becomes ``AIA-research``), which the reading would
   otherwise not match.

   It is not delegated to ``urllib.robotparser``: Python 3.13.8 (gh-138515)
   changed that module's normalisation and 3.13.14 (gh-138907) replaced its
   algorithm with RFC 9309's, both in patch releases, so a decision that asked
   it changed answer with the interpreter. AIA's answer depends on no
   interpreter's version (``.planning/plans/deep-research-web-search.md`` § 15).

A file's ``Sitemap:`` lines (RFC 9309 § 2.2.4: outside any group, for every
agent) are kept on the policy as data -- at most :data:`MAX_ROBOTS_SITEMAPS`,
each an absolute ``http(s)`` URL -- for a crawler to read; nothing here opens one.

Pure: stdlib only.
"""

from __future__ import annotations

import math
import re
import string
from collections.abc import Iterable
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Final
from urllib.parse import quote, unquote, urlparse, urlsplit

__all__ = [
    "AGENT_TOKEN",
    "MAX_ROBOTS_BYTES",
    "MAX_ROBOTS_SITEMAPS",
    "ROBOTS_DISALLOWED",
    "ROBOTS_UNAVAILABLE",
    "RobotsPolicy",
    "RobotsState",
    "policy_for_response",
    "sitemap_lines",
]

#: The product token AIA's user agent starts with and robots.txt groups are matched by.
AGENT_TOKEN: Final = "AIA-research"
#: RFC 9309 § 2.5: a crawler must parse at least 500 KiB; more is ignored.
MAX_ROBOTS_BYTES: Final = 512_000
#: ``Sitemap:`` lines kept from one robots.txt; later ones are ignored.
MAX_ROBOTS_SITEMAPS: Final = 50
#: A ``Sitemap:`` URL longer than this is ignored, never truncated.
MAX_SITEMAP_URL_CHARS: Final = 2048
#: A ``FetchRefused`` reason: the host's robots.txt forbids the URL.
ROBOTS_DISALLOWED: Final = "robots_disallowed"
#: A ``FetchRefused`` reason: the host's robots.txt could not be read, so nothing is.
ROBOTS_UNAVAILABLE: Final = "robots_unavailable"

_UNRESERVED: Final = frozenset(string.ascii_letters + string.digits + "-._~")
_HEX: Final = frozenset(string.hexdigits)
_USER_AGENT_VERSION: Final = re.compile(r"^(\s*user-agent\s*:\s*[^/#\s]+)/[^#]*", re.IGNORECASE)


class RobotsState(StrEnum):
    """How a host's policy was decided."""

    #: The file was read and its rules apply.
    RULES = "rules"
    #: No file (404 and most 4xx): everything is allowed.
    ALLOW_ALL = "allow_all"
    #: 401 or 403: everything is disallowed.
    DISALLOW_ALL = "disallow_all"
    #: 429, 5xx, a timeout or a lost answer: everything is disallowed for now.
    UNAVAILABLE = "unavailable"


def _normalise(text: str) -> str:
    """RFC 9309 § 2.2.2: unreserved octets decoded, everything else non-ASCII encoded."""
    out: list[str] = []
    i = 0
    while i < len(text):
        char = text[i]
        pair = text[i + 1 : i + 3]
        if char == "%" and len(pair) == 2 and set(pair) <= _HEX:
            decoded = chr(int(pair, 16))
            out.append(decoded if decoded in _UNRESERVED else "%" + pair.upper())
            i += 3
            continue
        if ord(char) <= 32 or ord(char) >= 127:
            out.append("".join(f"%{byte:02X}" for byte in char.encode("utf-8")))
        else:
            out.append(char)
        i += 1
    return "".join(out)


@dataclass(frozen=True, slots=True)
class _Rule:
    allow: bool
    #: The normalised path pattern, as written (``*`` and a final ``$`` special).
    pattern: str
    regex: re.Pattern[str] = field(compare=False)

    @classmethod
    def of(cls, *, allow: bool, path: str) -> _Rule:
        pattern = _normalise(path)
        anchored = pattern.endswith("$")
        body = pattern[:-1] if anchored else pattern
        source = ".*".join(re.escape(part) for part in body.split("*"))
        return cls(allow, pattern, re.compile(source + (r"\Z" if anchored else ""), re.DOTALL))


@dataclass(slots=True)
class _Group:
    agents: list[str] = field(default_factory=list)
    rules: list[_Rule] = field(default_factory=list)
    delays: list[float] = field(default_factory=list)


def _groups(text: str) -> list[_Group]:
    groups: list[_Group] = []
    current: _Group | None = None
    in_rules = False
    for raw in text.removeprefix("﻿").splitlines():
        line = raw.split("#", 1)[0].strip()
        if ":" not in line:
            continue
        key, value = (part.strip() for part in line.split(":", 1))
        key = key.lower()
        if key in {"user-agent", "useragent", "user agent"}:
            if current is None or in_rules:
                current = _Group()
                groups.append(current)
                in_rules = False
            current.agents.append(value.split("/", 1)[0].strip().lower())
        elif current is None:
            continue
        elif key in {"allow", "disallow"}:
            in_rules = True
            if value:  # an empty rule matches nothing (RFC 9309 § 2.2.2)
                current.rules.append(_Rule.of(allow=key == "allow", path=value))
        elif key == "crawl-delay":
            in_rules = True
            try:
                delay = float(value)
            except ValueError:
                continue
            if math.isfinite(delay) and delay >= 0:
                current.delays.append(delay)
    return groups


def sitemap_lines(text: str) -> tuple[str, ...]:
    """The ``Sitemap:`` URLs a robots.txt declares, in order, deduplicated and capped.

    Only absolute ``http``/``https`` URLs with a host are kept; the host is not
    checked here (a sitemap may live on another host; the reader decides).
    """
    found: dict[str, None] = {}
    for raw in text[:MAX_ROBOTS_BYTES].removeprefix("\ufeff").splitlines():
        line = raw.strip()
        if ":" not in line:
            continue
        key, value = (part.strip() for part in line.split(":", 1))
        if key.lower() != "sitemap" or not value or len(value) > MAX_SITEMAP_URL_CHARS:
            continue
        # A comment may follow; a URL has no whitespace in it.
        url = value.split()[0]
        parts = urlsplit(url)
        if parts.scheme.lower() not in {"http", "https"} or not parts.netloc:
            continue
        found.setdefault(url, None)
        if len(found) >= MAX_ROBOTS_SITEMAPS:
            break
    return tuple(found)


@dataclass(slots=True)
class _FirstMatchGroup:
    """One group as the first-match reading keeps it: agents as written, rules in order."""

    agents: list[str] = field(default_factory=list)
    #: ``(allow, path)``; the path quoted, compared as a plain prefix (``*`` alone: any).
    rules: list[tuple[bool, str]] = field(default_factory=list)
    #: The last whole-second ``Crawl-delay`` in the group.
    delay: int | None = None

    def applies_to(self, agent: str) -> bool:
        token = agent.split("/")[0].lower()
        return any(name == "*" or name.lower() in token for name in self.agents)

    def allows(self, path: str) -> bool:
        for allow, prefix in self.rules:
            if prefix == "*" or path.startswith(prefix):
                return allow
        return True


#: The schemes a URL is re-joined with ``//`` for, as Python 3.12 lists them (``uses_netloc``).
_JOINS_NETLOC: Final = frozenset(
    {
        "file",
        "ftp",
        "git",
        "git+ssh",
        "gopher",
        "http",
        "https",
        "imap",
        "itms-services",
        "mms",
        "nfs",
        "nntp",
        "prospero",
        "rsync",
        "rtsp",
        "rtsps",
        "rtspu",
        "sftp",
        "shttp",
        "snews",
        "svn",
        "svn+ssh",
        "telnet",
        "wais",
        "ws",
        "wss",
    }
)


def _join(scheme: str, netloc: str, path: str, params: str, query: str, fragment: str) -> str:
    """``urlunparse`` as Python 3.12 has it; 3.13 (gh-85110) prefixes ``//`` to a ``//x`` path."""
    url = f"{path};{params}" if params else path
    if netloc or (scheme in _JOINS_NETLOC and url[:2] != "//"):
        if url and url[:1] != "/":
            url = "/" + url
        url = "//" + netloc + url
    if scheme:
        url = scheme + ":" + url
    if query:
        url += "?" + query
    if fragment:
        url += "#" + fragment
    return url


def _first_match_rule(*, allow: bool, path: str) -> tuple[bool, str] | None:
    """A rule as the first-match reading compares it; None for a path that cannot be split."""
    if path == "" and not allow:  # an empty Disallow allows everything
        allow = True
    try:
        parts = urlparse(path)
    except ValueError:  # "//[x": 3.12 raised out of the whole parse
        return None
    return allow, quote(_join(*parts))


def _first_match_target(url: str) -> str:
    parts = urlparse(unquote(url))
    return quote(_join("", "", parts.path, parts.params, parts.query, parts.fragment)) or "/"


@dataclass(frozen=True, slots=True)
class _FirstMatchReading:
    """The first-match reading of a robots.txt, as Python 3.12's ``urllib.robotparser`` has it.

    A port of that module's ``parse``, ``can_fetch`` and ``crawl_delay``, so the second
    opinion is the same on every interpreter. ``urllib.parse`` only splits URLs here;
    joining them back is :func:`_join`'s. Two departures, where 3.12 raised ``ValueError``
    out of the whole parse: a ``Crawl-delay`` that is not decimal digits (``²``) is
    ignored (as 3.13.15 does, gh-153417), and so is a rule whose path cannot be split
    (``Disallow: //[x``, as 3.13.8 does, gh-138432).
    """

    #: Groups not naming ``*``, in file order; the first that applies is used.
    named: tuple[_FirstMatchGroup, ...]
    #: The first group naming ``*``, used when no named group applies; later ones dropped.
    default: _FirstMatchGroup | None

    @classmethod
    def parse(cls, lines: Iterable[str]) -> _FirstMatchReading:
        named: list[_FirstMatchGroup] = []
        defaults: list[_FirstMatchGroup] = []

        def close(group: _FirstMatchGroup) -> None:
            (defaults if "*" in group.agents else named).append(group)

        group = _FirstMatchGroup()
        state = 0  # 0: outside a group; 1: after a user-agent line; 2: after a rule
        for raw in lines:
            if not raw and state:  # a blank line ends a group, or discards an empty one
                if state == 2:
                    close(group)
                group, state = _FirstMatchGroup(), 0
            line = raw.split("#", 1)[0].strip()
            if ":" not in line:
                continue
            key, value = line.split(":", 1)
            key, value = key.strip().lower(), unquote(value.strip())
            if key == "user-agent":
                if state == 2:
                    close(group)
                    group = _FirstMatchGroup()
                group.agents.append(value)
                state = 1
            elif state == 0:
                continue
            elif key in {"allow", "disallow"}:
                rule = _first_match_rule(allow=key == "allow", path=value)
                if rule is not None:
                    group.rules.append(rule)
                state = 2
            elif key == "crawl-delay":
                if value.strip().isdecimal():
                    group.delay = int(value)
                state = 2
            elif key == "request-rate":
                state = 2
        if state == 2:
            close(group)
        return cls(tuple(named), defaults[0] if defaults else None)

    def _group(self, agent: str) -> _FirstMatchGroup | None:
        return next((g for g in self.named if g.applies_to(agent)), self.default)

    def allows(self, agent: str, url: str) -> bool:
        group = self._group(agent)
        return group is None or group.allows(_first_match_target(url))

    def crawl_delay(self, agent: str) -> int | None:
        group = self._group(agent)
        return None if group is None else group.delay


def _target(url: str) -> str:
    parts = urlsplit(url)
    return _normalise((parts.path or "/") + (f"?{parts.query}" if parts.query else ""))


@dataclass(frozen=True, slots=True)
class RobotsPolicy:
    """What one host's robots.txt allows AIA's agent, and how often."""

    state: RobotsState
    rules: tuple[_Rule, ...] = ()
    #: Seconds between two requests to the host; None when the file names none.
    crawl_delay_s: float | None = None
    #: Why the policy is what it is, for the journal ("http_503", "parsed", ...).
    detail: str = ""
    #: The file's ``Sitemap:`` URLs (:func:`sitemap_lines`); data, never followed here.
    sitemaps: tuple[str, ...] = ()
    _first_match: _FirstMatchReading | None = field(default=None, compare=False, repr=False)

    @classmethod
    def allow_all(cls, detail: str) -> RobotsPolicy:
        return cls(RobotsState.ALLOW_ALL, detail=detail)

    @classmethod
    def disallow_all(cls, detail: str) -> RobotsPolicy:
        return cls(RobotsState.DISALLOW_ALL, detail=detail)

    @classmethod
    def unavailable(cls, detail: str) -> RobotsPolicy:
        return cls(RobotsState.UNAVAILABLE, detail=detail)

    @classmethod
    def parse(cls, text: str, *, agent: str = AGENT_TOKEN) -> RobotsPolicy:
        """The policy a robots.txt body sets for ``agent`` (its product token)."""
        text = text[:MAX_ROBOTS_BYTES]
        token = agent.lower()
        groups = _groups(text)
        chosen = [g for g in groups if token in g.agents] or [g for g in groups if "*" in g.agents]
        delays = [d for g in chosen for d in g.delays]
        # The first-match reading matches a group's agent as a substring of ours, so
        # "AIA-research/2.0" would not name AIA there: it is given the product token.
        first_match = _FirstMatchReading.parse(
            _USER_AGENT_VERSION.sub(r"\1", line) for line in text.splitlines()
        )
        first_match_delay = first_match.crawl_delay(agent)
        if first_match_delay is not None:
            delays.append(float(first_match_delay))
        return cls(
            RobotsState.RULES,
            rules=tuple(rule for g in chosen for rule in g.rules),
            crawl_delay_s=max(delays) if delays else None,
            detail="parsed",
            sitemaps=sitemap_lines(text),
            _first_match=first_match,
        )

    def _rfc_allows(self, url: str) -> bool:
        target = _target(url)
        best: _Rule | None = None
        for rule in self.rules:
            if not rule.regex.match(target):
                continue
            if (
                best is None
                or len(rule.pattern) > len(best.pattern)
                or (len(rule.pattern) == len(best.pattern) and rule.allow)
            ):
                best = rule
        return best is None or best.allow

    def refusal(self, url: str) -> str | None:
        """None when AIA may request ``url`` on this host; otherwise the refusal's reason."""
        if urlsplit(url).path == "/robots.txt":
            return None
        if self.state is RobotsState.ALLOW_ALL:
            return None
        if self.state is RobotsState.DISALLOW_ALL:
            return ROBOTS_DISALLOWED
        if self.state is RobotsState.UNAVAILABLE:
            return ROBOTS_UNAVAILABLE
        if not self._rfc_allows(url):
            return ROBOTS_DISALLOWED
        if self._first_match is not None and not self._first_match.allows(AGENT_TOKEN, url):
            return ROBOTS_DISALLOWED
        return None


def policy_for_response(status: int, body: bytes) -> RobotsPolicy:
    """The policy a host's final (non-redirect) answer for ``/robots.txt`` sets."""
    if 200 <= status < 300:
        return RobotsPolicy.parse(body[:MAX_ROBOTS_BYTES].decode("utf-8", errors="replace"))
    if status in (401, 403):
        return RobotsPolicy.disallow_all(f"http_{status}")
    if status == 429 or status >= 500:
        return RobotsPolicy.unavailable(f"http_{status}")
    if 400 <= status < 500:
        return RobotsPolicy.allow_all(f"http_{status}")
    # 1xx, or a redirect the caller did not follow: nothing was read.
    return RobotsPolicy.unavailable(f"http_{status}")
