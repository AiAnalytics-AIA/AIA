"""``AIFieldwork.answer_plans``: plans from any source answered exactly as fieldwork answers them
(panel-grounded-respondents 7e1). No network, no worker: a scripted caller stands in for the
gateway."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from aia_core.domain.ai_contracts import ModelCallFailed, validate_structured_output
from aia_core.domain.ai_respondent import block_contract, fictional_roster, plan_respondent
from aia_core.domain.fieldwork_events import (
    FIELDWORK_EVENTS_VERSION,
    PAYLOAD_KEYS,
    FieldworkEvent,
    progress,
    respondent,
)
from aia_core.domain.licence import DataLineage
from aia_core.domain.providers import Provider
from aia_core.domain.research_design import compile_design
from aia_core.domain.residency import DataClass
from aia_core.domain.respondent_behavior import AIA_RESPONSE_V1
from aia_core.domain.workflow import FailureClass
from aia_core.infrastructure.build_identity import BuildIdentity
from aia_executors import ai_fieldwork
from aia_executors.ai_fieldwork import AIFieldwork, AIFieldworkConfig, Answered
from aia_worker.executor import Failed

DESIGN: dict[str, Any] = {
    "title": "Fiktivní plány",
    "n": 6,
    "sections": [
        {
            "type": "questions",
            "questions": [
                {"id": "q1", "text": "Jak často?", "typ": "skala", "skala": [1, 4]},
                {"id": "q2", "text": "Co?", "typ": "vyber", "kategorie": ["A", "B", "C"]},
            ],
        }
    ],
}


class _Caller:
    """Answers every item with all mass on its first option; records what it was asked."""

    def __init__(self, **_: Any) -> None:
        self.requests: list[Any] = []

    def preflight(self, request: Any) -> Any:
        return SimpleNamespace(route_id="route-x", model="model-x")

    def invoke(self, request: Any) -> Any:
        self.requests.append(request)
        return SimpleNamespace(
            output=self.output_for(request),
            call_id=f"c{len(self.requests)}",
            provider_request_id="p",
            resolved_model="model-x",
            provenance=SimpleNamespace(
                route_id="route-x", policy_version="v", schema_fingerprint="s"
            ),
            total_cost_usd=0.001,
            cost_basis=SimpleNamespace(value="estimated"),
            usage_events=(SimpleNamespace(call_id=f"c{len(self.requests)}"),),
        )

    output_for: Any = None


class _Context:
    def __init__(self) -> None:
        self.checkpoints = 0
        self.progressed: list[dict[str, Any]] = []

    def checkpoint(self) -> None:
        self.checkpoints += 1

    def progress(self, message: str, **counts: Any) -> None:
        self.progressed.append({"message": message, **counts})


def _setup(
    caller: _Caller,
    *,
    design: dict[str, Any] = DESIGN,
    scale_labels_in_prompt: bool = False,
    heartbeat: bool = False,
    respondent_events: bool = False,
) -> tuple[AIFieldwork, Any, list[Any]]:
    spec, problems = compile_design(design)
    assert spec is not None, problems
    personas = fictional_roster(6, seed=1)
    plans = [plan_respondent(spec, p) for p in personas]

    def output_for(request: Any) -> Any:
        block = next(p.blocks[0] for p in plans if p.blocks)
        payload = {
            item.item_id: {"probabilities": [1.0] + [0.0] * (item.width - 1)}
            for item in block.items
        }
        checked = validate_structured_output(block_contract(block), structured=payload, text="")
        assert checked.ok, checked.violations
        return checked.value

    caller.output_for = output_for
    fieldwork = AIFieldwork(
        gateway=None,  # type: ignore[arg-type]
        config=AIFieldworkConfig(
            policy_version="test",
            provider=Provider.AWS_BEDROCK,
            reservation_usd=0.01,
            max_output_tokens=1000,
            fictional_client_ids=frozenset(),
            scale_labels_in_prompt=scale_labels_in_prompt,
            heartbeat=heartbeat,
            respondent_events=respondent_events,
        ),
        build=BuildIdentity(sha="abc"),
        caller_factory=lambda **_: caller,
    )
    return fieldwork, spec, plans


def test_plans_from_elsewhere_are_answered_block_by_block_and_drawn_by_code() -> None:
    caller = _Caller()
    fieldwork, spec, plans = _setup(caller)
    context = _Context()
    answered = fieldwork.answer_plans(
        plans,
        spec,
        context,  # type: ignore[arg-type]
        seed=7,
        response=AIA_RESPONSE_V1,
        data_class=DataClass.CLASS_C_INTERNAL,
        lineage=DataLineage(datasets=frozenset({"synthetic"})),
    )
    assert isinstance(answered, Answered)
    assert len(answered.rows) == len(plans) == context.checkpoints
    assert len(caller.requests) == sum(len(p.blocks) for p in plans)
    assert answered.resolution.route_id == "route-x"
    assert len(answered.calls) == len(caller.requests)
    assert {c["respondent_id"] for c in answered.calls} == {p.persona.persona_id for p in plans}
    for _, answers in answered.rows:
        assert set(answers) >= {"q1", "q2"}
    # The fieldwork event contract (RQC7): the last report counts every respondent and block.
    assert context.progressed[-1] == {
        "message": FieldworkEvent.PROGRESS,
        **progress(respondents=len(plans), of=len(plans), sent=len(caller.requests), replayed=0),
    }


def test_each_draw_is_recorded_beside_the_answers_it_gave() -> None:
    caller = _Caller()
    fieldwork, spec, plans = _setup(caller)
    answered = fieldwork.answer_plans(
        plans,
        spec,
        _Context(),  # type: ignore[arg-type]
        seed=7,
        response=AIA_RESPONSE_V1,
        data_class=DataClass.CLASS_C_INTERNAL,
        lineage=DataLineage(datasets=frozenset({"synthetic"})),
    )
    assert isinstance(answered, Answered)
    assert len(answered.details) == len(answered.rows)
    for detail in answered.details:
        assert len(detail["q2"]["probabilities"]) == 3


def test_answers_from_another_binding_than_required_fail_before_any_request() -> None:
    caller = _Caller()
    fieldwork, spec, plans = _setup(caller)
    kwargs: dict[str, Any] = {
        "seed": 7,
        "response": AIA_RESPONSE_V1,
        "data_class": DataClass.CLASS_C_INTERNAL,
        "lineage": DataLineage(datasets=frozenset({"synthetic"})),
    }
    refused = fieldwork.answer_plans(
        plans,
        spec,
        _Context(),  # type: ignore[arg-type]
        require_binding="aws_bedrock/another-model/route-x",
        **kwargs,
    )
    assert isinstance(refused, Failed)
    assert refused.error["reason"] == "model_binding_changed"
    assert refused.error["resolved"] == "aws_bedrock/model-x/route-x"
    assert caller.requests == []
    same = fieldwork.answer_plans(
        plans,
        spec,
        _Context(),  # type: ignore[arg-type]
        require_binding="aws_bedrock/model-x/route-x",
        **kwargs,
    )
    assert isinstance(same, Answered) and caller.requests


_LABELLED: dict[str, Any] = {
    **DESIGN,
    "sections": [
        {
            "type": "questions",
            "questions": [
                {**DESIGN["sections"][0]["questions"][0], "popisky_skaly": ["nikdy", "denně"]},
                DESIGN["sections"][0]["questions"][1],
            ],
        }
    ],
}


def _asked(*, scale_labels_in_prompt: bool, override: bool | None = None) -> str:
    caller = _Caller()
    fieldwork, spec, plans = _setup(
        caller, design=_LABELLED, scale_labels_in_prompt=scale_labels_in_prompt
    )
    answered = fieldwork.answer_plans(
        plans,
        spec,
        _Context(),  # type: ignore[arg-type]
        seed=7,
        response=AIA_RESPONSE_V1,
        data_class=DataClass.CLASS_C_INTERNAL,
        lineage=DataLineage(datasets=frozenset({"synthetic"})),
        scale_labels_in_prompt=override,
    )
    assert isinstance(answered, Answered)
    text = "\n".join(r.messages[0].content for r in caller.requests)
    # What is recorded is what was sent: the value used, never the switch read again.
    assert answered.scale_labels_in_prompt is ("nikdy" in text)
    return text


def test_a_scale_questions_labels_are_sent_only_with_the_switch_on() -> None:
    """input-interactions 3b: AIA_AI_SCALE_LABELS_IN_PROMPT decides; a validation's arms ask the
    system they preregistered, so they override it."""
    assert "Škála 1 až 4 (1 = nikdy, 4 = denně)." in _asked(scale_labels_in_prompt=True)
    off = _asked(scale_labels_in_prompt=False)
    assert "Škála 1 až 4. " in off and "nikdy" not in off
    assert "nikdy" not in _asked(scale_labels_in_prompt=True, override=False)


class _Journal:
    """A lineage's kept answers in memory, as ``_RunJournal`` keeps them (RQC0)."""

    def __init__(self, entries: dict[str, dict[str, Any]] | None = None) -> None:
        self.entries = dict(entries or {})
        self.override: dict[str, Any] | None = None

    def kept(self) -> dict[str, dict[str, Any]]:
        return dict(self.entries)

    def put(self, key: str, payload: dict[str, Any]) -> dict[str, Any]:
        if self.override is not None:  # an earlier, raced answer is what is kept
            payload = {**payload, "output": self.override}
        return self.entries.setdefault(key, payload)


