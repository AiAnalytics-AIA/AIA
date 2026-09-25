"""The model call contract: requests, results, errors, usage and structured output.

These are the shapes ADR 0005 decision A fixes. They are AIA's, not a provider
library's: an adapter translates a provider's wire format *into* them, and
nothing upstream of an adapter ever sees a provider SDK type.

Four properties are carried by the shapes themselves rather than by discipline
at call sites:

* **No scope on a request.** :class:`ModelRequest` has no organization, client
  or study field. Scope travels only on the execution context, as an issued
  ``StudyContext`` (see :mod:`aia_core.domain.ai_execution`), so neither a
  caller's payload nor a model's output can name whose data a call carries.
* **The ten-way error taxonomy survives normalisation.** :class:`ProviderError`
  carries a :class:`ProviderErrorKind` and a :class:`Delivery`; quota, capacity
  and authentication stay distinguishable all the way to the recovery decision.
* **The provider request id is never optional in the shape**, only in value: it
  is carried on success *and* failure, because the failure path is where it is
  needed to reconcile a possibly-billed call.
* **Structured output is validated deterministically.** The output contract is a
  Pydantic model; its JSON Schema is what the provider sees, and Pydantic in
  strict JSON mode is what decides whether the answer is acceptable. The model
  is never asked whether its own output is valid.

No I/O.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any, Final, Literal, Protocol
from uuid import uuid4

from pydantic import BaseModel, ValidationError

from .ai_models import ModelBinding, ModelCapability
from .licence import DataLineage
from .providers import Provider
from .residency import DataClass
from .workflow import FailureClass, classify_failure

__all__ = [
    "AIUsageEvent",
    "AdapterRequest",
    "AdapterResponse",
    "AgentDefinition",
    "CallProvenance",
    "CallPurpose",
    "CostBasis",
    "Delivery",
    "FallbackPolicy",
    "FinishReason",
    "Message",
    "ModelCallFailed",
    "ModelRequest",
    "ModelResult",
    "ModelUsage",
    "ProviderAdapter",
    "ProviderError",
    "ProviderErrorKind",
    "StructuredValidation",
    "UsageOutcome",
    "canonical_json",
    "content_fingerprint",
    "extract_json_object",
    "input_fingerprint",
    "new_call_id",
    "new_usage_event_id",
    "output_schema",
    "schema_fingerprint",
    "schema_node_is_open",
    "schema_object_nodes",
    "schema_supports_strict",
    "strictify",
    "validate_structured_output",
]


def new_call_id() -> str:
    """Return a new model call id. Fixed before dispatch, recorded first."""
    return "CALL-" + uuid4().hex[:20]


def new_usage_event_id() -> str:
    """Return a new usage ledger entry id."""
    return "AUE-" + uuid4().hex[:20]


# --------------------------------------------------------------------------- #
# The ten-way taxonomy
# --------------------------------------------------------------------------- #


class ProviderErrorKind(StrEnum):
    """Why a provider call failed, in the reference's vocabulary.

    The ten classes of ``ai_router.classify_provider_exception`` plus ``OTHER``
    for anything unrecognised. The values are the reference's bracketed tags, and
    :func:`aia_core.domain.workflow.classify_failure` is the one mapping from a
    tag to a :class:`FailureClass` -- this enum does not keep a second copy of it
    (anti-pattern A6).
    """

    MISSING = "MISSING"
    AUTHENTICATION = "AUTHENTICATION"
    PERMISSION = "PERMISSION"
    QUOTA = "QUOTA"
    CAPACITY = "CAPACITY"
    MODEL = "MODEL"
    SCHEMA = "SCHEMA"
    TRANSPORT = "TRANSPORT"
    SDK_OUTDATED = "SDK_OUTDATED"
    MAX_TURNS = "MAX_TURNS"
    OTHER = "OTHER"

    @property
    def failure_class(self) -> FailureClass:
        """The workflow failure class this kind drives recovery with."""
        return classify_failure(self.value)


class Delivery(StrEnum):
    """What is known about whether a call reached the provider.

    This is the fact the billing question turns on, so an adapter must state it
    rather than leave it to be inferred from the error type:

    * ``NOT_SENT`` -- nothing left the process (connection refused, DNS failure,
      a request rejected locally). Nothing can have been billed.
    * ``RESPONDED`` -- the provider answered, with success or an error. The
      outcome is known.
    * ``UNKNOWN`` -- the request may have been received and processed, and no
      answer arrived (a read timeout, a reset connection). It may have been
      billed. This is the ``SETTLED_UNCERTAIN`` case.
    """

    NOT_SENT = "NOT_SENT"
    RESPONDED = "RESPONDED"
    UNKNOWN = "UNKNOWN"

    @property
    def outcome_known(self) -> bool:
        """True when there is no open billing question."""
        return self is not Delivery.UNKNOWN


class ProviderError(Exception):
    """A classified provider failure, raised by an adapter.

    An adapter that cannot classify an error raises ``OTHER`` (permanent), never
    ``TRANSPORT`` (retryable): an error nobody understands must not be retried
    against a metered provider on the assumption that it is transient.
    """

    def __init__(
        self,
        message: str,
        *,
        kind: ProviderErrorKind,
        delivery: Delivery,
        provider_request_id: str | None = None,
        retry_after: datetime | None = None,
        http_status: int | None = None,
        provider_error_type: str = "",
    ) -> None:
        super().__init__(message)
        self.kind = kind
        self.delivery = delivery
        self.provider_request_id = provider_request_id
        self.retry_after = retry_after
        self.http_status = http_status
        self.provider_error_type = provider_error_type


# --------------------------------------------------------------------------- #
# Structured output
# --------------------------------------------------------------------------- #


def canonical_json(value: Any) -> str:
    """Deterministic JSON text: sorted keys, no whitespace, UTF-8 preserved."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def output_schema(contract: type[BaseModel]) -> dict[str, Any]:
    """The JSON Schema a provider is shown for an output contract."""
    return contract.model_json_schema(mode="validation")


