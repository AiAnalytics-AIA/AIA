"""When an archived copy of a page may be asked for: only when the live page cannot serve.

Plan ``deep-research-web-search.md`` § 4 (never an archive to get round a paywall),
§ 5.3 (the ``archive`` tool) and § 7 rung 9: an archived copy is for a **dead or
moved page only**, never a first choice and never for a page that is live behind a
paywall, a login or a challenge. The live attempt comes first; this module reads what
it found and decides.

:func:`decide_archive_use` is the only issuer of an :class:`ArchivePermit`, and the
retrieval gate asks the archive only with one, for the same URL. It allows:

* **dead** -- the live fetch was answered ``404`` or ``410``, or the host no longer
  resolves (``address_unresolved``);
* **moved** -- the live fetch was redirected to another URL and the page it landed
  on does not hold the quote that was needed;
* **changed** -- the live page is the same URL and no longer holds the quote.

Everything else is refused, and said: the live page holds the quote
(``live_has_quote``); a page served behind a barrier, or answered ``401``, ``402``,
``403`` or ``451`` (``live_access_restricted``); a rate limit, a server error or a
failed connection, which a later live attempt may get past (``live_transient``); an
answer whose delivery is unknown (``live_uncertain``); a URL AIA's own policy
refused before sending (``live_refused``) -- an archive does not route round AIA's
rules; and any failure not named here (``live_failure_unrecognised``): unknown is
never scored as dead.

Whether a captured page is behind a barrier is stated by whoever captured it; there
is no default (:class:`AccessBarrier` has ``UNKNOWN``, and unknown refuses).

Pure: stdlib only, and grounding's text normalisation.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Final

from .grounding import locate_quote

__all__ = [
    "AccessBarrier",
    "ArchiveBasis",
    "ArchiveDecision",
    "ArchivePermit",
    "LiveAttempt",
    "decide_archive_use",
]


class AccessBarrier(StrEnum):
    """What stood between a reader and a live page's text, as its capture states it."""

    NONE = "none"
    PAYWALL = "paywall"
    LOGIN = "login"
    CHALLENGE = "challenge"  # a CAPTCHA or a bot check
    UNKNOWN = "unknown"


class ArchiveBasis(StrEnum):
    """Why the archive may be asked."""

    DEAD = "dead"
    MOVED = "moved"
    CHANGED = "changed"


#: Fetch failures that mean the page is gone: the publisher said so, or the host is gone.
_DEAD: Final = frozenset({"http_404", "http_410", "address_unresolved"})
#: Answers that mean "not for you": a paywall, a login, a refusal, a legal block.
_RESTRICTED: Final = frozenset({"http_401", "http_402", "http_403", "http_451"})
#: Failures a later live attempt may get past.
_TRANSIENT_FIXED: Final = frozenset(
    {"http_408", "http_429", "connect_failed", "tls_failed", "transport_failed", "reset"}
)
_SERVER_ERROR: Final = re.compile(r"^http_5[0-9]{2}$")
#: Refusals by AIA's own fetch policy (``web.check_url`` and friends), before sending.
_REFUSED: Final = frozenset(
    {
        "url_invalid",
        "url_scheme",
        "url_credentials",
        "url_port",
        "url_internal_host",
        "address_invalid",
        "address_not_public",
        "content_type",
        "body_too_large",
        "redirect_invalid",
        "too_many_redirects",
        "class_a_url",
    }
)


@dataclass(frozen=True, slots=True)
class LiveAttempt:
    """What one live fetch of ``url`` found. Built from the gate's fetch outcome.

    Exactly one of: ``failure`` (the fetch's reason) or a captured page
    (``final_url``, ``text`` and ``barrier``, all stated).
    """

    url: str
    failure: str | None
    uncertain: bool
    final_url: str | None = None
    text: str | None = None
    barrier: AccessBarrier | None = None

    def __post_init__(self) -> None:
        captured = (self.final_url, self.text, self.barrier)
        if self.failure is not None:
            if any(part is not None for part in captured):
                raise ValueError("a failed attempt carries no page")
        elif any(part is None for part in captured) or self.uncertain:
            raise ValueError("a captured page states its final URL, its text and its barrier")


# Proves a permit was issued by decide_archive_use. Module-private: a permit decoded
# from model output or a stored payload cannot carry it.
_ARCHIVE_ISSUER: Final = object()


@dataclass(frozen=True, slots=True)
class ArchivePermit:
    """Leave to ask the archive about one URL, and why."""

    url: str
    basis: ArchiveBasis
    _issuer: Any

    def __post_init__(self) -> None:
        if self._issuer is not _ARCHIVE_ISSUER:
            raise ValueError("an archive permit is issued only by decide_archive_use")


@dataclass(frozen=True, slots=True)
class ArchiveDecision:
    """A permit, or the reason there is none."""

    url: str
    permit: ArchivePermit | None
    refusal: str | None


def _refused(url: str, reason: str) -> ArchiveDecision:
    return ArchiveDecision(url=url, permit=None, refusal=reason)


def _permitted(url: str, basis: ArchiveBasis) -> ArchiveDecision:
    return ArchiveDecision(
        url=url, permit=ArchivePermit(url=url, basis=basis, _issuer=_ARCHIVE_ISSUER), refusal=None
    )


def decide_archive_use(attempt: LiveAttempt, *, needed_quote: str) -> ArchiveDecision:
    """May the archive be asked for ``attempt.url``, given what the live page did?

    ``needed_quote`` is the text the reader needs from the page (a cited sentence or
    figure). It must say something: an empty need cannot show a page has changed.
    """
    url = attempt.url
    if not needed_quote.strip():
        raise ValueError("the quote that was needed is stated")
    if attempt.uncertain:
        return _refused(url, "live_uncertain")
    if attempt.failure is not None:
        reason = attempt.failure
        if reason in _DEAD:
            return _permitted(url, ArchiveBasis.DEAD)
        if reason in _RESTRICTED:
            return _refused(url, "live_access_restricted")
        if reason in _TRANSIENT_FIXED or _SERVER_ERROR.fullmatch(reason):
            return _refused(url, "live_transient")
        if reason in _REFUSED or reason.startswith(("refused_", "egress_")):
            return _refused(url, "live_refused")
        return _refused(url, "live_failure_unrecognised")
    if attempt.barrier is not AccessBarrier.NONE:
        # A paywall, a login, a challenge -- or nobody said: never round it by archive.
        return _refused(url, "live_access_restricted")
    if locate_quote(attempt.text or "", needed_quote) is not None:
        return _refused(url, "live_has_quote")
    if attempt.final_url != url:
        return _permitted(url, ArchiveBasis.MOVED)
    return _permitted(url, ArchiveBasis.CHANGED)