class _RunContext(_Context):
    def __init__(self, run_id: str) -> None:
        super().__init__()
        self.step = SimpleNamespace(run_id=run_id)


def _answer(
    fieldwork: AIFieldwork, spec: Any, plans: list[Any], journal: _Journal, run_id: str
) -> Any:
    return fieldwork.answer_plans(
        plans,
        spec,
        _RunContext(run_id),  # type: ignore[arg-type]
        seed=7,
        response=AIA_RESPONSE_V1,
        data_class=DataClass.CLASS_C_INTERNAL,
        lineage=DataLineage(datasets=frozenset({"synthetic"})),
        journal=journal,  # type: ignore[arg-type]
    )


def test_a_kept_answer_is_replayed_unsent_and_names_the_run_that_paid() -> None:
    journal = _Journal()
    first = _Caller()
    fieldwork, spec, plans = _setup(first)
    paid = _answer(fieldwork, spec, plans, journal, "RUN-1")
    assert isinstance(paid, Answered) and len(journal.entries) == len(first.requests) > 0

    again = _Caller()
    fieldwork, spec, plans = _setup(again)
    replayed = _answer(fieldwork, spec, plans, journal, "RUN-2")
    assert isinstance(replayed, Answered)
    assert again.requests == []
    assert replayed.rows == paid.rows, "the same outputs draw the same answers"
    assert {c["replayed_from_run"] for c in replayed.calls} == {"RUN-1"}
    assert all(c["cost_usd"] == 0.0 and c["calls"] == 0 for c in replayed.calls)