def content_fingerprint(value: Any) -> str:
    """``sha256:`` hash of a JSON value's canonical form."""
    return "sha256:" + hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def input_fingerprint(request: AdapterRequest) -> str:
    """Content hash of what one call sends: the provider-neutral inputs.

    The model and provider are recorded separately; this identifies the
    *content*, so the same inputs sent to a fallback model share a fingerprint.
    """
    return content_fingerprint(
        {
            "system": request.system,
            "messages": [{"role": m.role, "content": m.content} for m in request.messages],
            "output_schema": dict(request.output_schema) if request.output_schema else None,
            "max_output_tokens": request.max_output_tokens,
        }
    )


def schema_fingerprint(schema: Mapping[str, Any]) -> str:
    """Content hash of a schema, recorded in provenance.

    A contract change changes results, so it must be visible on every call that
    used the old one.
    """
    return content_fingerprint(schema)


_SCHEMA_MAPS: Final = ("properties", "$defs", "definitions", "patternProperties")
_SCHEMA_LISTS: Final = ("anyOf", "oneOf", "allOf", "prefixItems")
_SCHEMA_SINGLES: Final = ("items", "additionalProperties", "not", "if", "then", "else")


def schema_object_nodes(node: Any) -> list[dict[str, Any]]:
    """Every object node in a JSON Schema, depth-first, including ``$defs``.

    The walk follows schema keywords rather than every dict value, so a property
    that happens to be *named* ``properties`` or ``type`` is not mistaken for a
    schema node.
    """
    found: list[dict[str, Any]] = []
    if not isinstance(node, dict):
        return found
    if node.get("type") == "object" or "properties" in node:
        found.append(node)
    for key in _SCHEMA_MAPS:
        for child in (node.get(key) or {}).values():
            found.extend(schema_object_nodes(child))
    for key in _SCHEMA_LISTS:
        for child in node.get(key) or ():
            found.extend(schema_object_nodes(child))
    for key in _SCHEMA_SINGLES:
        found.extend(schema_object_nodes(node.get(key)))
    return found


