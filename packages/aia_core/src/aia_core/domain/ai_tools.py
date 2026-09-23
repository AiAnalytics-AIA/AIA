"""The tool registry: what an agent may call, with arguments a model cannot abuse.

ADR 0007: statistics, parsing, aggregation, validation and cost are tested
deterministic software, exposed to agents as registered tools. The model chooses
*which* tool and *with what parameters*; the tool does the work.

That makes tool arguments the widest untrusted surface in the system -- they are
written by a model -- so the registry holds two lines:

* **Scope never comes from arguments.** A tool's argument model may not declare
  an organization, client, study, tenant or actor field, and a call whose raw
  arguments carry one is refused before validation. The tool receives scope
  from the invocation, which holds an issued ``StudyContext``. The worst a
  compromised argument can do is fail.
* **Arguments are validated strictly and completely.** Argument and result
  models must forbid undeclared fields; arguments are parsed in Pydantic strict
  JSON mode, so ``"5"`` is not an integer and an invented parameter is an error.

An agent can call only the tools its :class:`AgentDefinition` allows. No I/O
here; a tool that reads study data does so through repositories it was
constructed with, under the scope it is handed.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Final

from pydantic import BaseModel, ValidationError

from .ai_contracts import (
    AgentDefinition,
    canonical_json,
    content_fingerprint,
    output_schema,
    schema_node_is_open,
    schema_object_nodes,
)
from .residency import DataClass
from .scope import ScopeDenied, ScopeGrant, StudyContext

__all__ = [
    "SCOPE_ARGUMENT_NAMES",
    "ToolDefinition",
    "ToolEffect",
    "ToolInvocation",
    "ToolRefused",
    "ToolRegistry",
    "ToolResult",
]

#: Argument names that would let a model address data by scope. Compared after
#: normalisation (lower case, separators removed), so ``studyId``, ``study-id``
#: and ``STUDY_ID`` are all the same refusal.
SCOPE_ARGUMENT_NAMES: Final = frozenset(
    {
        "organizationid",
        "organisationid",
        "orgid",
        "clientid",
        "studyid",
        "tenantid",
        "workspaceid",
        "actorid",
        "userid",
        "scope",
        "studycontext",
        "grant",
    }
)

_SEPARATORS: Final = re.compile(r"[^a-z0-9]")


def _normalise(name: str) -> str:
    return _SEPARATORS.sub("", name.lower())


def _scope_keys_in(value: Any) -> list[str]:
    """Every key in a nested argument payload that names a scope."""
    found: list[str] = []
    if isinstance(value, Mapping):
        for key, child in value.items():
            if _normalise(str(key)) in SCOPE_ARGUMENT_NAMES:
                found.append(str(key))
            found.extend(_scope_keys_in(child))
    elif isinstance(value, list):
        for item in value:
            found.extend(_scope_keys_in(item))
    return found


def _declared_names(schema: Mapping[str, Any]) -> list[str]:
    """Every property name and alias an argument schema declares, at any depth."""
    names: list[str] = []
    for node in schema_object_nodes(schema):
        names.extend(str(k) for k in node.get("properties", {}))
    return names


class ToolEffect(StrEnum):
    """What a tool touches. Metered external calls are deliberately absent.

    A tool that spends money needs its own egress check, reservation and ledger
    entry -- the generalized metered-cost ledger that does not exist yet
    (``docs/architecture/ai-runtime.md``, *Cost accounting*). Until it does, such
    a tool cannot be registered, rather than being registered and uncounted.
    """

    #: Deterministic computation over its arguments only.
    PURE = "PURE"
    #: Reads study data through repositories, under the invocation's scope.
    READS_STUDY_DATA = "READS_STUDY_DATA"


class ToolRefused(PermissionError):
    """A tool call was refused. ``reason`` is a stable code."""

    def __init__(self, message: str, *, reason: str, violations: tuple[str, ...] = ()) -> None:
        super().__init__(message)
        self.reason = reason
        self.violations = violations


@dataclass(frozen=True, slots=True)
class ToolInvocation:
    """The trusted half of a tool call: who is calling, under which scope."""

    scope: StudyContext
    agent_id: str
    call_id: str

    def __post_init__(self) -> None:
        if not isinstance(self.scope, StudyContext) or not isinstance(self.scope.grant, ScopeGrant):
            raise ScopeDenied(
                "tool calls require an issued study context", reason="unauthorised_scope"
            )


ToolHandler = Callable[[ToolInvocation, BaseModel], BaseModel]


@dataclass(frozen=True, slots=True)
class ToolDefinition:
    """One registered tool.

    ``result_data_class`` is required: a tool's output goes back into a model's
    context, and the next call's egress decision needs to know what it carries.
    There is no default for the same reason ``ModelRequest`` has none.
    """

    name: str
    version: str
    description: str
    args_model: type[BaseModel]
    result_model: type[BaseModel]
    handler: ToolHandler
    result_data_class: DataClass
    effect: ToolEffect = ToolEffect.PURE

    def spec(self) -> dict[str, Any]:
        """The provider-facing description: name, description, input schema."""
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": output_schema(self.args_model),
        }


@dataclass(frozen=True, slots=True)
class ToolResult:
    """A tool's validated result, with the fingerprints provenance needs."""

    tool: str
    version: str
    result: BaseModel
    data_class: DataClass
    args_fingerprint: str
    result_fingerprint: str