def test_another_model_or_route_asks_again_rather_than_replay() -> None:
    journal = _Journal()
    fieldwork, spec, plans = _setup(_Caller())
    _answer(fieldwork, spec, plans, journal, "RUN-1")
    other = _Caller()
    other.preflight = lambda request: SimpleNamespace(route_id="route-y", model="model-y")  # type: ignore[method-assign]
    fieldwork, spec, plans = _setup(other)
    _answer(fieldwork, spec, plans, journal, "RUN-2")
    assert len(other.requests) == sum(len(p.blocks) for p in plans)


def test_an_output_the_draw_refuses_is_never_kept() -> None:
    journal = _Journal()
    caller = _Caller()
    fieldwork, spec, plans = _setup(caller)
    valid = caller.output_for
    # The first answer has an item with no probability mass: the attempt fails on it.
    caller.output_for = lambda request: valid(request).model_copy(
        update={"item_0": valid(request).item_0.model_copy(update={"probabilities": [0.0] * 4})}
    )
    assert isinstance(_answer(fieldwork, spec, plans, journal, "RUN-1"), Failed)
    assert journal.entries == {}


def test_a_raced_answer_kept_first_is_the_one_drawn_from() -> None:
    journal = _Journal()
    caller = _Caller()
    fieldwork, spec, plans = _setup(caller)
    # Another attempt kept an answer with all mass on the last option of every item.
    block = next(p.blocks[0] for p in plans if p.blocks)
    journal.override = {
        item.item_id: {"probabilities": [0.0] * (item.width - 1) + [1.0]} for item in block.items
    }
    answered = _answer(fieldwork, spec, plans, journal, "RUN-1")
    assert isinstance(answered, Answered)
    fresh = _answer(*_setup(_Caller()), _Journal(), "RUN-9")
    assert answered.rows != fresh.rows, "the kept answer, not this attempt's own, drew the rows"