def _closed(node: Mapping[str, Any]) -> bool:
    """True when an object node declares its properties and forbids all others."""
    return "properties" in node and node.get("additionalProperties") is False


def schema_node_is_open(node: Mapping[str, Any]) -> bool:
    """True when an object node accepts keys nobody declared a shape for.

    A typed map (``dict[str, int]``: no properties, ``additionalProperties`` a
    schema) is not open -- every value is still validated. An object with
    ``additionalProperties`` absent or true is open: anything goes.
    """
    extra = node.get("additionalProperties", True)
    if "properties" in node:
        return extra is not False
    return not isinstance(extra, dict)


def schema_supports_strict(schema: Mapping[str, Any]) -> bool:
    """True when a provider's strict mode can enforce ``schema`` *unchanged*.

    Strict mode requires every object to declare its properties, to forbid
    others, and to require all of them. A schema with an optional field or a
    free-form object does not qualify.

    The reference made the same judgement (``ai_router``, strict-tier
    docstring): rather than mutating the contract to fit -- which silently changes
    the returned data shape -- an incompatible schema simply skips the strict
    tier. The deterministic validator still applies either way.
    """
    for node in schema_object_nodes(schema):
        if not _closed(node):
            return False
        properties = node.get("properties", {})
        if set(node.get("required", ())) != set(properties):
            return False
    return True


def strictify(schema: Mapping[str, Any]) -> dict[str, Any]:
    """Return a copy of a strict-compatible schema ready for a strict-mode provider.

    Raises ``ValueError`` for a schema that is not strict-compatible, rather than
    rewriting it into one: making an optional field required is a contract
    change, not a formatting step.
    """
    if not schema_supports_strict(schema):
        raise ValueError("schema is not strict-compatible; send it non-strict instead")
    strict = deepcopy(dict(schema))
    for node in schema_object_nodes(strict):
        node["additionalProperties"] = False
    return strict


_FENCE: Final = "```"


def extract_json_object(text: str) -> str | None:
    """Return the JSON object text in a model's answer, or None.

    Deliberately narrow. Accepted: the whole answer is one JSON object, or the
    whole answer is one fenced code block containing one. Rejected: prose around
    JSON, several objects, a JSON array, anything that needs a guess about which
    part the model "meant". A lenient extractor turns a malformed answer into a
    plausible one, and the validator would then approve the guess.
    """
    body = text.strip()
    if body.startswith(_FENCE):
        if not body.endswith(_FENCE) or len(body) < 2 * len(_FENCE):
            return None
        first_line, newline, rest = body[len(_FENCE) : -len(_FENCE)].partition("\n")
        if not newline or first_line.strip().lower() not in ("", "json"):
            return None
        body = rest.strip()
    try:
        parsed = json.loads(body)
    except ValueError:
        return None
    return body if isinstance(parsed, dict) else None


@dataclass(frozen=True, slots=True)
class StructuredValidation:
    """The deterministic verdict on one structured answer."""

    ok: bool
    value: BaseModel | None
    violations: tuple[str, ...] = ()


def validate_structured_output(
    contract: type[BaseModel],
    *,
    structured: Mapping[str, Any] | None,
    text: str,
) -> StructuredValidation:
    """Validate a provider's answer against its output contract.

    ``structured`` is the provider-native object (for example a forced tool's
    input) and wins when present; otherwise ``text`` must be a JSON object per
    :func:`extract_json_object`. Validation is Pydantic strict JSON mode against a
    contract that forbids undeclared fields: ``"12"`` is not an integer and an
    invented field is a violation, not a silently dropped extra.
    """
    if structured is not None:
        payload = canonical_json(structured)
    else:
        extracted = extract_json_object(text)
        if extracted is None:
            return StructuredValidation(
                ok=False, value=None, violations=("output is not a single JSON object",)
            )
        payload = extracted

    try:
        value = contract.model_validate_json(payload, strict=True)
    except ValidationError as exc:
        violations = tuple(
            f"{'.'.join(str(p) for p in error['loc']) or '<root>'}: {error['msg']}"
            for error in exc.errors()
        )
        return StructuredValidation(ok=False, value=None, violations=violations)
    return StructuredValidation(ok=True, value=value)


