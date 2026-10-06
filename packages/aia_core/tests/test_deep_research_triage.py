"""Triage readers: the contract, grounding before hand-off, and the parallel runner.

Plan ``deep-research-web-search.md`` chunk 20. Everything runs the real
:class:`GovernedModelGateway` over the real Bedrock adapter, with a recorded transport
in place of AWS (``fixtures/deep_research_triage/recorded.json``: fictional pages and
hand-authored Converse answers, keyed by the page each request carries, so answers
match pages whatever order the requests leave in). No network.

The caller here (:class:`MeteredCaller`) keeps the worker's obligations the way
``aia_executors.ai_step.StepModelCaller`` does: one reservation per logical request,
its own journal, settled once with what the request's calls cost.
"""

from __future__ import annotations

import ast
import asyncio
import json
from collections import Counter
from collections.abc import AsyncIterator, Sequence
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from aia_core.application import deep_research_triage as runner_module
from aia_core.application.deep_research_triage import (
    SemaphoreLimiter,
    TriageRun,
    TriageStatus,
    triage_pages,
)
from aia_core.application.model_gateway import GovernedModelGateway
from aia_core.domain.ai_contracts import (
    Delivery,
    ModelCallFailed,
    ModelRequest,
    ModelResult,
    ProviderErrorKind,
)
from aia_core.domain.ai_execution import ExecutionContext, ReservationView
from aia_core.domain.ai_models import ModelCapability, ModelRegistry, parse_model_config
from aia_core.domain.deep_research import triage as triage_module
from aia_core.domain.deep_research.contracts import QuarantineReason
from aia_core.domain.deep_research.grounding import detect_instructions
from aia_core.domain.deep_research.triage import (
    MAX_CANDIDATE_QUOTES,
    TRIAGE_AGENT_ID,
    TRIAGE_TEXT_CHARS,
    TriageDrop,
    TriagePage,
    TriageQuestion,
    TriageVerdict,
    page_part,
    review_verdict,
    triage_agent,
    triage_questions,
    triage_request,
)
from aia_core.domain.licence import DataLineage
from aia_core.domain.licence_determinations import recorded_policy
from aia_core.domain.providers import Provider
from aia_core.domain.residency import DataClass, EgressPolicy, ProviderRoute, ResidencyZone
from aia_core.domain.workflow import FailureClass
from aia_core.infrastructure.ai_call_journal import InMemoryCallJournal
from aia_core.infrastructure.model_adapters import BedrockConverseAdapter
from aia_core.infrastructure.model_adapters.transport import (
    HttpRequest,
    HttpResponse,
    TransportFailure,
)

FIXTURE = Path(__file__).parent / "fixtures" / "deep_research_triage" / "recorded.json"
RECORDED: dict[str, Any] = json.loads(FIXTURE.read_text(encoding="utf-8"))

PROFILE = "eu.example.light-test-v1:0"  # a test id, not a real profile
ROUTE = "bedrock-eu-test"
POLICY = "policy-triage-v1"
#: $1 in, $5 out per Mtok: the test route's light-model prices.
IN_PRICE, OUT_PRICE = 1.0, 5.0
#: Reservation per logical request: a primary and one repair at the ceilings fit.
RESERVATION_USD = 0.5
MAX_OUTPUT = 1024


# --------------------------------------------------------------------------- #
# Recorded world
# --------------------------------------------------------------------------- #


def _text(segments: Sequence[Any]) -> str:
    out = []
    for segment in segments:
        out.append(segment if isinstance(segment, str) else segment["repeat"] * segment["times"])
    return "".join(out)


def _pages() -> list[TriagePage]:
    pages = []
    for page in RECORDED["pages"]:
        text = _text(page["text"])
        pages.append(
            TriagePage(
                snapshot_id=page["snapshot_id"],
                url=page["url"],
                title=page["title"],
                text=text,
                instructions_detected=detect_instructions(text),
            )
        )
    return pages


QUESTIONS = triage_questions(RECORDED["sub_questions"])
PAGES = _pages()
BY_ID = {p.snapshot_id: p for p in PAGES}


class Signer:
    def sign(self, *, method: str, url: str, headers: Any, body: bytes) -> dict[str, str]:
        return {**dict(headers), "authorization": "AWS4-HMAC-SHA256 test"}