def test_a_replay_names_the_respondent_answered_now_when_two_sent_the_same_request() -> None:
    from dataclasses import replace

    journal = _Journal()
    caller = _Caller()
    fieldwork, spec, plans = _setup(caller)
    first = next(p for p in plans if p.blocks)
    # Two respondents whose blocks are byte for byte the same: only their ids differ.
    twins = [first, replace(first, persona=first.persona.model_copy(update={"persona_id": "TWIN"}))]
    _answer(fieldwork, spec, twins, journal, "RUN-1")
    assert len(journal.entries) == len(first.blocks), "the twins share each block's key"

    fieldwork, spec, _ = _setup(_Caller())
    replayed = _answer(fieldwork, spec, twins, journal, "RUN-2")
    assert isinstance(replayed, Answered)
    assert [c["respondent_id"] for c in replayed.calls] == [
        p.persona.persona_id for p in twins for _ in p.blocks
    ]
    assert [c["block"] for c in replayed.calls] == [b.index for p in twins for b in p.blocks]


def _plain(fieldwork: AIFieldwork, spec: Any, plans: list[Any], context: Any) -> Any:
    return fieldwork.answer_plans(
        plans,
        spec,
        context,
        seed=7,
        response=AIA_RESPONSE_V1,
        data_class=DataClass.CLASS_C_INTERNAL,
        lineage=DataLineage(datasets=frozenset({"synthetic"})),
    )


def test_a_replayed_run_reports_its_blocks_replayed_not_sent() -> None:
    journal = _Journal()
    fieldwork, spec, plans = _setup(_Caller())
    _answer(fieldwork, spec, plans, journal, "RUN-1")
    fieldwork, spec, plans = _setup(_Caller())
    context = _RunContext("RUN-2")
    fieldwork.answer_plans(
        plans,
        spec,
        context,  # type: ignore[arg-type]
        seed=7,
        response=AIA_RESPONSE_V1,
        data_class=DataClass.CLASS_C_INTERNAL,
        lineage=DataLineage(datasets=frozenset({"synthetic"})),
        journal=journal,  # type: ignore[arg-type]
    )
    last = context.progressed[-1]
    assert (last["sent"], last["replayed"]) == (0, sum(len(p.blocks) for p in plans))


def _slow(monkeypatch: Any) -> None:
    """Every read of the clock is 31 s after the last: each block takes longer than a heartbeat."""
    ticks = iter(range(0, 100_000, 31))
    monkeypatch.setattr(ai_fieldwork, "monotonic", lambda: float(next(ticks)))


def test_without_the_switch_a_slow_model_reports_only_every_few_respondents(
    monkeypatch: Any,
) -> None:
    _slow(monkeypatch)
    fieldwork, spec, plans = _setup(_Caller())
    context = _Context()
    _plain(fieldwork, spec, plans, context)
    assert [e["respondents"] for e in context.progressed] == [len(plans)]


#: Ten closed questions: two blocks a respondent (MAX_BLOCK_ITEMS is 8).
TWO_BLOCKS: dict[str, Any] = {
    **DESIGN,
    "sections": [
        {
            "type": "questions",
            "questions": [
                {"id": f"q{i}", "text": f"Otázka {i}?", "typ": "skala", "skala": [1, 4]}
                for i in range(1, 11)
            ],
        }
    ],
}