# --------------------------------------------------------------------------- #
# Agents
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class AgentDefinition:
    """What an agent is: its capability, its prompt identity and its output contract.

    An agent names a **capability**, never a model. It names a prompt by id and
    version rather than carrying prompt text, so a prompt change is a tracked
    change with its own identity (reference ``ai-prompt-inventory.md``,
    rebuild requirement 1) and every call's provenance says which one ran.

    ``output_contract`` is a Pydantic model that must forbid undeclared fields,
    at every level. A contract that tolerates extras lets a model invent a field
    and have it silently dropped -- or, worse, silently kept by a later consumer
    that reads the raw payload.

    ``schema_repair_attempts`` is 0 or 1. The taxonomy allows a structured-output
    violation one repair; a second is a loop that spends money converging on
    nothing.
    """

    agent_id: str
    version: str
    capability: ModelCapability
    prompt_id: str
    prompt_version: str
    output_contract: type[BaseModel] | None = None
    allowed_tools: frozenset[str] = frozenset()
    max_output_tokens: int = 4096
    schema_repair_attempts: int = 1

    def __post_init__(self) -> None:
        for name in ("agent_id", "version", "prompt_id", "prompt_version"):
            if not str(getattr(self, name)).strip():
                raise ValueError(f"{name} is required on an agent definition")
        if self.max_output_tokens <= 0:
            raise ValueError("max_output_tokens must be positive")
        if self.schema_repair_attempts not in (0, 1):
            raise ValueError("schema_repair_attempts is 0 or 1")
        if self.capability is ModelCapability.EMBEDDING:
            raise ValueError("embedding is not a generative agent capability")
        if self.output_contract is not None:
            schema = output_schema(self.output_contract)
            open_nodes = [n for n in schema_object_nodes(schema) if schema_node_is_open(n)]
            if open_nodes:
                raise ValueError(
                    f"output contract {self.output_contract.__name__} must forbid undeclared "
                    "fields at every level (model_config extra='forbid')"
                )

    @property
    def is_structured(self) -> bool:
        """True when the agent returns a validated object rather than text."""
        return self.output_contract is not None

    @property
    def schema(self) -> dict[str, Any] | None:
        """The output contract's JSON Schema, or None for a text agent."""
        return output_schema(self.output_contract) if self.output_contract else None


# --------------------------------------------------------------------------- #
# Request
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class Message:
    """One conversational turn sent to a model."""

    role: Literal["user", "assistant"]
    content: str


@dataclass(frozen=True, slots=True)
class FallbackPolicy:
    """An **explicitly authorised** fallback, or none. Never implicit.

    The default is no fallback. A non-empty policy names the alternates, the
    failure kinds that may trigger them, and the person who authorised it --
    because a fallback nobody authorised is exactly the silent provider switch
    the product forbids. It must be built from a recorded user decision (a
    provider event with ``explicit_user_action``), never from an error handler.

    Only kinds whose failure says nothing about the request's validity are
    eligible: quota, capacity, an unavailable model, or a transport failure. A
    misconfiguration (authentication, permission, missing) must surface, not be
    routed around.
    """

    alternates: tuple[ModelBinding, ...] = ()
    on: frozenset[ProviderErrorKind] = frozenset()
    authorised_by: str = ""

    def __post_init__(self) -> None:
        if not self.alternates:
            if self.on or self.authorised_by:
                raise ValueError("a fallback policy without alternates authorises nothing")
            return
        if not self.authorised_by.strip():
            raise ValueError("an explicit fallback must name who authorised it")
        if not self.on:
            raise ValueError("an explicit fallback must name the failures it covers")
        ineligible = self.on - _FALLBACK_ELIGIBLE
        if ineligible:
            raise ValueError(
                "fallback cannot cover " + ", ".join(sorted(k.value for k in ineligible))
            )

    @property
    def is_explicit(self) -> bool:
        """True when any fallback is authorised."""
        return bool(self.alternates)


