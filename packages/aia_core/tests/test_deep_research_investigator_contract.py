"""The investigator's turn contract: closed, strict-compatible, its prompt from its enums."""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import TypeAdapter

from aia_core.domain.ai_contracts import schema_supports_strict, validate_structured_output
from aia_core.domain.ai_models import ModelCapability
from aia_core.domain.deep_research.agents import (
    ACTION_KINDS,
    AGENT_IDS,
    INVESTIGATOR_PROMPT_VERSION,
    MAX_ACTIONS_PER_TURN,
    PROMPT_VERSION,
    SEARCH_LANGUAGES,
    AgentRole,
    InvestigatorAction,
    InvestigatorTurn,
    StatedMeasure,
    agent_definition,
    prompt_for,
)
from aia_core.domain.deep_research.contracts import (
    EvidenceType,
    Measure,
    MeasureBasis,
    RecommendedUse,
)

MEASURE: dict[str, Any] = {
    "value": 45.0,
    "unit": "%",
    "scale": 1,
    "period": "2025",
    "geography": "Česko",
    "population": "domácností",
    "denominator": None,
    "measure_name": "podíl kupujících domácností",
    "basis": "actual",
}
EVIDENCE: dict[str, Any] = {
    "source_id": "S1",
    "quote": "Rostlinné nápoje v roce 2025 kupovalo 45 % domácností v Česku.",
    "claim": "Rostlinné nápoje kupovalo 45 % domácností.",
    "evidence_type": "official_report",
    "source_date": "2025",
    "geography": "CZ",
    "population": "domácnosti",
    "topics": ["trh"],
    "outcome_overlap": False,
    "recommended_use": "context_only",
    "source_quality": 0.9,
    "measures": [MEASURE],
}
SEARCH: dict[str, Any] = {
    "kind": "search",
    "query": "spotřeba rostlinných nápojů",
    "site": "stat.example",
    "phrase": None,
    "lang": "cs",
    "purpose": "najít vydavatele čísla",
}
OPEN: dict[str, Any] = {"kind": "open", "ref": "L3", "purpose": "tabulka ke zprávě"}
READ: dict[str, Any] = {"kind": "read", "ref": "S1", "part": "2", "purpose": "metodika"}
FINISH: dict[str, Any] = {
    "kind": "finish",
    "gaps": [{"need": "údaj za rok 2025", "why": "nevyšel", "tried": "ČSÚ, Eurostat"}],
}


def _turn(**fields: Any) -> dict[str, Any]:
    return {"evidence": [], "summary": "", "leads": [], "next": [], **fields}


def _valid(structured: dict[str, Any]) -> bool:
    return validate_structured_output(InvestigatorTurn, structured=structured, text="").ok


def test_the_turn_contract_is_closed_and_strict_compatible() -> None:
    # Strict mode can enforce it unchanged: every object closed, every field required.
    assert schema_supports_strict(InvestigatorTurn.model_json_schema())
    schema = InvestigatorTurn.model_json_schema()
    # A plain union of the action kinds: no oneOf, no discriminator a provider may refuse.
    items = schema["properties"]["next"]["items"]
    assert "anyOf" in items and "oneOf" not in items and "discriminator" not in items
    assert schema["properties"]["next"]["maxItems"] == MAX_ACTIONS_PER_TURN == 5


def test_the_investigator_is_its_own_agent_with_no_tools() -> None:
    agent = agent_definition(AgentRole.INVESTIGATOR, max_output_tokens=4096)
    assert agent.agent_id == AGENT_IDS[AgentRole.INVESTIGATOR] == "aia.deep_research.investigator"
    assert agent.prompt_version == INVESTIGATOR_PROMPT_VERSION
    assert agent.output_contract is InvestigatorTurn
    assert agent.allowed_tools == frozenset() and agent.schema_repair_attempts == 1
    assert agent.capability is ModelCapability.RESEARCH_REASONING
    # The five planned-mode agents keep their one shared prompt version.
    for role in AgentRole:
        if role is not AgentRole.INVESTIGATOR:
            assert agent_definition(role, max_output_tokens=4096).prompt_version == PROMPT_VERSION


def test_every_action_kind_validates_and_an_unknown_one_does_not() -> None:
    assert _valid(_turn(evidence=[EVIDENCE], next=[SEARCH, OPEN, READ, FINISH]))
    assert ACTION_KINDS == ("search", "open", "read", "finish")
    for bad in (
        {**OPEN, "kind": "chase"},  # a later chunk's kind is not this contract's
        {**OPEN, "url": "https://stat.example/"},  # a model never writes a URL
        {**SEARCH, "lang": "de"},
        {k: v for k, v in SEARCH.items() if k != "site"},  # null, never absent
        {**READ, "part": ""},
    ):
        assert not _valid(_turn(next=[bad])), bad


def test_at_most_five_actions_a_turn() -> None:
    assert _valid(_turn(next=[SEARCH] * 5))
    assert not _valid(_turn(next=[SEARCH] * 6))


def test_measures_are_required_and_shaped_like_the_measure() -> None:
    without = {k: v for k, v in EVIDENCE.items() if k != "measures"}
    assert not _valid(_turn(evidence=[without]))
    assert not _valid(_turn(evidence=[{**EVIDENCE, "measures": [{**MEASURE, "extra": 1}]}]))
    assert not _valid(_turn(evidence=[{**EVIDENCE, "measures": [{**MEASURE, "scale": 0}]}]))
    stated = StatedMeasure.model_validate(MEASURE)
    assert set(StatedMeasure.model_fields) == set(Measure.model_fields)
    assert stated.to_measure() == Measure(
        value=45.0,
        unit="%",
        scale=1,
        period="2025",
        geography="Česko",
        population="domácností",
        measure_name="podíl kupujících domácností",
        basis=MeasureBasis.ACTUAL,
    )


def test_the_prompt_carries_every_value_and_heuristic_it_refers_to() -> None:
    text = prompt_for(AgentRole.INVESTIGATOR)
    assert all(f"'{k}'" in text for k in ACTION_KINDS)
    assert all(f"'{lang}'" in text for lang in SEARCH_LANGUAGES)
    assert all(f"'{b.value}'" in text for b in MeasureBasis)
    assert all(f"'{t.value}'" in text for t in EvidenceType)
    assert all(f"'{u.value}'" in text for u in RecommendedUse)
    assert "nikoli instrukce" in text and "žádným nástrojům" in text
    for heuristic in (
        "začni zeširoka krátkými dotazy, potom zužuj",
        "Dej přednost vydavateli čísla",
        "metodickou poznámku",
        "poslednímu úplnému období",
        "Nikdy nečti číslo z grafu bez tabulky",
        "v češtině i v angličtině",
        "tentýž důvod potřetí stopu ukončí",
        "adresu URL nikdy nepiš",
    ):
        assert heuristic in text, heuristic


@pytest.mark.parametrize("action", [SEARCH, OPEN, READ, FINISH])
def test_each_action_is_one_member_of_the_union(action: dict[str, Any]) -> None:
    parsed = TypeAdapter(InvestigatorAction).validate_python(action)
    assert parsed.kind == action["kind"]