def test_a_slow_model_still_reports_a_heartbeat(monkeypatch: Any) -> None:
    _slow(monkeypatch)
    caller = _Caller()
    fieldwork, spec, plans = _setup(caller, design=TWO_BLOCKS, heartbeat=True)
    assert all(len(p.blocks) == 2 for p in plans)
    # A fresh run sends every block in order: answer each with its own block's shape.
    order = [b for p in plans for b in p.blocks]

    def output_for(request: Any) -> Any:
        block = order[len(caller.requests) - 1]
        payload = {
            item.item_id: {"probabilities": [1.0] + [0.0] * (item.width - 1)}
            for item in block.items
        }
        return validate_structured_output(block_contract(block), structured=payload, text="").value

    caller.output_for = output_for
    context = _Context()
    _plain(fieldwork, spec, plans, context)
    reports = [e for e in context.progressed if e["message"] == FieldworkEvent.PROGRESS]
    # Between a respondent's two blocks the heartbeat reports those answered so far; once the
    # respondent is answered, it is counted at once, never a respondent behind.
    assert [r["respondents"] for r in reports] == [n for i in range(len(plans)) for n in (i, i + 1)]
    for report in reports:
        assert set(report) - {"message"} == set(PAYLOAD_KEYS[FieldworkEvent.PROGRESS])
    # Counts only grow, and the heartbeat never claims a respondent not yet answered.
    assert [r["respondents"] for r in reports] == sorted(r["respondents"] for r in reports)
    assert reports[-1]["respondents"] == len(plans)


def test_a_park_writes_no_progress_and_returns_its_reason() -> None:
    """Why the step stopped reaches the feed through the engine's STEP_RECOVERY (RQC7a)."""

    class Refusing(_Caller):
        def preflight(self, request: Any) -> Any:
            raise ModelCallFailed(
                "route closed",
                failure=FailureClass.RUNTIME_UNAVAILABLE,
                reason="egress_route_not_approved_for_class",
            )

    caller = Refusing()
    fieldwork, spec, plans = _setup(caller)
    context = _Context()
    parked = _plain(fieldwork, spec, plans, context)
    assert isinstance(parked, Failed) and caller.requests == []
    assert parked.error["reason"] == "egress_route_not_approved_for_class"
    assert context.progressed == []


def _respondents(context: _Context) -> list[dict[str, Any]]:
    return [e for e in context.progressed if e["message"] == FieldworkEvent.RESPONDENT]