_FALLBACK_ELIGIBLE: Final = frozenset(
    {
        ProviderErrorKind.QUOTA,
        ProviderErrorKind.CAPACITY,
        ProviderErrorKind.MODEL,
        ProviderErrorKind.TRANSPORT,
    }
)


@dataclass(frozen=True, slots=True)
class ModelRequest:
    """One logical model call, as domain code states it.

    There is no organization, client or study field and there must never be one.
    Whose data this is comes from the execution context's issued scope.

    ``data_classification`` has no default. ``None`` is representable so that a
    caller that forgot to classify reaches the egress boundary and is refused
    there, loudly, rather than being defaulted to the most permissive class.

    ``data_lineage`` has no default either, for the same reason at the licence
    gate (ADR 0016 decision 5): the datasets the material was computed from, or
    ``DataLineage.none()`` for material computed from none. ``None`` is refused.
    """

    agent: AgentDefinition
    policy_version: str
    data_classification: DataClass | None
    data_lineage: DataLineage | None
    system: str
    messages: tuple[Message, ...]
    requested_provider: Provider | None = None
    requested_model: str | None = None
    fallback_policy: FallbackPolicy = field(default_factory=FallbackPolicy)
    budget_reservation_id: str | None = None
    max_output_tokens: int | None = None

    def __post_init__(self) -> None:
        if not self.messages:
            raise ValueError("a model request needs at least one message")
        if self.max_output_tokens is not None and self.max_output_tokens <= 0:
            raise ValueError("max_output_tokens must be positive")

    @property
    def capability(self) -> ModelCapability:
        """The logical capability requested -- the agent's."""
        return self.agent.capability

    @property
    def output_token_limit(self) -> int:
        """The output cap for this call."""
        return self.max_output_tokens or self.agent.max_output_tokens


# --------------------------------------------------------------------------- #
# Adapter boundary
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class AdapterRequest:
    """What an adapter is asked to send. Already resolved, authorised and budgeted.

    ``call_id`` is AIA's identifier for this one call, fixed before dispatch and
    recorded in the ledger first. Where a provider accepts a client-supplied
    request id, the adapter sends it, so an uncertain call can be looked up on the
    provider side by an id AIA already holds.
    """

    call_id: str
    provider: Provider
    model: str
    system: str
    messages: tuple[Message, ...]
    max_output_tokens: int
    output_schema: Mapping[str, Any] | None = None
    schema_name: str = ""
    strict_schema: bool = False


class FinishReason(StrEnum):
    """Why generation stopped, normalised across providers."""

    COMPLETED = "COMPLETED"
    TRUNCATED = "TRUNCATED"
    REFUSED = "REFUSED"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True, slots=True)
class ModelUsage:
    """Token usage as the provider reported it.

    ``None`` means *not reported*, which is different from zero. A subscription
    runtime that returns no counts must not appear to have used none, and a
    metered call with no counts cannot be priced from them.
    """

    input_tokens: int | None = None
    output_tokens: int | None = None
    cache_read_input_tokens: int | None = None
    cache_write_input_tokens: int | None = None

    def __post_init__(self) -> None:
        # A negative count would fail pricing *after* the call was dispatched.
        # Refusing it here makes a bad adapter fail inside ``send``, where the
        # gateway records the call as uncertain rather than losing it.
        for name in (
            "input_tokens",
            "output_tokens",
            "cache_read_input_tokens",
            "cache_write_input_tokens",
        ):
            value = getattr(self, name)
            if value is not None and value < 0:
                raise ValueError(f"{name} cannot be negative")

    @property
    def is_priceable(self) -> bool:
        """True when input and output counts are both reported."""
        return self.input_tokens is not None and self.output_tokens is not None


