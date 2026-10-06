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
2. ``urllib.robotparser`` -- the standard library's reading. It is kept as a
   second opinion because it is the reference the plan names, but alone it
   is *more permissive* than the RFC where it differs: it takes the first
   matching rule rather than the longest (``Allow: /`` before ``Disallow:
   /private`` allows ``/private``), ignores ``*`` and ``$`` (``Disallow:
   /*.pdf`` disallows nothing) and drops a second ``User-agent: *`` group. Where
   it is stricter (``Disallow: /`` before ``Allow: /public`` refuses
   ``/public``, and a tie goes to the first rule; a group whose agent is a
   substring of AIA's token applies), the stricter answer stands: AIA never
   requests what either reading forbids. It is given each group's product token
   (``AIA-research/2.0`` becomes ``AIA-research``), which it would not match.

Pure: stdlib only.
"""

from __future__ import annotations

import math
import re
import string
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Final
from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser

__all__ = [
    "AGENT_TOKEN",
    "MAX_ROBOTS_BYTES",
    "ROBOTS_DISALLOWED",
    "ROBOTS_UNAVAILABLE",
    "RobotsPolicy",
    "RobotsState",
    "policy_for_response",
]

#: The product token AIA's user agent starts with and robots.txt groups are matched by.
AGENT_TOKEN: Final = "AIA-research"
#: RFC 9309 § 2.5: a crawler must parse at least 500 KiB; more is ignored.
MAX_ROBOTS_BYTES: Final = 512_000
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
    _stdlib: RobotFileParser | None = field(default=None, compare=False, repr=False)

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
        stdlib = RobotFileParser()
        # The standard library matches a group's agent as a substring of ours, so
        # "AIA-research/2.0" would not name AIA there: it is given the product token.
        stdlib.parse(_USER_AGENT_VERSION.sub(r"\1", line) for line in text.splitlines())
        stdlib_delay = stdlib.crawl_delay(agent)
        if stdlib_delay is not None:
            delays.append(float(stdlib_delay))
        return cls(
            RobotsState.RULES,
            rules=tuple(rule for g in chosen for rule in g.rules),
            crawl_delay_s=max(delays) if delays else None,
            detail="parsed",
            _stdlib=stdlib,
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
        if self._stdlib is not None and not self._stdlib.can_fetch(AGENT_TOKEN, url):
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
