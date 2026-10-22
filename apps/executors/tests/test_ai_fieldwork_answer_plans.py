"""``AIFieldwork.answer_plans``: plans from any source answered exactly as fieldwork answers them
(panel-grounded-respondents 7e1). No network, no worker: a scripted caller stands in for the
gateway."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from aia_core.domain.ai_contracts import validate_structured_output
from aia_core.domain.ai_respondent import block_contract, fictional_roster, plan_respondent
from aia_core.domain.licence import DataLineage
from aia_core.domain.providers import Provider
from aia_core.domain.research_design import compile_design
from aia_core.domain.residency import DataClass
from aia_core.domain.respondent_behavior import AIA_RESPONSE_V1
from aia_core.infrastructure.build_identity import BuildIdentity
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
        self.progressed.append(counts)


def _setup(
    caller: _Caller, *, design: dict[str, Any] = DESIGN, scale_labels_in_prompt: bool = False
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
    assert context.progressed[-1] == {"respondents": len(plans), "of": len(plans)}


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