def _converse(answer: dict[str, Any]) -> dict[str, Any]:
    return {
        "output": {
            "message": {
                "role": "assistant",
                "content": [
                    {"toolUse": {"toolUseId": "t1", "name": RECORDED["tool"], "input": answer}}
                ],
            }
        },
        "stopReason": "tool_use",
        "usage": {"inputTokens": 2000, "outputTokens": 120},
    }


class RecordedTriage:
    """Bedrock's side: the next recorded answer for the page a request carries.

    Instrumented: counts requests in flight (each send yields to the loop before it
    answers, so concurrent requests do overlap) and keeps the highest count seen.
    ``hold`` makes chosen pages wait for an event, to force a completion order.
    """

    def __init__(
        self,
        *,
        uncertain: frozenset[str] = frozenset(),
        hold: dict[str, asyncio.Event] | None = None,
    ) -> None:
        self._answers = {p["snapshot_id"]: list(p["answers"]) for p in RECORDED["pages"]}
        self._uncertain = uncertain
        self._hold = hold or {}
        self.requests: list[HttpRequest] = []
        self.pages_sent: list[str] = []
        self.completed: list[str] = []
        self.in_flight = 0
        self.max_in_flight = 0

    @staticmethod
    def page_of(request: HttpRequest) -> str:
        user = request.body["messages"][0]["content"][0]["text"]
        return str(json.loads(user)["page"]["source_id"])

    async def send(self, request: HttpRequest, *, timeout_s: float) -> HttpResponse:
        page = self.page_of(request)
        self.requests.append(request)
        self.pages_sent.append(page)
        self.in_flight += 1
        self.max_in_flight = max(self.max_in_flight, self.in_flight)
        try:
            for _ in range(3):
                await asyncio.sleep(0)
            if page in self._hold:
                await self._hold[page].wait()
            if page in self._uncertain:
                raise TransportFailure(
                    "read timed out after sending",
                    kind=ProviderErrorKind.TRANSPORT,
                    delivery=Delivery.UNKNOWN,
                )
            answer = self._answers[page].pop(0)
        finally:
            self.in_flight -= 1
        self.completed.append(page)
        return HttpResponse(
            status=200,
            headers={"x-amzn-requestid": f"req-{len(self.requests)}"},
            body=_converse(answer),
        )


def _registry(*, bind_triage: bool = True) -> ModelRegistry:
    binding = {"provider": Provider.AWS_BEDROCK.value, "model": PROFILE, "route_id": ROUTE}
    capability = (
        ModelCapability.RESEARCH_TRIAGE if bind_triage else ModelCapability.RESEARCH_REASONING
    )
    return parse_model_config(
        {
            "models": [
                {
                    "provider": Provider.AWS_BEDROCK.value,
                    "model": PROFILE,
                    "capabilities": [capability.value],
                    "max_output_tokens": 8192,
                    "context_window_tokens": 200000,
                    "pricing": {"input_usd_per_mtok": IN_PRICE, "output_usd_per_mtok": OUT_PRICE},
                    "supports_strict_schema": False,
                }
            ],
            "policies": [
                {
                    "version": POLICY,
                    "allowed_providers": [Provider.AWS_BEDROCK.value],
                    "bindings": {capability.value: binding},
                }
            ],
        }
    )


def _gateway(transport: RecordedTriage, *, bind_triage: bool = True) -> GovernedModelGateway:
    route = ProviderRoute(
        route_id=ROUTE,
        provider=Provider.AWS_BEDROCK.value,
        zone=ResidencyZone.EU,
        eu_processing_approved=True,
        excluded_from_training=True,
        approved_for=frozenset({DataClass.CLASS_C_INTERNAL}),
    )
    adapter = BedrockConverseAdapter(
        transport=transport, signer=Signer(), region="eu-central-1", model_id=PROFILE
    )
    return GovernedModelGateway(
        registry=_registry(bind_triage=bind_triage),
        egress=EgressPolicy(routes=(route,)),
        licence=recorded_policy(),
        adapters={ROUTE: adapter},
    )


class Stop(BaseException):
    """Stands in for the worker's ``StopExecution`` (a ``BaseException``)."""


