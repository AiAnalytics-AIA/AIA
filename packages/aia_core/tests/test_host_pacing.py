"""The politeness seam: the in-process pacer, and any transport put behind a pacer.

``LocalHostPacer`` is the rule ``PublicHttpsTransport`` kept before the seam existed
(``test_web_public_fetch.py`` still holds the transport to it, unedited); the shared
pacer is ``test_fan_out_coordination.py``'s.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field

import pytest

from aia_core.domain.deep_research.contracts import RetrievalMode
from aia_core.domain.deep_research.web import FetchRefused
from aia_core.infrastructure.host_pacing import HOST_WAIT_EXCEEDED, LocalHostPacer, PacedTransport
from aia_core.infrastructure.web_retrieval import FetchedResponse
from aia_core.infrastructure.web_retrieval_live import PublicHttpsTransport


@dataclass
class Clock:
    now: float = 100.0
    slept: list[float] = field(default_factory=list)

    def monotonic(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.slept.append(seconds)
        self.now += seconds


def test_the_local_pacer_waits_the_interval_after_the_last_end() -> None:
    clock = Clock()
    pacer = LocalHostPacer(monotonic=clock.monotonic, sleep=clock.sleep)
    with pacer.turn("a.example", 2.0):
        clock.now += 0.5
    with pacer.turn("a.example", 2.0):
        pass
    with pacer.turn("b.example", 2.0):
        pass
    assert clock.slept == [2.0], "the second request to a.example only"


def test_the_local_pacer_records_the_end_of_a_failed_request() -> None:
    clock = Clock()
    pacer = LocalHostPacer(monotonic=clock.monotonic, sleep=clock.sleep)
    with pytest.raises(RuntimeError), pacer.turn("a.example", 1.0):
        raise RuntimeError("the request failed")
    with pacer.turn("a.example", 1.0):
        pass
    assert clock.slept == [1.0]


@dataclass
class Inner:
    calls: list[str] = field(default_factory=list)

    @property
    def retrieval_mode(self) -> RetrievalMode:
        return RetrievalMode.RECORDED

    def get(self, url: str, *, address: str, max_bytes: int) -> FetchedResponse:
        self.calls.append(url)
        return FetchedResponse(status=200, headers={}, body=b"ok", truncated=False)


@dataclass
class Refusing:
    turns: list[tuple[str, float]] = field(default_factory=list)

    @contextmanager
    def turn(self, host: str, interval_s: float) -> Iterator[None]:
        self.turns.append((host, interval_s))
        raise FetchRefused("too late", reason=HOST_WAIT_EXCEEDED)
        yield  # pragma: no cover - never reached


def test_a_paced_transport_asks_the_pacer_for_the_urls_host_and_keeps_the_mode() -> None:
    clock = Clock()
    inner = Inner()
    paced = PacedTransport(
        inner, pacer=LocalHostPacer(monotonic=clock.monotonic, sleep=clock.sleep), interval_s=1.5
    )
    for path in ("/a", "/b"):
        assert paced.get(f"https://stats.example{path}", address="93.184.215.14", max_bytes=10)
    assert inner.calls == ["https://stats.example/a", "https://stats.example/b"]
    assert clock.slept == [1.5]
    assert paced.retrieval_mode is RetrievalMode.RECORDED and paced.inner is inner


def test_a_refusal_by_the_pacer_sends_nothing() -> None:
    inner, pacer = Inner(), Refusing()
    paced = PacedTransport(inner, pacer=pacer, interval_s=1.0)
    with pytest.raises(FetchRefused) as refused:
        paced.get("https://Stats.Example/x", address="93.184.215.14", max_bytes=10)
    assert refused.value.reason == HOST_WAIT_EXCEEDED
    assert inner.calls == [] and pacer.turns == [("stats.example", 1.0)]


def test_a_negative_interval_is_refused() -> None:
    with pytest.raises(ValueError, match="not negative"):
        PacedTransport(Inner(), pacer=LocalHostPacer(), interval_s=-1.0)


@dataclass
class Recording:
    """A pacer that lets everything through and says what it was asked."""

    turns: list[tuple[str, float]] = field(default_factory=list)

    @contextmanager
    def turn(self, host: str, interval_s: float) -> Iterator[None]:
        self.turns.append((host, interval_s))
        yield


@dataclass
class Wire:
    answers: dict[str, FetchedResponse]
    sent: list[str] = field(default_factory=list)

    def get(
        self, *, address: str, host: str, target: str, headers: object, max_bytes: int
    ) -> FetchedResponse:
        self.sent.append(f"{host}{target}")
        return self.answers.get(
            target, FetchedResponse(status=404, headers={}, body=b"", truncated=False)
        )


class OneAddress:
    def resolve(self, host: str) -> tuple[str, ...]:
        return ("93.184.215.14",)


def test_the_public_transport_asks_its_pacer_for_every_request_robots_included() -> None:
    """The robots.txt at the minimum interval, the page at the host's crawl delay."""
    pacer = Recording()
    wire = Wire(
        {
            "/robots.txt": FetchedResponse(
                status=200,
                headers={"content-type": "text/plain"},
                body=b"User-agent: *\nCrawl-delay: 4\n",
                truncated=False,
            ),
            "/a": FetchedResponse(
                status=200, headers={"content-type": "text/html"}, body=b"<p>x</p>", truncated=False
            ),
        }
    )
    transport = PublicHttpsTransport(
        contact="research-desk@aia.example",
        resolver=OneAddress(),
        wire=wire,
        min_interval_s=1.0,
        pacer=pacer,
    )

    transport.get("https://stats.example/a", address="93.184.215.14", max_bytes=1000)

    assert wire.sent == ["stats.example/robots.txt", "stats.example/a"]
    assert pacer.turns == [("stats.example", 1.0), ("stats.example", 4.0)]