_TOOL_NAME: Final = re.compile(r"^[a-z][a-z0-9_]{0,63}$")


class ToolRegistry:
    """Registered tools, checked at registration and at every call."""

    def __init__(self, tools: Iterable[ToolDefinition] = ()) -> None:
        self._tools: dict[str, ToolDefinition] = {}
        for tool in tools:
            self.register(tool)

    def register(self, tool: ToolDefinition) -> None:
        """Add a tool, or raise ``ValueError`` if it could be abused.

        Checked here rather than at first call, so a bad tool stops a deploy
        instead of an agent.
        """
        if not _TOOL_NAME.match(tool.name):
            raise ValueError(f"tool name {tool.name!r} must be lower_snake_case")
        if tool.name in self._tools:
            raise ValueError(f"tool {tool.name} is already registered")
        if not tool.version.strip():
            raise ValueError(f"tool {tool.name} needs a version")
        if not isinstance(tool.effect, ToolEffect):
            raise ValueError(f"tool {tool.name} declares an unsupported effect")

        for label, model in (("argument", tool.args_model), ("result", tool.result_model)):
            schema = output_schema(model)
            if any(schema_node_is_open(n) for n in schema_object_nodes(schema)):
                raise ValueError(
                    f"tool {tool.name} {label} model must forbid undeclared fields "
                    "(model_config extra='forbid')"
                )

        scoped = [
            n
            for n in _declared_names(output_schema(tool.args_model))
            if _normalise(n) in SCOPE_ARGUMENT_NAMES
        ]
        if scoped:
            raise ValueError(
                f"tool {tool.name} declares scope arguments {sorted(scoped)}; scope comes "
                "from the invocation's issued StudyContext, never from model arguments"
            )
        self._tools[tool.name] = tool

    def get(self, name: str) -> ToolDefinition | None:
        """Return a registered tool, or None."""
        return self._tools.get(name)

    def specs_for(self, agent: AgentDefinition) -> list[dict[str, Any]]:
        """Provider-facing specs for the tools this agent may call, by name.

        An allowed tool that is not registered is an error: an agent believing
        it has a tool it does not is a prompt that promises something false.
        """
        missing = sorted(agent.allowed_tools - set(self._tools))
        if missing:
            raise ValueError(f"agent {agent.agent_id} allows unregistered tools {missing}")
        return [self._tools[name].spec() for name in sorted(agent.allowed_tools)]

    def invoke(
        self,
        *,
        agent: AgentDefinition,
        name: str,
        raw_arguments: Mapping[str, Any] | str,
        invocation: ToolInvocation,
    ) -> ToolResult:
        """Validate and run one model-requested tool call, or raise :class:`ToolRefused`."""
        if invocation.agent_id != agent.agent_id:
            raise ToolRefused("invocation is for a different agent", reason="agent_mismatch")
        if name not in agent.allowed_tools:
            raise ToolRefused(
                f"agent {agent.agent_id} may not call {name!r}", reason="tool_not_allowed"
            )
        tool = self._tools.get(name)
        if tool is None:
            raise ToolRefused(f"no tool named {name!r}", reason="unknown_tool")

        if isinstance(raw_arguments, str):
            try:
                parsed: Any = json.loads(raw_arguments)
            except ValueError as exc:
                raise ToolRefused(
                    "tool arguments are not JSON", reason="invalid_arguments"
                ) from exc
        else:
            parsed = raw_arguments
        if not isinstance(parsed, Mapping):
            raise ToolRefused("tool arguments must be an object", reason="invalid_arguments")

        scoped = _scope_keys_in(parsed)
        if scoped:
            # Refused before validation, and with its own reason: this is not a
            # malformed call, it is an attempt to address data by scope.
            raise ToolRefused(
                f"tool arguments may not carry scope ({sorted(scoped)})",
                reason="scope_in_model_arguments",
            )

        payload = canonical_json(parsed)
        try:
            arguments = tool.args_model.model_validate_json(payload, strict=True)
        except ValidationError as exc:
            violations = tuple(
                f"{'.'.join(str(p) for p in e['loc']) or '<root>'}: {e['msg']}"
                for e in exc.errors()
            )
            raise ToolRefused(
                f"invalid arguments for {name}", reason="invalid_arguments", violations=violations
            ) from exc

        result = tool.handler(invocation, arguments)
        if not isinstance(result, tool.result_model):
            # A tool returning the wrong shape is a defect in the tool, not in the
            # model's call; refusing keeps the bad value out of the next prompt.
            raise ToolRefused(
                f"tool {name} returned {type(result).__name__}, not {tool.result_model.__name__}",
                reason="tool_contract_violation",
            )

        return ToolResult(
            tool=tool.name,
            version=tool.version,
            result=result,
            data_class=tool.result_data_class,
            args_fingerprint=content_fingerprint(parsed),
            result_fingerprint=content_fingerprint(result.model_dump(mode="json")),
        )