class MeteredCaller:
    """Reserve once per logical request, journal every call, settle once.

    ``stop_on`` raises :class:`Stop` from the reservation of that page's request, as
    a worker that lost its lease or ran out of budget would.
    """

    def __init__(self, gateway: GovernedModelGateway, scope: Any, *, stop_on: str = "") -> None:
        self._gateway = gateway
        self._scope = scope
        self._stop_on = stop_on
        self.reserved: list[str] = []
        self.settled: dict[str, float] = {}
        self.calls_per_request: dict[str, int] = {}

    def _context(self, journal: Any, reservation: ReservationView | None) -> ExecutionContext:
        return ExecutionContext(
            scope=self._scope,
            runtime_version="runtime-test",
            journal=journal,
            run_id="RUN-1",
            step_id="STP-1",
            attempt_id="ATT-1",
            reservation=reservation,
        )

    def preflight(self, request: ModelRequest) -> object:
        return self._gateway.preflight(request, self._context(InMemoryCallJournal(), None))

    async def invoke(self, request: ModelRequest) -> ModelResult:
        page = json.loads(request.messages[0].content)["page"]["source_id"]
        if page == self._stop_on:
            raise Stop(page)
        reservation = ReservationView(f"RSV-{page}", RESERVATION_USD)
        assert reservation.reservation_id not in self.reserved, "reserved twice"
        self.reserved.append(reservation.reservation_id)
        journal = InMemoryCallJournal()
        try:
            result = await self._gateway.invoke(request, self._context(journal, reservation))
        except ModelCallFailed as failure:
            if failure.outcome_known:
                self._settle(reservation, journal)
            raise
        self._settle(reservation, journal)
        return result

    def _settle(self, reservation: ReservationView, journal: InMemoryCallJournal) -> None:
        assert reservation.reservation_id not in self.settled, "settled twice"
        self.settled[reservation.reservation_id] = journal.committed_usd()
        self.calls_per_request[reservation.reservation_id] = len(journal.dispatched)


@pytest.fixture
def scope(scoped: Any) -> Any:
    return scoped.scope(user="researcher", study="primary")


def _run(
    caller: MeteredCaller,
    pages: Sequence[TriagePage] = PAGES,
    *,
    limit: int = 3,
    limiter: Any = None,
) -> TriageRun:
    return asyncio.run(
        triage_pages(
            pages,
            QUESTIONS,
            caller=caller,
            limiter=limiter or SemaphoreLimiter(limit),
            data_class=DataClass.CLASS_C_INTERNAL,
            lineage=DataLineage.none(),
            policy_version=POLICY,
            max_output_tokens=MAX_OUTPUT,
        )
    )


def _outcome(run: TriageRun, page: str) -> Any:
    return next(o for o in run.outcomes if o.snapshot_id == page)


def _id(n: int) -> str:
    return f"SNP-{n:024d}"


# --------------------------------------------------------------------------- #
# The contract
# --------------------------------------------------------------------------- #


def test_a_verdict_carries_at_most_three_quotes() -> None:
    TriageVerdict.model_validate(
        {"relevant": True, "sub_question": "Q1", "quotes": ["a" * 20] * MAX_CANDIDATE_QUOTES}
    )
    with pytest.raises(ValidationError, match="at most 3"):
        TriageVerdict.model_validate(
            {"relevant": True, "sub_question": "Q1", "quotes": ["a" * 20] * 4}
        )


