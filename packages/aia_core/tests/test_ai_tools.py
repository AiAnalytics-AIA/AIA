"""The tool registry and the execution context: scope never comes from a model.

A tool's arguments are written by a model, which makes them the widest untrusted
input in the system. These tests pin the two lines the registry holds -- no scope
in arguments, and strict validation of everything else -- and the matching rule
on the model-call side: an execution context accepts only an issued scope.
"""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any

import pytest
from pydantic import BaseModel, ConfigDict, Field

from aia_core.domain.ai_contracts import AgentDefinition, ModelCallFailed, ProviderErrorKind
from aia_core.domain.ai_execution import ExecutionContext, ReservationView, recovery_inputs
from aia_core.domain.ai_models import ModelCapability
from aia_core.domain.ai_tools import (
    ToolDefinition,
    ToolEffect,
    ToolInvocation,
    ToolRefused,
    ToolRegistry,
)
from aia_core.domain.residency import DataClass
from aia_core.domain.scope import ScopeDenied
from aia_core.domain.workflow import FailureClass


class SumArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    values: list[int]


class SumResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    total: int
    study_seen: str


def _sum(invocation: ToolInvocation, args: BaseModel) -> BaseModel:
    assert isinstance(args, SumArgs)
    # The study comes from the issued scope, not from anything the model wrote.
    return SumResult(total=sum(args.values), study_seen=invocation.scope.study_id)


def _tool(**overrides: Any) -> ToolDefinition:
    base: dict[str, Any] = {
        "name": "sum_values",
        "version": "1",
        "description": "Add integers.",
        "args_model": SumArgs,
        "result_model": SumResult,
        "handler": _sum,
        "result_data_class": DataClass.CLASS_B_DERIVED_CLIENT,
    }
    return ToolDefinition(**{**base, **overrides})


def _agent(tools: frozenset[str] = frozenset({"sum_values"})) -> AgentDefinition:
    return AgentDefinition(
        agent_id="calc-agent",
        version="1",
        capability=ModelCapability.FAST_EXTRACTION,
        prompt_id="calc",
        prompt_version="1",
        allowed_tools=tools,
    )


@pytest.fixture
def scope(scoped: Any) -> Any:
    return scoped.scope(user="researcher", study="primary")


@pytest.fixture
def invocation(scope: Any) -> ToolInvocation:
    return ToolInvocation(scope=scope, agent_id="calc-agent", call_id="CALL-1")


# --------------------------------------------------------------------------- #
# Registration
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "field_name", ["study_id", "client_id", "organization_id", "tenant_id", "actor_id", "scope"]
)
def test_tool_declaring_a_scope_argument_is_refused_at_registration(field_name: str) -> None:
    args = type(
        "ScopedArgs",
        (BaseModel,),
        {
            "__annotations__": {field_name: str},
            "model_config": ConfigDict(extra="forbid"),
        },
    )
    with pytest.raises(ValueError, match="scope comes from the invocation"):
        ToolRegistry([_tool(args_model=args)])


def test_scope_argument_hidden_in_a_nested_model_or_alias_is_refused() -> None:
    class Inner(BaseModel):
        model_config = ConfigDict(extra="forbid")
        study_ref: str = Field(alias="studyId")

    class Outer(BaseModel):
        model_config = ConfigDict(extra="forbid")
        filters: list[Inner]

    with pytest.raises(ValueError, match="scope"):
        ToolRegistry([_tool(args_model=Outer)])


def test_open_argument_or_result_model_is_refused() -> None:
    class OpenArgs(BaseModel):
        values: list[int]

    class OpenResult(BaseModel):
        total: int

    with pytest.raises(ValueError, match="argument model must forbid"):
        ToolRegistry([_tool(args_model=OpenArgs)])
    with pytest.raises(ValueError, match="result model must forbid"):
        ToolRegistry([_tool(result_model=OpenResult)])


@pytest.mark.parametrize("name", ["SumValues", "sum-values", "", "9sum"])
def test_tool_names_are_lower_snake_case(name: str) -> None:
    with pytest.raises(ValueError, match="lower_snake_case"):
        ToolRegistry([_tool(name=name)])


