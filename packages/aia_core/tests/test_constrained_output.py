"""Every contract's schema reduced for Bedrock's grammar (brief-analysis-schema-repair chunk 4a).

The golden fixture pins each agent contract's verdict and the SHA-256 of its reduced schema, so a
contract change that moves what the grammar is sent is seen in review. Rewrite it with
``python packages/aia_core/tests/test_constrained_output.py --write``.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any

import pytest
from pydantic import BaseModel, ConfigDict, Field

from aia_core.domain.ai_contracts import canonical_json, output_schema, validate_structured_output
from aia_core.domain.ai_respondent import Block, Item, block_contract
from aia_core.domain.analysis.harness import AnalysisDraft
from aia_core.domain.constrained_output import (
    MAX_OPTIONAL_PROPERTIES,
    MAX_UNION_PROPERTIES,
    reduce_for_grammar,
)
from aia_core.domain.deep_research import agents as deep_research_agents
from aia_core.domain.deep_research.triage import TriageVerdict
from aia_core.domain.research_agents import CONTRACTS, BriefAnalysis
from aia_core.domain.research_lead import LeadOutput, lead_contract
from aia_core.domain.source_proposals import SourceProposals

FIXTURE = Path(__file__).parent / "fixtures" / "constrained_output" / "contracts.json"


def _contracts() -> dict[str, type[BaseModel]]:
    found: dict[str, type[BaseModel]] = {f"research:{a.value}": c for a, c in CONTRACTS.items()}
    found.update(
        {
            "analysis": AnalysisDraft,
            "client_source_proposals": SourceProposals,
            "deep_research:triage": TriageVerdict,
            "study_lead": LeadOutput,
        }
    )
    for role, contract in deep_research_agents._CONTRACTS.items():
        found[f"deep_research:{role.value}"] = contract
    return found


def _verdicts() -> dict[str, dict[str, str | None]]:
    verdicts: dict[str, dict[str, str | None]] = {}
    for key, contract in sorted(_contracts().items()):
        reduced = reduce_for_grammar(output_schema(contract))
        verdicts[key] = {
            "refusal": reduced.refusal,
            "sha256": None
            if reduced.schema is None
            else hashlib.sha256(canonical_json(reduced.schema).encode()).hexdigest(),
        }
    return verdicts


def test_every_contracts_verdict_and_reduced_schema_is_pinned() -> None:
    assert _verdicts() == json.loads(FIXTURE.read_text())


def test_twenty_of_the_twenty_two_contracts_reduce_and_the_lead_and_investigator_do_not() -> None:
    verdicts = _verdicts()
    refused = {k: v["refusal"] for k, v in verdicts.items() if v["refusal"] is not None}
    assert len(verdicts) == 22
    assert refused == {
        "study_lead": "keyword:discriminator",
        "deep_research:investigator": "union_properties:18>16",
    }


class _Bounded(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=5)
    tags: list[str] = Field(min_length=2, max_length=4)
    pair: tuple[str, str]
    score: int = Field(ge=1, le=10)


def test_bounds_are_dropped_and_a_tuple_is_sent_as_an_array_of_its_items() -> None:
    reduced = reduce_for_grammar(output_schema(_Bounded)).schema
    assert reduced is not None
    props = reduced["properties"]
    assert props["name"] == {"title": "Name", "type": "string"}
    assert props["tags"] == {"items": {"type": "string"}, "title": "Tags", "type": "array"}
    assert props["pair"] == {"items": {"type": "string"}, "title": "Pair", "type": "array"}
    assert props["score"] == {"title": "Score", "type": "integer"}
    assert reduced["additionalProperties"] is False


def test_what_the_grammar_no_longer_holds_the_contract_still_refuses() -> None:
    too_long = {"name": "abcdefgh", "tags": ["a"], "pair": ["a", "b", "c"], "score": 99}
    verdict = validate_structured_output(_Bounded, structured=too_long, text="")
    assert not verdict.ok
    assert {v.split(":")[0] for v in verdict.violations} == {"name", "tags", "pair", "score"}


class _Open(BaseModel):
    model_config = ConfigDict(extra="forbid")
    counts: dict[str, int]


class _Node(BaseModel):
    model_config = ConfigDict(extra="forbid")
    children: list[_Node]


@pytest.mark.parametrize(
    ("contract", "refusal"),
    [
        (_Open, "open_object"),
        (_Node, "recursive"),
    ],
)
def test_what_the_grammar_cannot_express_is_refused_by_name(
    contract: type[BaseModel], refusal: str
) -> None:
    reduced = reduce_for_grammar(output_schema(contract))
    assert (reduced.schema, reduced.refusal) == (None, refusal)


def test_a_pattern_with_lookaround_or_a_backreference_is_refused() -> None:
    def with_pattern(pattern: str) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {"code": {"type": "string", "pattern": pattern}},
            "required": ["code"],
            "additionalProperties": False,
        }

    assert reduce_for_grammar(with_pattern(r"^(?!x)\w+$")).refusal == "pattern"
    assert reduce_for_grammar(with_pattern(r"^(a)\1$")).refusal == "pattern"
    assert reduce_for_grammar(with_pattern(r"^T[1-9][0-9]{0,2}$")).schema is not None


def test_an_unknown_keyword_is_refused_never_passed_on() -> None:
    reduced = reduce_for_grammar(
        {"type": "object", "properties": {}, "additionalProperties": False, "oneOf": []}
    )
    assert reduced.refusal == "keyword:oneOf"


def test_the_limits_on_optional_and_union_properties_hold() -> None:
    def schema(optional: int, unions: int) -> dict[str, Any]:
        props: dict[str, Any] = {f"o{i}": {"type": "string"} for i in range(optional)}
        props |= {f"u{i}": {"anyOf": [{"type": "string"}, {"type": "null"}]} for i in range(unions)}
        required = [k for k in props if k.startswith("u")]
        return {
            "type": "object",
            "properties": props,
            "required": required,
            "additionalProperties": False,
        }

    assert reduce_for_grammar(schema(MAX_OPTIONAL_PROPERTIES, 0)).schema is not None
    assert reduce_for_grammar(schema(MAX_OPTIONAL_PROPERTIES + 1, 0)).refusal == (
        "optional_properties:13>12"
    )
    assert reduce_for_grammar(schema(0, MAX_UNION_PROPERTIES)).schema is not None
    assert reduce_for_grammar(schema(0, MAX_UNION_PROPERTIES + 1)).refusal == (
        "union_properties:17>16"
    )


def test_the_contract_itself_is_never_changed() -> None:
    before = output_schema(BriefAnalysis)
    reduce_for_grammar(before)
    assert before == output_schema(BriefAnalysis)


def _object(props: dict[str, Any], **extra: Any) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": props,
        "required": list(props),
        "additionalProperties": False,
        **extra,
    }


@pytest.mark.parametrize(
    ("schema", "refusal"),
    [
        (_object({"x": {"type": ["object", "null"]}}), "open_object"),
        (_object({"x": {"type": "array", "prefixItems": []}}), "empty_tuple"),
        (_object({"x": {"$ref": "#/$defs/Missing"}}), "dangling_ref"),
        (
            _object(
                {"x": {"$ref": "#/$defs/A"}},
                **{"$defs": {"A": _object({"y": {"$ref": "#/$defs/Missing"}})}},
            ),
            "dangling_ref",
        ),
        (_object({"x": {"$ref": "#/properties/y"}, "y": {"type": "string"}}), "ref_outside_defs"),
        (_object({"x": {"type": "string", "pattern": "(?P<n>a)(?P=n)"}}), "pattern"),
        (_object({"x": {"type": "string", "pattern": "a{1000}"}}), "pattern"),
        (_object({"x": {"type": "string", "pattern": "a{100,}"}}), "pattern"),
    ],
)
def test_every_edge_the_grammar_cannot_take_is_refused(
    schema: dict[str, Any], refusal: str
) -> None:
    assert reduce_for_grammar(schema).refusal == refusal


def test_a_definition_counts_each_time_it_is_referenced() -> None:
    five_optional = {
        "type": "object",
        "properties": {f"o{i}": {"type": "string"} for i in range(5)},
        "additionalProperties": False,
    }
    schema = _object(
        {f"use{i}": {"$ref": "#/$defs/D"} for i in range(3)}, **{"$defs": {"D": five_optional}}
    )
    assert reduce_for_grammar(schema).refusal == "optional_properties:15>12"


def test_a_long_respondent_block_still_reduces() -> None:
    block = Block(
        index=0,
        items=tuple(
            Item(item_id=f"q{n}", kind="choice", text="?", labels=("a", "b", "c"))
            for n in range(40)
        ),
    )
    assert reduce_for_grammar(output_schema(block_contract(block))).schema is not None


# --------------------------------------------------------------------------- #
# No client text in a schema sent to the grammar: Bedrock caches compiled schemas for 24 h
# apart from the messages, outside their protections (AWS, read 2026-10-28).
# --------------------------------------------------------------------------- #

SECRET = "TAJNÁ OTÁZKA KLIENTA 4242"


def test_a_respondent_block_schema_names_items_by_id_never_by_their_text() -> None:
    block = Block(
        index=0,
        items=(
            Item(item_id="q1", kind="choice", text=SECRET, labels=(SECRET, "Ne")),
            Item(item_id="q2", kind="open", text=SECRET),
        ),
    )
    schema = output_schema(block_contract(block))
    reduced = reduce_for_grammar(schema).schema
    assert reduced is not None
    assert SECRET not in json.dumps(schema, ensure_ascii=False)
    assert SECRET not in json.dumps(reduced, ensure_ascii=False)


def test_the_leads_schema_carries_none_of_the_context_its_checks_read() -> None:
    contract = lead_contract(allowed_text=SECRET, identifiers=frozenset({SECRET}))
    assert SECRET not in json.dumps(output_schema(contract), ensure_ascii=False)


def test_no_static_contract_is_built_from_anything_but_code() -> None:
    # Every contract the fixture pins is a class: built once, at import, from code alone.
    assert all(isinstance(c, type) for c in _contracts().values())


if __name__ == "__main__" and "--write" in sys.argv:
    FIXTURE.parent.mkdir(parents=True, exist_ok=True)
    FIXTURE.write_text(json.dumps(_verdicts(), indent=2, sort_keys=True) + "\n")
    print(f"wrote {FIXTURE}")
