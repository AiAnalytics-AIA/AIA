"""Whose turn it is to request a host: the politeness seam every fetcher goes through.

A :class:`HostPacer` holds one host for one request and lets it start only once the
host is free and the interval it is owed has passed since the end of the previous
request to it -- one request at a time per host, measured from the end of the last
(plan ``deep-research-web-search.md`` chunk 5). Where that state lives is the
pacer's:

* :class:`LocalHostPacer` -- in this process: the rule ``PublicHttpsTransport``
  always kept, and still keeps by default;
* ``fan_out_coordination.SharedHostPacer`` -- in PostgreSQL, one row per host, for
  every process of the deployment (chunk 21,
  ``docs/architecture/deep-research-fan-out.md`` § 3).

:class:`PacedTransport` puts any :class:`~aia_core.infrastructure.web_retrieval.FetchTransport`
behind a pacer at a fixed interval -- a transport that reads no robots.txt (the
pinned routes, a recorded replay in the tests). ``PublicHttpsTransport`` takes a
pacer itself, because the interval it owes a host depends on that host's crawl delay.

A pacer that would have to wait longer than it may refuses before anything is sent
(``FetchRefused``, :data:`HOST_WAIT_EXCEEDED`): the caller's request is answered as a
failure that sent nothing, never queued without bound.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable, Iterator
from contextlib import AbstractContextManager, contextmanager
from typing import Final, Protocol

from ..domain.deep_research.contracts import RetrievalMode
from ..domain.deep_research.web import check_url
from .web_retrieval import FetchedResponse, FetchTransport

__all__ = [
    "HOST_WAIT_EXCEEDED",
    "HostPacer",
    "LocalHostPacer",
    "PacedTransport",
]

#: Why a request was refused before sending: its host's turn would come too late.
HOST_WAIT_EXCEEDED: Final = "host_wait_exceeded"


class HostPacer(Protocol):
    """Hold ``host`` for one request, starting once the host is free and its interval passed."""

    def turn(self, host: str, interval_s: float) -> AbstractContextManager[None]:
        """Wait for the host's turn, hold it for the ``with`` block, then record its end.

        ``interval_s`` is what the host is owed after this request: the next one to it
        starts no sooner than this one's end plus ``interval_s``. Raises ``FetchRefused``
        (:data:`HOST_WAIT_EXCEEDED`) instead of waiting longer than the pacer allows.
        """
        ...


class LocalHostPacer:
    """The in-process pacer: a lock per host and the end of its last request.

    Exactly the rule ``PublicHttpsTransport`` kept before the seam existed: under the
    host's lock, wait until ``last end + interval``, send, record the end. The clock
    and the sleep are injectable. It never refuses: within one process the wait is
    bounded by the interval itself.
    """

    def __init__(
        self,
        *,
        monotonic: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._monotonic = monotonic
        self._sleep = sleep
        self._guard = threading.Lock()
        self._locks: dict[str, threading.Lock] = {}
        self._last: dict[str, float] = {}

    def _lock(self, host: str) -> threading.Lock:
        with self._guard:
            return self._locks.setdefault(host, threading.Lock())

    @contextmanager
    def turn(self, host: str, interval_s: float) -> Iterator[None]:
        with self._lock(host):
            last = self._last.get(host)
            if last is not None:
                wait = last + interval_s - self._monotonic()
                if wait > 0:
                    self._sleep(wait)
            try:
                yield
            finally:
                self._last[host] = self._monotonic()


class PacedTransport:
    """Any fetch transport, paced per host by a :class:`HostPacer` at a fixed interval.

    The inner transport's mode is this transport's mode: pacing changes when a request
    leaves, never what answers it. A refusal by the pacer happens before the inner
    transport is called, so nothing is sent.
    """

    def __init__(self, inner: FetchTransport, *, pacer: HostPacer, interval_s: float) -> None:
        if interval_s < 0:
            raise ValueError("a host's interval is not negative")
        self._inner = inner
        self._pacer = pacer
        self._interval_s = interval_s

    @property
    def retrieval_mode(self) -> RetrievalMode:
        return self._inner.retrieval_mode

    @property
    def inner(self) -> FetchTransport:
        return self._inner

    def get(self, url: str, *, address: str, max_bytes: int) -> FetchedResponse:
        with self._pacer.turn(check_url(url), self._interval_s):
            return self._inner.get(url, address=address, max_bytes=max_bytes)