def test_each_respondent_names_its_cell_and_its_blocks_with_the_switch_on() -> None:
    """RQC7b: one ``fieldwork_respondent`` per respondent, in order, with the cell it was given."""
    from aia_core.domain.population.sampling import QuotaCell

    journal = _Journal()
    caller = _Caller()
    fieldwork, spec, plans = _setup(caller, respondent_events=True)
    # A panel sample's cells as the sampler names them (one allotted none), and each respondent's.
    quota_cells = (
        QuotaCell(("žena", "18-29"), 3),
        QuotaCell(("muž", "65"), 0),
        QuotaCell(("muž", "30-44"), 3),
    )
    at = [0, 2, 2, 0, 0, 2]
    quota = SimpleNamespace(
        quota_cells=quota_cells,
        audit=SimpleNamespace(quota_fields=("pohlavi", "vek")),
        respondents=tuple(SimpleNamespace(quota_cell=i) for i in at),
    )
    keys = ["zena/18-29", "muz/65", "muz/30-44"]
    cells = [keys[i] for i in at]
    context = _RunContext("RUN-1")
    fieldwork.answer_plans(
        plans,
        spec,
        context,  # type: ignore[arg-type]
        seed=7,
        response=AIA_RESPONSE_V1,
        data_class=DataClass.CLASS_C_INTERNAL,
        lineage=DataLineage(datasets=frozenset({"synthetic"})),
        journal=journal,  # type: ignore[arg-type]
        quota=quota,  # type: ignore[arg-type]
    )
    # The cells once, before the first respondent, without the one allotted none.
    assert context.progressed[0] == {
        "message": FieldworkEvent.SAMPLE,
        "version": FIELDWORK_EVENTS_VERSION,
        "quota_fields": ["pohlavi", "vek"],
        "cells": [
            {"key": "zena/18-29", "values": ["žena", "18-29"], "n": 3},
            {"key": "muz/30-44", "values": ["muž", "30-44"], "n": 3},
        ],
    }
    assert [e["message"] for e in context.progressed].count(FieldworkEvent.SAMPLE) == 1
    rows = _respondents(context)
    assert rows == [
        {
            "message": FieldworkEvent.RESPONDENT,
            **respondent(respondent=i + 1, cell=cells[i], sent=len(p.blocks), replayed=0),
        }
        for i, p in enumerate(plans)
    ]
    for row in rows:
        assert set(row) - {"message"} == set(PAYLOAD_KEYS[FieldworkEvent.RESPONDENT])
    # Each row is written once its respondent is answered: before the progress that counts it.
    progress_at = next(
        i for i, e in enumerate(context.progressed) if e["message"] == FieldworkEvent.PROGRESS
    )
    assert context.progressed[progress_at - 1]["respondent"] == len(plans)

    # Run again over the journal: every block replayed, none sent, each in its cell.
    fieldwork, spec, plans = _setup(_Caller(), respondent_events=True)
    again = _RunContext("RUN-2")
    _answer_into(fieldwork, spec, plans, journal, again, quota=quota)
    assert [(r["cell"], r["sent"], r["replayed"]) for r in _respondents(again)] == [
        (cells[i], 0, len(p.blocks)) for i, p in enumerate(plans)
    ]
    # Without a panel sample (the roster, a validation's arms) no cell and no row is written.
    fieldwork, spec, plans = _setup(_Caller(), respondent_events=True)
    roster = _RunContext("RUN-3")
    _answer_into(fieldwork, spec, plans, _Journal(), roster)
    assert {e["message"] for e in roster.progressed} == {FieldworkEvent.PROGRESS}


def test_a_park_writes_no_cells() -> None:
    """The cells follow the preflight: a run the gateway refuses writes nothing (RQC7b)."""
    from aia_core.domain.population.sampling import QuotaCell

    class Refusing(_Caller):
        def preflight(self, request: Any) -> Any:
            raise ModelCallFailed(
                "route closed",
                failure=FailureClass.RUNTIME_UNAVAILABLE,
                reason="egress_route_not_approved_for_class",
            )

    fieldwork, spec, plans = _setup(Refusing(), respondent_events=True)
    context = _RunContext("RUN-1")
    quota = SimpleNamespace(
        quota_cells=(QuotaCell(("žena",), 6),),
        audit=SimpleNamespace(quota_fields=("pohlavi",)),
        respondents=tuple(SimpleNamespace(quota_cell=0) for _ in plans),
    )
    parked = _answer_into(fieldwork, spec, plans, _Journal(), context, quota=quota)
    assert isinstance(parked, Failed) and context.progressed == []


def test_without_the_switch_no_respondent_is_written() -> None:
    fieldwork, spec, plans = _setup(_Caller())
    context = _Context()
    _plain(fieldwork, spec, plans, context)
    assert _respondents(context) == []
    assert {e["message"] for e in context.progressed} == {FieldworkEvent.PROGRESS}


def _answer_into(
    fieldwork: AIFieldwork,
    spec: Any,
    plans: list[Any],
    journal: _Journal,
    context: Any,
    quota: Any = None,
) -> Any:
    return fieldwork.answer_plans(
        plans,
        spec,
        context,
        seed=7,
        response=AIA_RESPONSE_V1,
        data_class=DataClass.CLASS_C_INTERNAL,
        lineage=DataLineage(datasets=frozenset({"synthetic"})),
        journal=journal,  # type: ignore[arg-type]
        quota=quota,
    )
