"""The model call contract: taxonomy, structured output, agents, requests, ledger.

Structured-output validation is the deterministic gate between a model's answer
and anything downstream, so most of these assert a *rejection*: a numeric
string, an invented field, prose around JSON. Each is an answer a lenient parser
would have accepted.
"""

from __future__ import annotations

import dataclasses
from datetime import UTC, datetime
from typing import Any

import pytest
from pydantic import BaseModel, ConfigDict

from aia_core.domain.ai_contracts import (
    AgentDefinition,
    AIUsageEvent,
    CallPurpose,
    CostBasis,
    Delivery,
    FallbackPolicy,
    Message,
    ModelCallFailed,
    ModelRequest,
    ModelUsage,
    ProviderErrorKind,
    UsageOutcome,
    extract_json_object,
    output_schema,
    schema_fingerprint,
    schema_supports_strict,
    strictify,
    validate_structured_output,
)
from aia_core.domain.ai_models import ModelBinding, ModelCapability
from aia_core.domain.providers import Provider
from aia_core.domain.residency import DataClass
from aia_core.domain.workflow import _TAG_TO_CLASS, FailureClass


class Closed(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    count: int


class Nested(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: list[Closed]
    label: str


class WithOptional(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    note: str | None = None


class TypedMap(BaseModel):
    model_config = ConfigDict(extra="forbid")
    scores: dict[str, int]


class Open(BaseModel):
    name: str


class OpenInside(BaseModel):
    model_config = ConfigDict(extra="forbid")
    child: Open


class PropertyNamedProperties(BaseModel):
    model_config = ConfigDict(extra="forbid")
    properties: str
    type: str


def _agent(**overrides: Any) -> AgentDefinition:
    base: dict[str, Any] = {
        "agent_id": "test-agent",
        "version": "1",
        "capability": ModelCapability.FAST_EXTRACTION,
        "prompt_id": "test-prompt",
        "prompt_version": "1",
        "output_contract": Closed,
    }
    return AgentDefinition(**{**base, **overrides})


# --------------------------------------------------------------------------- #
# Taxonomy
# --------------------------------------------------------------------------- #


def test_taxonomy_is_the_reference_ten_plus_other() -> None:
    kinds = {k.value for k in ProviderErrorKind}
    assert len(kinds) == 11
    assert "OTHER" in kinds


def test_taxonomy_and_workflow_tag_map_are_one_vocabulary() -> None:
    """Anti-pattern A6: an enum emitted in one module and matched in another
    drifts. Every kind must be a tag the workflow classifier matches, and every
    tag it matches must be a kind an adapter can emit."""
    assert {k.value for k in ProviderErrorKind} == set(_TAG_TO_CLASS)


@pytest.mark.parametrize(
    ("kind", "failure"),
    [
        (ProviderErrorKind.MISSING, FailureClass.MISSING_CONFIGURATION),
        (ProviderErrorKind.AUTHENTICATION, FailureClass.AUTHENTICATION),
        (ProviderErrorKind.PERMISSION, FailureClass.PERMISSION),
        (ProviderErrorKind.QUOTA, FailureClass.QUOTA),
        (ProviderErrorKind.CAPACITY, FailureClass.PROVIDER_CAPACITY),
        (ProviderErrorKind.MODEL, FailureClass.MODEL_UNAVAILABLE),
        (ProviderErrorKind.SCHEMA, FailureClass.SCHEMA_VIOLATION),
        (ProviderErrorKind.TRANSPORT, FailureClass.TRANSPORT),
        (ProviderErrorKind.SDK_OUTDATED, FailureClass.SDK_OUTDATED),
        (ProviderErrorKind.MAX_TURNS, FailureClass.MAX_TURNS),
        (ProviderErrorKind.OTHER, FailureClass.UNKNOWN),
    ],
)
def test_each_kind_drives_its_own_recovery_class(
    kind: ProviderErrorKind, failure: FailureClass
) -> None:
    assert kind.failure_class is failure


def test_quota_and_capacity_stay_distinguishable() -> None:
    """ADR 0005 condition 5. Collapsing them turns a wait into a failed study."""
    assert ProviderErrorKind.QUOTA.failure_class is not ProviderErrorKind.CAPACITY.failure_class
    assert ProviderErrorKind.QUOTA.failure_class.consumes_attempt is False
    assert ProviderErrorKind.AUTHENTICATION.failure_class.is_permanent


def test_only_unknown_delivery_leaves_the_billing_question_open() -> None:
    assert Delivery.NOT_SENT.outcome_known
    assert Delivery.RESPONDED.outcome_known
    assert not Delivery.UNKNOWN.outcome_known


# --------------------------------------------------------------------------- #
# Strict schemas
# --------------------------------------------------------------------------- #


def test_closed_all_required_contract_is_strict_compatible() -> None:
    assert schema_supports_strict(output_schema(Closed))
    assert schema_supports_strict(output_schema(Nested))


@pytest.mark.parametrize("contract", [WithOptional, TypedMap, Open])
def test_contracts_strict_mode_cannot_enforce_unchanged_skip_the_strict_tier(
    contract: type[BaseModel],
) -> None:
    assert not schema_supports_strict(output_schema(contract))


def test_strictify_refuses_rather_than_rewrites_an_incompatible_schema() -> None:
    """Making an optional field required is a contract change."""
    with pytest.raises(ValueError, match="not strict-compatible"):
        strictify(output_schema(WithOptional))


def test_strictify_does_not_mutate_the_contract_schema() -> None:
    schema = output_schema(Nested)
    before = schema_fingerprint(schema)
    strict = strictify(schema)
    assert schema_fingerprint(schema) == before
    assert strict["additionalProperties"] is False
    assert strict["$defs"]["Closed"]["additionalProperties"] is False


def test_property_named_like_a_keyword_is_not_a_schema_node() -> None:
    assert schema_supports_strict(output_schema(PropertyNamedProperties))


def test_schema_fingerprint_is_stable_and_content_sensitive() -> None:
    assert schema_fingerprint(output_schema(Closed)) == schema_fingerprint(output_schema(Closed))
    assert schema_fingerprint(output_schema(Closed)) != schema_fingerprint(output_schema(Nested))
    assert schema_fingerprint({"a": 1, "b": 2}) == schema_fingerprint({"b": 2, "a": 1})


# --------------------------------------------------------------------------- #
# JSON extraction is deliberately narrow
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "text",
    [
        '{"name": "a", "count": 1}',
        '  {"name": "a", "count": 1}\n',
        '```json\n{"name": "a", "count": 1}\n```',
        '```\n{"name": "a", "count": 1}\n```',
    ],
)
def test_accepted_json_shapes(text: str) -> None:
    extracted = extract_json_object(text)
    assert extracted is not None
    assert extracted.startswith("{")


@pytest.mark.parametrize(
    "text",
    [
        'Here you go: {"name": "a", "count": 1}',
        '{"name": "a", "count": 1} Hope that helps!',
        '[{"name": "a", "count": 1}]',
        '{"name": "a"}{"name": "b"}',
        '```python\n{"name": "a", "count": 1}\n```',
        '```{"name": "a", "count": 1}```',
        '```json\n{"name": "a"',
        "",
    ],
)
def test_ambiguous_or_wrapped_answers_are_not_guessed_at(text: str) -> None:
    assert extract_json_object(text) is None


# --------------------------------------------------------------------------- #
# Deterministic validation
# --------------------------------------------------------------------------- #


def test_valid_answer_validates() -> None:
    verdict = validate_structured_output(Closed, structured=None, text='{"name":"a","count":3}')
    assert verdict.ok
    assert isinstance(verdict.value, Closed)
    assert verdict.value.count == 3
    assert verdict.violations == ()


def test_numeric_string_is_not_an_integer() -> None:
    verdict = validate_structured_output(Closed, structured=None, text='{"name":"a","count":"3"}')
    assert not verdict.ok
    assert verdict.value is None
    assert any(v.startswith("count:") for v in verdict.violations)


def test_invented_field_is_a_violation_not_a_dropped_extra() -> None:
    verdict = validate_structured_output(
        Closed, structured=None, text='{"name":"a","count":3,"confidence":0.99}'
    )
    assert not verdict.ok
    assert any(v.startswith("confidence:") for v in verdict.violations)


def test_missing_field_and_nested_violations_are_located() -> None:
    verdict = validate_structured_output(
        Nested, structured={"items": [{"name": "a"}], "label": "x"}, text=""
    )
    assert not verdict.ok
    assert "items.0.count: Field required" in verdict.violations


def test_provider_native_structure_wins_over_text() -> None:
    verdict = validate_structured_output(
        Closed, structured={"name": "a", "count": 1}, text="not json at all"
    )
    assert verdict.ok


def test_unparseable_text_is_one_violation() -> None:
    verdict = validate_structured_output(Closed, structured=None, text="I cannot help with that.")
    assert verdict.violations == ("output is not a single JSON object",)


def test_validation_is_deterministic() -> None:
    text = '{"name": 1, "count": "x", "extra": true}'
    first = validate_structured_output(Closed, structured=None, text=text)
    second = validate_structured_output(Closed, structured=None, text=text)
    assert first.violations == second.violations
    assert len(first.violations) == 3


# --------------------------------------------------------------------------- #
# Agent definitions
# --------------------------------------------------------------------------- #


def test_agent_with_closed_contract_is_structured() -> None:
    agent = _agent()
    assert agent.is_structured
    assert agent.schema == output_schema(Closed)


def test_text_agent_has_no_schema() -> None:
    agent = _agent(output_contract=None)
    assert not agent.is_structured
    assert agent.schema is None


@pytest.mark.parametrize("contract", [Open, OpenInside])
def test_contract_tolerating_undeclared_fields_is_refused(contract: type[BaseModel]) -> None:
    with pytest.raises(ValueError, match="forbid undeclared fields"):
        _agent(output_contract=contract)


def test_typed_map_is_a_closed_contract() -> None:
    assert _agent(output_contract=TypedMap).is_structured


@pytest.mark.parametrize(
    "overrides",
    [
        {"schema_repair_attempts": 2},
        {"schema_repair_attempts": -1},
        {"max_output_tokens": 0},
        {"capability": ModelCapability.EMBEDDING},
        {"agent_id": " "},
        {"prompt_version": ""},
    ],
)
def test_agent_definition_rejects_unusable_settings(overrides: dict[str, Any]) -> None:
    with pytest.raises(ValueError):
        _agent(**overrides)


# --------------------------------------------------------------------------- #
# Fallback is explicit or absent
# --------------------------------------------------------------------------- #


ALTERNATE = ModelBinding(provider=Provider.OPENAI, model="m", route_id="r")


def test_default_fallback_policy_authorises_nothing() -> None:
    assert FallbackPolicy().is_explicit is False


def test_explicit_fallback_needs_an_authoriser() -> None:
    with pytest.raises(ValueError, match="who authorised"):
        FallbackPolicy(alternates=(ALTERNATE,), on=frozenset({ProviderErrorKind.CAPACITY}))


def test_explicit_fallback_needs_the_kinds_it_covers() -> None:
    with pytest.raises(ValueError, match="failures it covers"):
        FallbackPolicy(alternates=(ALTERNATE,), authorised_by="user-1")


@pytest.mark.parametrize(
    "kind",
    [
        ProviderErrorKind.AUTHENTICATION,
        ProviderErrorKind.PERMISSION,
        ProviderErrorKind.MISSING,
        ProviderErrorKind.SCHEMA,
        ProviderErrorKind.OTHER,
    ],
)
def test_misconfiguration_cannot_be_routed_around(kind: ProviderErrorKind) -> None:
    with pytest.raises(ValueError, match="cannot cover"):
        FallbackPolicy(alternates=(ALTERNATE,), on=frozenset({kind}), authorised_by="user-1")


def test_kinds_without_alternates_authorise_nothing() -> None:
    with pytest.raises(ValueError):
        FallbackPolicy(on=frozenset({ProviderErrorKind.CAPACITY}))


# --------------------------------------------------------------------------- #
# Requests carry no scope
# --------------------------------------------------------------------------- #


def test_model_request_has_no_scope_field() -> None:
    """Whose data a call carries comes from the issued StudyContext only."""
    names = {f.name for f in dataclasses.fields(ModelRequest)}
    for forbidden in ("organization_id", "client_id", "study_id", "actor_id", "scope"):
        assert forbidden not in names


def test_request_requires_messages_and_a_positive_cap() -> None:
    with pytest.raises(ValueError):
        ModelRequest(
            agent=_agent(),
            policy_version="p",
            data_classification=DataClass.CLASS_C_INTERNAL,
            system="s",
            messages=(),
        )
    with pytest.raises(ValueError):
        ModelRequest(
            agent=_agent(),
            policy_version="p",
            data_classification=DataClass.CLASS_C_INTERNAL,
            system="s",
            messages=(Message(role="user", content="x"),),
            max_output_tokens=0,
        )


def test_request_output_limit_defaults_to_the_agent() -> None:
    request = ModelRequest(
        agent=_agent(max_output_tokens=123),
        policy_version="p",
        data_classification=None,
        system="s",
        messages=(Message(role="user", content="x"),),
    )
    assert request.output_token_limit == 123
    assert request.capability is ModelCapability.FAST_EXTRACTION
    assert request.fallback_policy.is_explicit is False


# --------------------------------------------------------------------------- #
# Usage and ledger records
# --------------------------------------------------------------------------- #


def test_unreported_usage_is_not_zero() -> None:
    assert ModelUsage().is_priceable is False
    assert ModelUsage(input_tokens=0, output_tokens=0).is_priceable is True


def _event(**overrides: Any) -> AIUsageEvent:
    base: dict[str, Any] = {
        "event_id": "e1",
        "call_id": "c1",
        "outcome": UsageOutcome.SUCCEEDED,
        "purpose": CallPurpose.PRIMARY,
        "organization_id": "o",
        "client_id": "c",
        "study_id": "s",
        "actor_id": "a",
        "run_id": None,
        "step_id": None,
        "attempt_id": None,
        "reservation_id": None,
        "agent_id": "ag",
        "agent_version": "1",
        "prompt_id": "p",
        "prompt_version": "1",
        "capability": ModelCapability.CRITIC,
        "policy_version": "pv",
        "runtime_version": "rv",
        "provider": Provider.OPENAI,
        "model": "m",
        "served_model": "m",
        "route_id": "r",
        "data_class": DataClass.CLASS_C_INTERNAL,
        "residency_zone": "NON_EU",
        "provider_request_id": None,
        "error_kind": None,
        "failure_class": None,
        "finish_reason": None,
        "usage": ModelUsage(),
        "cost_usd": 0.0,
        "cost_basis": CostBasis.METERED,
        "schema_fingerprint": None,
        "substituted_from": None,
        "fallback_from": None,
        "fallback_authorised_by": None,
        "occurred_at": datetime(2026, 9, 22, tzinfo=UTC),
    }
    return AIUsageEvent(**{**base, **overrides})


def test_negative_cost_only_on_a_compensating_entry() -> None:
    with pytest.raises(ValueError, match="compensating"):
        _event(cost_usd=-1.0)
    entry = _event(
        cost_usd=-1.0,
        cost_basis=CostBasis.COMPENSATION,
        outcome=UsageOutcome.RESOLVED_NOT_BILLED,
        supersedes_event_id="e0",
    )
    assert entry.cost_usd == -1.0


def test_resolution_must_name_what_it_supersedes() -> None:
    with pytest.raises(ValueError, match="supersedes"):
        _event(outcome=UsageOutcome.RESOLVED_BILLED)


def test_dispatched_is_the_only_non_terminal_outcome() -> None:
    assert [o for o in UsageOutcome if not o.is_terminal] == [UsageOutcome.DISPATCHED]


def test_failure_offers_no_way_around_itself() -> None:
    failure = ModelCallFailed("x", failure=FailureClass.QUOTA, reason="r")
    for attribute in ("suggested_provider", "fallback_provider", "fallback_model"):
        assert not hasattr(failure, attribute)
    assert failure.outcome_known is True