@pytest.mark.parametrize(
    "answer",
    [
        {"relevant": True, "sub_question": None, "quotes": []},
        {"relevant": False, "sub_question": "Q1", "quotes": []},
        {"relevant": False, "sub_question": None, "quotes": ["a" * 30]},
        {"relevant": True, "sub_question": "Q10", "quotes": []},
        {"relevant": True, "sub_question": "Q1", "quotes": ["a" * 401]},
        {"relevant": True, "sub_question": "Q1", "quotes": [], "reason": "extra"},
    ],
)
def test_an_inconsistent_or_open_verdict_is_a_violation(answer: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        TriageVerdict.model_validate_json(json.dumps(answer), strict=True)


def test_the_triage_reader_names_the_light_capability_and_holds_no_tools() -> None:
    agent = triage_agent(max_output_tokens=MAX_OUTPUT)
    assert agent.capability is ModelCapability.RESEARCH_TRIAGE
    assert agent.allowed_tools == frozenset()
    assert agent.agent_id == TRIAGE_AGENT_ID
    assert agent.schema_repair_attempts == 1


def test_a_request_carries_the_part_and_questions_as_data_and_asks_for_no_model() -> None:
    page = BY_ID[_id(7)]
    part = page_part(page.text)
    request = triage_request(
        page,
        part,
        QUESTIONS,
        data_class=DataClass.CLASS_C_INTERNAL,
        lineage=DataLineage.none(),
        policy_version=POLICY,
        max_output_tokens=MAX_OUTPUT,
    )
    assert len(request.messages) == 1
    payload = json.loads(request.messages[0].content)
    assert payload["page"]["text"] == part.text
    assert payload["page"]["text_truncated"] is True
    assert [q["id"] for q in payload["sub_questions"]] == ["Q1", "Q2"]
    assert request.requested_model is None and request.requested_provider is None
    assert request.thinking_budget_tokens is None
    assert not request.fallback_policy.is_explicit


def test_questions_are_numbered_in_order_and_at_least_one_is_needed() -> None:
    assert triage_questions([" a ", "", "b"]) == (
        TriageQuestion("Q1", "a"),
        TriageQuestion("Q2", "b"),
    )
    with pytest.raises(ValueError):
        triage_questions([" "])
    with pytest.raises(ValueError):
        triage_questions(["q"] * 10)


def test_a_part_is_bounded_and_ends_on_a_word() -> None:
    text = "slovo " * 3000
    part = page_part(text)
    assert len(part.text) <= TRIAGE_TEXT_CHARS
    assert part.truncated and part.text.endswith("slovo")
    assert text[part.start : part.end] == part.text
    whole = page_part("krátká stránka")
    assert whole.text == "krátká stránka" and not whole.truncated
    later = page_part(text, start=TRIAGE_TEXT_CHARS)
    assert later.start == TRIAGE_TEXT_CHARS


# --------------------------------------------------------------------------- #
# Grounding before hand-off
# --------------------------------------------------------------------------- #


def _review(page_id: str, answer: dict[str, Any]) -> Any:
    page = BY_ID[page_id]
    return review_verdict(page, page_part(page.text), QUESTIONS, TriageVerdict(**answer))


def test_a_quote_not_in_the_snapshot_is_dropped_and_counted() -> None:
    review = _review(_id(1), RECORDED["pages"][0]["answers"][0])
    assert [q.quote for q in review.quotes] == RECORDED["pages"][0]["answers"][0]["quotes"][:2]
    assert [(d.reason, d.quote) for d in review.dropped] == [
        (
            QuarantineReason.UNGROUNDED_EXCERPT.value,
            "Rostlinné nápoje kupuje polovina všech dospělých lidí",
        )
    ]


def test_a_quote_carrying_numbers_is_grounded_with_its_measures() -> None:
    review = _review(
        _id(1),
        {
            "relevant": True,
            "sub_question": "Q2",
            "quotes": ["Průměrná cena litru dosáhla v roce 2024 v Česku 42 Kč za litr"],
        },
    )
    assert review.dropped == ()
    (quote,) = review.quotes
    lo, hi = quote.span
    assert hi - lo == len(quote.quote)


def test_a_short_quote_is_too_weak_to_hand_off() -> None:
    review = _review(_id(3), {"relevant": True, "sub_question": "Q2", "quotes": ["35 Kč"]})
    assert review.quotes == ()
    assert review.dropped[0].reason == QuarantineReason.UNGROUNDED_EXCERPT.value


def test_a_page_carrying_instructions_hands_off_no_quote() -> None:
    page = BY_ID[_id(4)]
    assert page.instructions_detected
    review = _review(_id(4), RECORDED["pages"][3]["answers"][0])
    assert review.relevant and review.quotes == ()
    assert review.dropped[0].reason == QuarantineReason.SOURCE_CONTAINS_INSTRUCTIONS.value


def test_a_quote_outside_the_part_shown_is_dropped() -> None:
    review = _review(_id(7), RECORDED["pages"][6]["answers"][0])
    assert len(review.quotes) == 1
    assert review.dropped[0].reason == TriageDrop.OUTSIDE_PART.value


def test_an_unknown_sub_question_rejects_the_verdict() -> None:
    review = _review(_id(6), RECORDED["pages"][5]["answers"][0])
    assert not review.relevant and review.sub_question is None
    assert review.rejected == TriageDrop.UNKNOWN_SUB_QUESTION.value
    assert [d.reason for d in review.dropped] == [TriageDrop.UNKNOWN_SUB_QUESTION.value]


def test_the_same_quote_twice_is_kept_once() -> None:
    review = _review(_id(8), RECORDED["pages"][7]["answers"][0])
    assert len(review.quotes) == 1
    assert review.dropped[0].reason == TriageDrop.DUPLICATE_QUOTE.value


# --------------------------------------------------------------------------- #
# The runner, end to end, recorded
# --------------------------------------------------------------------------- #


def test_every_page_is_triaged_in_order_and_only_grounded_quotes_are_handed_off(
    scope: Any,
) -> None:
    transport = RecordedTriage()
    caller = MeteredCaller(_gateway(transport), scope)
    run = _run(caller, limit=3)

    assert [o.snapshot_id for o in run.outcomes] == [p.snapshot_id for p in PAGES]
    statuses = {o.snapshot_id: o.status for o in run.outcomes}
    assert statuses[_id(5)] is TriageStatus.FAILED
    assert all(s is TriageStatus.TRIAGED for k, s in statuses.items() if k != _id(5))
    assert _outcome(run, _id(5)).reason == "structured_output_invalid"

    handed = {o.snapshot_id: [q.quote for q in o.hand_off] for o in run.outcomes}
    assert handed == {
        _id(1): RECORDED["pages"][0]["answers"][0]["quotes"][:2],
        _id(2): [],
        _id(3): RECORDED["pages"][2]["answers"][1]["quotes"],
        _id(4): [],
        _id(5): [],
        _id(6): [],
        _id(7): ["Tato kapitola popisuje metodiku vymyšleného šetření a jeho omezení."],
        _id(8): ["rostlinné nápoje loni kupovalo 45 % domácností v Česku"],
    }
    # Every handed-off quote is in its own snapshot; nothing else reached hand-off.
    for outcome in run.outcomes:
        for quote in outcome.hand_off:
            assert quote.quote.split()[0] in BY_ID[outcome.snapshot_id].text
    assert run.dropped_by_reason == {
        QuarantineReason.SOURCE_CONTAINS_INSTRUCTIONS.value: 1,
        QuarantineReason.UNGROUNDED_EXCERPT.value: 1,
        TriageDrop.DUPLICATE_QUOTE.value: 1,
        TriageDrop.OUTSIDE_PART.value: 1,
        TriageDrop.UNKNOWN_SUB_QUESTION.value: 1,
    }
    assert run.quotes_grounded == 5 and run.quotes_dropped == 5
    assert {o.snapshot_id for o in run.relevant} == {
        _id(1),
        _id(3),
        _id(4),
        _id(7),
        _id(8),
    }
    assert run.stopped == ""


def test_four_quotes_are_refused_and_repaired_once_never_truncated(scope: Any) -> None:
    transport = RecordedTriage()
    caller = MeteredCaller(_gateway(transport), scope)
    run = _run(caller, [BY_ID[_id(3)], BY_ID[_id(5)]], limit=1)

    repaired = _outcome(run, _id(3))
    assert repaired.status is TriageStatus.TRIAGED
    assert [q.quote for q in repaired.hand_off] == RECORDED["pages"][2]["answers"][1]["quotes"]
    assert len(repaired.call_ids) == 2
    # The repair is told why, and the fourth quote never becomes a candidate.
    repair_body = transport.requests[1].body
    assert "quotes" in repair_body["messages"][-1]["content"][0]["text"]

    failed = _outcome(run, _id(5))
    assert failed.status is TriageStatus.FAILED and failed.hand_off == ()
    assert len(failed.call_ids) == 2
    assert caller.calls_per_request == {f"RSV-{_id(3)}": 2, f"RSV-{_id(5)}": 2}


def test_each_page_reserves_once_and_settles_once_with_what_its_calls_cost(scope: Any) -> None:
    transport = RecordedTriage()
    caller = MeteredCaller(_gateway(transport), scope)
    run = _run(caller, limit=4)

    assert sorted(caller.reserved) == sorted(f"RSV-{p.snapshot_id}" for p in PAGES)
    assert set(caller.settled) == set(caller.reserved)
    per_call = (2000 * IN_PRICE + 120 * OUT_PRICE) / 1_000_000
    for outcome in run.outcomes:
        calls = caller.calls_per_request[f"RSV-{outcome.snapshot_id}"]
        assert caller.settled[f"RSV-{outcome.snapshot_id}"] == pytest.approx(calls * per_call)
        assert outcome.cost_usd == pytest.approx(calls * per_call)
    assert run.cost_usd == pytest.approx(sum(caller.settled.values()))
    # Eight pages, two repaired: ten calls, each one sent once.
    assert len(transport.requests) == 10
    assert Counter(transport.pages_sent) == Counter(
        {p.snapshot_id: 2 if p.snapshot_id in {_id(3), _id(5)} else 1 for p in PAGES}
    )


@pytest.mark.parametrize("limit", [1, 2, 3, 5])
def test_the_runner_never_exceeds_its_limit_and_does_reach_it(scope: Any, limit: int) -> None:
    transport = RecordedTriage()
    _run(MeteredCaller(_gateway(transport), scope), limit=limit)
    assert transport.max_in_flight == limit


def test_any_limiter_bounds_the_calls_in_flight(scope: Any) -> None:
    """The runner asks only for a slot: an instrumented limiter sees every send inside one."""

    class Counting:
        def __init__(self, limit: int) -> None:
            self.inner = SemaphoreLimiter(limit)
            self.held = 0
            self.peak = 0
            self.slots = 0

        @asynccontextmanager
        async def slot(self) -> AsyncIterator[None]:
            async with self.inner.slot():
                self.held += 1
                self.slots += 1
                self.peak = max(self.peak, self.held)
                try:
                    yield
                finally:
                    self.held -= 1

    transport = RecordedTriage()
    limiter = Counting(2)
    _run(MeteredCaller(_gateway(transport), scope), limiter=limiter)
    assert limiter.peak == 2 == transport.max_in_flight
    assert limiter.slots == len(PAGES)


def test_results_keep_the_pages_order_whatever_order_answers_arrive_in(scope: Any) -> None:
    pages = [BY_ID[_id(n)] for n in (1, 2, 4)]  # none repaired: one answer each

    async def scenario() -> tuple[TriageRun, list[str]]:
        hold = {p.snapshot_id: asyncio.Event() for p in pages}
        transport = RecordedTriage(hold=hold)
        caller = MeteredCaller(_gateway(transport), scope)
        task = asyncio.create_task(
            triage_pages(
                pages,
                QUESTIONS,
                caller=caller,
                limiter=SemaphoreLimiter(3),
                data_class=DataClass.CLASS_C_INTERNAL,
                lineage=DataLineage.none(),
                policy_version=POLICY,
                max_output_tokens=MAX_OUTPUT,
            )
        )
        for _ in range(1000):  # all three in flight before any answers
            if transport.in_flight == 3:
                break
            await asyncio.sleep(0)
        assert transport.in_flight == 3
        for page in reversed(pages):  # the last page answers first
            hold[page.snapshot_id].set()
            for _ in range(10):
                await asyncio.sleep(0)
        return await task, transport.completed

    run, completed = asyncio.run(scenario())
    assert completed == [_id(4), _id(2), _id(1)]
    assert [o.snapshot_id for o in run.outcomes] == [_id(1), _id(2), _id(4)]


def test_a_refused_capability_sends_nothing_and_reserves_nothing(scope: Any) -> None:
    transport = RecordedTriage()
    caller = MeteredCaller(_gateway(transport, bind_triage=False), scope)
    run = _run(caller)

    assert transport.requests == []
    assert caller.reserved == []
    assert {o.status for o in run.outcomes} == {TriageStatus.REFUSED}
    assert {o.reason for o in run.outcomes} == {"model_resolution_capability_not_configured"}
    assert run.stopped == "refused:model_resolution_capability_not_configured"


def test_a_refused_data_class_sends_nothing(scope: Any) -> None:
    transport = RecordedTriage()
    caller = MeteredCaller(_gateway(transport), scope)
    run = asyncio.run(
        triage_pages(
            PAGES,
            QUESTIONS,
            caller=caller,
            limiter=SemaphoreLimiter(2),
            data_class=DataClass.CLASS_A_CLIENT_CONFIDENTIAL,
            lineage=DataLineage.none(),
            policy_version=POLICY,
            max_output_tokens=MAX_OUTPUT,
        )
    )
    assert transport.requests == [] and caller.reserved == []
    assert {o.status for o in run.outcomes} == {TriageStatus.REFUSED}
    assert all(o.reason.startswith("egress_") for o in run.outcomes)


def test_an_uncertain_answer_stops_new_dispatch_and_is_never_resent(scope: Any) -> None:
    transport = RecordedTriage(uncertain=frozenset({_id(2)}))
    caller = MeteredCaller(_gateway(transport), scope)
    run = _run(caller, limit=1)

    assert _outcome(run, _id(1)).status is TriageStatus.TRIAGED
    assert _outcome(run, _id(2)).status is TriageStatus.UNCERTAIN
    assert {o.status for o in run.outcomes[2:]} == {TriageStatus.NOT_SENT}
    assert transport.pages_sent == [_id(1), _id(2)]
    assert run.stopped == f"uncertain:{_id(2)}"
    # An uncertain call is never settled as known.
    assert f"RSV-{_id(2)}" not in caller.settled
    assert _outcome(run, _id(2)).reason == "provider_transport"


def test_a_stop_from_the_caller_lets_calls_in_flight_finish_and_is_raised(scope: Any) -> None:
    transport = RecordedTriage()
    caller = MeteredCaller(_gateway(transport), scope, stop_on=_id(3))
    with pytest.raises(Stop):
        _run(caller, limit=2)
    # Pages 1 and 2 were in flight or done; page 3 stopped; nothing after it left.
    assert set(transport.pages_sent) <= {_id(1), _id(2)}
    assert set(caller.settled) == {f"RSV-{p}" for p in set(transport.pages_sent)}
    assert _id(4) not in transport.pages_sent


def test_a_page_is_triaged_once_per_run(scope: Any) -> None:
    caller = MeteredCaller(_gateway(RecordedTriage()), scope)
    with pytest.raises(ValueError):
        _run(caller, [PAGES[0], PAGES[0]])


def test_no_pages_is_no_work(scope: Any) -> None:
    run = _run(MeteredCaller(_gateway(RecordedTriage()), scope), [])
    assert run.outcomes == () and run.stopped == ""


# --------------------------------------------------------------------------- #
# A triage reader can send nothing
# --------------------------------------------------------------------------- #


def test_the_only_tool_a_request_offers_is_its_output_contract(scope: Any) -> None:
    transport = RecordedTriage()
    _run(MeteredCaller(_gateway(transport), scope), [BY_ID[_id(1)], BY_ID[_id(2)]])
    for request in transport.requests:
        tools = request.body["toolConfig"]["tools"]
        assert [t["toolSpec"]["name"] for t in tools] == [RECORDED["tool"]]
        assert request.body["toolConfig"]["toolChoice"] == {"tool": {"name": RECORDED["tool"]}}
        schema = tools[0]["toolSpec"]["inputSchema"]["json"]
        assert set(schema["properties"]) == {"relevant", "sub_question", "quotes"}


def _imports(module: Any) -> set[str]:
    tree = ast.parse(Path(module.__file__).read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
            names.update(f"{node.module}.{a.name}" for a in node.names)
        elif isinstance(node, ast.Import):
            names.update(a.name for a in node.names)
    return names


@pytest.mark.parametrize("module", [triage_module, runner_module])
def test_the_triage_modules_reach_no_retrieval_and_no_tool(module: Any) -> None:
    """Structurally: nothing a triage reader runs can search, fetch or meter a tool."""
    forbidden = ("web_retrieval", "web", "tooling", "ai_tools", "robots", "infrastructure")
    for name in _imports(module):
        parts = name.split(".")
        assert not any(f in parts for f in forbidden), name
    source = Path(module.__file__).read_text(encoding="utf-8")
    for token in ("RetrievalGate", "StepToolMeter", "ToolRegistry", "WebFetcher"):
        assert token not in source


def test_the_failure_class_of_a_refusal_is_configuration_not_a_retry(scope: Any) -> None:
    """A refusal is decided before anything is sent: the gateway's own classification."""
    gateway = _gateway(RecordedTriage(), bind_triage=False)
    page = PAGES[0]
    request = triage_request(
        page,
        page_part(page.text),
        QUESTIONS,
        data_class=DataClass.CLASS_C_INTERNAL,
        lineage=DataLineage.none(),
        policy_version=POLICY,
        max_output_tokens=MAX_OUTPUT,
    )
    with pytest.raises(ModelCallFailed) as refused:
        MeteredCaller(gateway, scope).preflight(request)
    assert refused.value.failure is FailureClass.MISSING_CONFIGURATION
    assert not refused.value.paid_call_dispatched