def test_duplicate_and_unversioned_tools_are_refused() -> None:
    registry = ToolRegistry([_tool()])
    with pytest.raises(ValueError, match="already registered"):
        registry.register(_tool())
    with pytest.raises(ValueError, match="version"):
        ToolRegistry([_tool(version=" ")])


def test_an_unsupported_effect_is_refused() -> None:
    """Metered external tools cannot be registered until their ledger exists."""
    with pytest.raises(ValueError, match="unsupported effect"):
        ToolRegistry([_tool(effect="EXTERNAL_PAID_CALL")])
    assert {e.value for e in ToolEffect} == {"PURE", "READS_STUDY_DATA"}


def test_specs_cover_only_allowed_tools_and_refuse_phantoms() -> None:
    registry = ToolRegistry([_tool()])
    specs = registry.specs_for(_agent())
    assert [s["name"] for s in specs] == ["sum_values"]
    assert specs[0]["input_schema"]["additionalProperties"] is False
    with pytest.raises(ValueError, match="unregistered"):
        registry.specs_for(_agent(frozenset({"sum_values", "imaginary"})))
    assert registry.get("sum_values") is not None
    assert registry.get("imaginary") is None


# --------------------------------------------------------------------------- #
# Invocation
# --------------------------------------------------------------------------- #


def test_valid_call_runs_under_the_invocation_scope(invocation: ToolInvocation) -> None:
    registry = ToolRegistry([_tool()])
    result = registry.invoke(
        agent=_agent(),
        name="sum_values",
        raw_arguments='{"values": [1, 2, 3]}',
        invocation=invocation,
    )
    assert isinstance(result.result, SumResult)
    assert result.result.total == 6
    assert result.result.study_seen == invocation.scope.study_id
    assert result.data_class is DataClass.CLASS_B_DERIVED_CLIENT
    assert result.args_fingerprint.startswith("sha256:")
    # Same arguments, same fingerprint, whatever the key order or spacing.
    again = registry.invoke(
        agent=_agent(),
        name="sum_values",
        raw_arguments={"values": [1, 2, 3]},
        invocation=invocation,
    )
    assert again.args_fingerprint == result.args_fingerprint
    assert again.result_fingerprint == result.result_fingerprint


@pytest.mark.parametrize(
    "arguments",
    [
        {"values": [1], "study_id": "STU-other"},
        {"values": [1], "clientId": "CLI-other"},
        {"values": [1], "filters": {"Organization-ID": "ORG-other"}},
        {"values": [1], "nested": [{"scope": {"study_id": "x"}}]},
    ],
)
def test_model_supplied_scope_is_refused_before_validation(
    invocation: ToolInvocation, arguments: dict[str, Any]
) -> None:
    """The dedicated reason matters: this is not a malformed call, it is an
    attempt to address another study's data."""
    registry = ToolRegistry([_tool()])
    with pytest.raises(ToolRefused) as exc:
        registry.invoke(
            agent=_agent(), name="sum_values", raw_arguments=arguments, invocation=invocation
        )
    assert exc.value.reason == "scope_in_model_arguments"


@pytest.mark.parametrize(
    ("arguments", "fragment"),
    [
        ('{"values": ["1"]}', "values.0"),
        ('{"values": [1], "extra": true}', "extra"),
        ("{}", "values"),
    ],
)
def test_arguments_are_validated_strictly(
    invocation: ToolInvocation, arguments: str, fragment: str
) -> None:
    registry = ToolRegistry([_tool()])
    with pytest.raises(ToolRefused) as exc:
        registry.invoke(
            agent=_agent(), name="sum_values", raw_arguments=arguments, invocation=invocation
        )
    assert exc.value.reason == "invalid_arguments"
    assert any(v.startswith(fragment) for v in exc.value.violations)


@pytest.mark.parametrize("arguments", ["not json", "[1, 2]", '"text"'])
def test_non_object_arguments_are_refused(invocation: ToolInvocation, arguments: str) -> None:
    registry = ToolRegistry([_tool()])
    with pytest.raises(ToolRefused) as exc:
        registry.invoke(
            agent=_agent(), name="sum_values", raw_arguments=arguments, invocation=invocation
        )
    assert exc.value.reason == "invalid_arguments"