@dataclass(frozen=True, slots=True)
class AdapterResponse:
    """A provider's successful answer, normalised."""

    text: str
    finish_reason: FinishReason
    usage: ModelUsage
    provider_request_id: str | None
    #: The model id the provider says served the call. Recorded so a provider-side
    #: substitution is visible even though AIA did not ask for one.
    served_model: str = ""
    #: A cost the provider itself reported. Provenance only: AIA's ledger prices
    #: from usage and its own catalog.
    reported_cost_usd: float | None = None
    #: The provider-native structured object, when the provider returned one.
    structured: Mapping[str, Any] | None = None


class ProviderAdapter(Protocol):
    """Transport for one provider. Translates, classifies, and does nothing else.

    An adapter **must not** retry, fall back, substitute a model or switch
    provider. Every one of those is a decision with cost and provenance
    consequences, and each is made -- and recorded -- above the adapter.
    """

    @property
    def provider(self) -> Provider: ...

    async def send(self, request: AdapterRequest) -> AdapterResponse:
        """Send one request. Raise :class:`ProviderError` on any failure."""
        ...


# --------------------------------------------------------------------------- #
# Result, provenance and the usage ledger record
# --------------------------------------------------------------------------- #


class CostBasis(StrEnum):
    """How a call's cost figure was arrived at."""

    #: Subscription runtime: no marginal API cost.
    SUBSCRIPTION = "SUBSCRIPTION"
    #: Priced from provider-reported usage and the catalog.
    METERED = "METERED"
    #: Usage was not reported (or the outcome is unknown), so the call is carried
    #: at its preflight ceiling. Over-stated rather than under-stated.
    CEILING = "CEILING"
    #: A compensating entry written when an uncertain call is resolved.
    COMPENSATION = "COMPENSATION"


class CallPurpose(StrEnum):
    """Why this call was made within one logical request."""

    PRIMARY = "PRIMARY"
    SCHEMA_REPAIR = "SCHEMA_REPAIR"
    FALLBACK = "FALLBACK"


class UsageOutcome(StrEnum):
    """The ledger state of one call.

    ``DISPATCHED`` is written *before* the call is sent. A ``DISPATCHED`` entry
    with no later entry for the same ``call_id`` is a call whose process died in
    flight -- which is precisely the call someone will later need to find.
    """

    DISPATCHED = "DISPATCHED"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    UNCERTAIN = "UNCERTAIN"
    RESOLVED_BILLED = "RESOLVED_BILLED"
    RESOLVED_NOT_BILLED = "RESOLVED_NOT_BILLED"

    @property
    def is_terminal(self) -> bool:
        """True when this entry closes the call (possibly as uncertain)."""
        return self is not UsageOutcome.DISPATCHED

    @property
    def is_resolution(self) -> bool:
        """True for a compensating entry that settles an uncertain call."""
        return self in (UsageOutcome.RESOLVED_BILLED, UsageOutcome.RESOLVED_NOT_BILLED)


@dataclass(frozen=True, slots=True)
class CallProvenance:
    """What produced an output, recorded on the result and on every ledger entry."""

    agent_id: str
    agent_version: str
    prompt_id: str
    prompt_version: str
    capability: ModelCapability
    policy_version: str
    runtime_version: str
    route_id: str
    data_class: DataClass
    schema_fingerprint: str | None
    substituted_from: str | None
    explicit_choice: bool
    #: The primary binding this call replaced, when it is an authorised fallback.
    fallback_from: str | None
    fallback_authorised_by: str | None
    started_at: datetime
    finished_at: datetime
    #: Content hash of the inputs of the call that produced the output.
    input_fingerprint: str | None = None


