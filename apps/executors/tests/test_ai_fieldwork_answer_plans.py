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


def _setup(caller: _Caller) -> tuple[AIFieldwork, Any, list[Any]]:
    spec, problems = compile_design(DESIGN)
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