def test_agent_may_call_only_its_allowed_tools(invocation: ToolInvocation) -> None:
    registry = ToolRegistry([_tool()])
    with pytest.raises(ToolRefused) as exc:
        registry.invoke(
            agent=_agent(frozenset()),
            name="sum_values",
            raw_arguments={"values": [1]},
            invocation=invocation,
        )
    assert exc.value.reason == "tool_not_allowed"

    with pytest.raises(ToolRefused) as exc:
        registry.invoke(
            agent=_agent(frozenset({"ghost"})),
            name="ghost",
            raw_arguments={},
            invocation=invocation,
        )
    assert exc.value.reason == "unknown_tool"


def test_invocation_for_another_agent_is_refused(scope: Any) -> None:
    registry = ToolRegistry([_tool()])
    with pytest.raises(ToolRefused) as exc:
        registry.invoke(
            agent=_agent(),
            name="sum_values",
            raw_arguments={"values": [1]},
            invocation=ToolInvocation(scope=scope, agent_id="someone-else", call_id="C"),
        )
    assert exc.value.reason == "agent_mismatch"


def test_tool_returning_the_wrong_shape_is_refused(invocation: ToolInvocation) -> None:
    def broken(_: ToolInvocation, __: BaseModel) -> BaseModel:
        return SumArgs(values=[])

    registry = ToolRegistry([_tool(handler=broken)])
    with pytest.raises(ToolRefused) as exc:
        registry.invoke(
            agent=_agent(), name="sum_values", raw_arguments={"values": [1]}, invocation=invocation
        )
    assert exc.value.reason == "tool_contract_violation"


def test_invocation_requires_an_issued_scope() -> None:
    forged = SimpleNamespace(
        organization_id="o", client_id="c", study_id="s", actor_id="a", grant=object()
    )
    with pytest.raises(ScopeDenied):
        ToolInvocation(scope=forged, agent_id="a", call_id="c")  # type: ignore[arg-type]


# --------------------------------------------------------------------------- #
# The execution context
# --------------------------------------------------------------------------- #


class _NullJournal:
    def record_dispatch(self, event: Any) -> None: ...
    def record_outcome(self, event: Any) -> None: ...
    def committed_usd(self) -> float:
        return 0.0


@pytest.mark.parametrize(
    "forged",
    [
        {"organization_id": "o", "client_id": "c", "study_id": "s", "actor_id": "a"},
        SimpleNamespace(
            organization_id="o", client_id="c", study_id="s", actor_id="a", grant=object()
        ),
        None,
    ],
)
def test_execution_context_refuses_anything_but_an_issued_scope(forged: Any) -> None:
    """A dict with the right keys is exactly what a model could produce."""
    with pytest.raises(ScopeDenied) as exc:
        ExecutionContext(scope=forged, runtime_version="rv", journal=_NullJournal())
    assert exc.value.reason == "unauthorised_scope"


def test_execution_context_accepts_an_issued_scope(scope: Any) -> None:
    context = ExecutionContext(scope=scope, runtime_version="rv", journal=_NullJournal())
    assert context.is_cancelled() is False
    assert context.clock().tzinfo is not None
    with pytest.raises(ValueError, match="runtime_version"):
        ExecutionContext(scope=scope, runtime_version=" ", journal=_NullJournal())


def test_reservation_view_rejects_nonsense() -> None:
    with pytest.raises(ValueError):
        ReservationView(reservation_id="", amount_usd=1.0)
    with pytest.raises(ValueError):
        ReservationView(reservation_id="RSV-1", amount_usd=-0.01)


def test_recovery_inputs_carry_the_failure_and_reset_but_not_the_billing_flags() -> None:
    reset = datetime(2026, 9, 23, 15, 0, tzinfo=UTC)
    failure = ModelCallFailed(
        "quota",
        failure=FailureClass.QUOTA,
        reason="provider_quota",
        error_kind=ProviderErrorKind.QUOTA,
        provider_request_id="req_1",
        retry_after=reset,
        paid_call_dispatched=True,
        outcome_known=True,
    )
    inputs = recovery_inputs(failure)
    assert inputs.failure is FailureClass.QUOTA
    assert inputs.quota_reset_at == reset
    assert inputs.error["error_kind"] == "QUOTA"
    assert inputs.error["provider_request_id"] == "req_1"
    # fail_attempt reads these from the attempt row; one source of truth.
    assert "paid_call_dispatched" not in inputs.error
    assert "outcome_known" not in inputs.error