@dataclass(frozen=True, slots=True)
class AIUsageEvent:
    """One entry in the authoritative AI usage ledger. Append-only.

    Every model call writes at least two: ``DISPATCHED`` before sending, and a
    terminal entry after. The attribution fields (organization, client, study,
    actor) are copied from the egress decision, which was computed from an issued
    ``StudyContext``; they are never taken from a request or a model.

    A correction is a new entry that names what it ``supersedes``, never an edit:
    an accounting record that can be changed after the fact cannot be reconciled
    against an invoice. Only a ``COMPENSATION`` entry may carry a negative cost.
    """

    event_id: str
    call_id: str
    outcome: UsageOutcome
    purpose: CallPurpose
    organization_id: str
    client_id: str
    study_id: str
    actor_id: str
    run_id: str | None
    step_id: str | None
    attempt_id: str | None
    reservation_id: str | None
    agent_id: str
    agent_version: str
    prompt_id: str
    prompt_version: str
    capability: ModelCapability
    policy_version: str
    runtime_version: str
    provider: Provider
    model: str
    served_model: str
    route_id: str
    data_class: DataClass
    residency_zone: str
    provider_request_id: str | None
    error_kind: ProviderErrorKind | None
    failure_class: FailureClass | None
    finish_reason: FinishReason | None
    usage: ModelUsage
    cost_usd: float
    cost_basis: CostBasis
    schema_fingerprint: str | None
    substituted_from: str | None
    fallback_from: str | None
    fallback_authorised_by: str | None
    occurred_at: datetime
    latency_ms: int | None = None
    #: The preflight worst case for this call. On ``DISPATCHED`` it is the
    #: exposure the call opens; on ``UNCERTAIN`` it is also the cost carried.
    ceiling_usd: float = 0.0
    #: Content hash of exactly what this call sent -- system prompt, messages,
    #: output schema and output cap -- so a primary call and its repair, or two
    #: calls from the same prompt version with different inputs, are told apart.
    input_fingerprint: str | None = None
    supersedes_event_id: str | None = None
    note: str = ""

    def __post_init__(self) -> None:
        if self.cost_usd < 0 and self.cost_basis is not CostBasis.COMPENSATION:
            raise ValueError("only a compensating entry may carry a negative cost")
        if self.outcome.is_resolution and not self.supersedes_event_id:
            raise ValueError("a resolution must name the entry it supersedes")


@dataclass(frozen=True, slots=True)
class ModelResult:
    """The outcome of one logical request that succeeded.

    ``usage_events`` holds every call the request made -- a failed primary before
    an authorised fallback, a schema-violating answer before its repair -- so the
    cost of the request is the sum of what was actually spent, not of the call
    that happened to succeed.
    """

    call_id: str
    resolved_provider: Provider
    resolved_model: str
    served_model: str
    provider_request_id: str | None
    usage: ModelUsage
    actual_cost_usd: float
    cost_basis: CostBasis
    finish_reason: FinishReason
    latency_ms: int
    provenance: CallProvenance
    text: str
    output: BaseModel | None
    usage_events: tuple[AIUsageEvent, ...]

    @property
    def total_cost_usd(self) -> float:
        """Cost of every call this request made, including failed ones."""
        return sum(e.cost_usd for e in self.usage_events if e.outcome.is_terminal)


class ModelCallFailed(Exception):
    """A logical request failed. Carries what recovery needs, and nothing more.

    ``failure`` drives :func:`aia_core.domain.workflow.decide_recovery`.
    ``outcome_known`` is False when any paid call this request dispatched has an
    unknown outcome -- the case that must become ``RECOVERY_REQUIRED`` and never
    an automatic retry. There is no ``suggested_provider`` and no
    ``fallback_model``: a failure is reported, not routed around.
    """

    def __init__(
        self,
        message: str,
        *,
        failure: FailureClass,
        reason: str,
        error_kind: ProviderErrorKind | None = None,
        provider_request_id: str | None = None,
        retry_after: datetime | None = None,
        paid_call_dispatched: bool = False,
        outcome_known: bool = True,
        violations: Sequence[str] = (),
        usage_events: Sequence[AIUsageEvent] = (),
    ) -> None:
        super().__init__(message)
        self.failure = failure
        self.reason = reason
        self.error_kind = error_kind
        self.provider_request_id = provider_request_id
        self.retry_after = retry_after
        self.paid_call_dispatched = paid_call_dispatched
        self.outcome_known = outcome_known
        self.violations = tuple(violations)
        self.usage_events = tuple(usage_events)
