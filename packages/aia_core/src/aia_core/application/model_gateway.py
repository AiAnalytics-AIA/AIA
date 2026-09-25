"""The governed model gateway: AIA's one implementation of the call semantics.

ADR 0005 decision A. Providers sit underneath as :class:`ProviderAdapter`
implementations that translate and classify and do nothing else; every decision
with cost or provenance consequences is made here, in this order, and recorded:

1. **Resolve** the capability to one ``(provider, model, route)`` under the
   request's policy version. Unconfigured, unpermitted or unknown is refused.
2. **Authorise egress** -- two gates, both required, neither implying the other:
   *residency* for the request's data class over the binding's route, from the
   issued ``StudyContext`` (unclassified material, an unknown route or a route
   that does not carry this class is refused, ADR 0008); then *licence
   eligibility* for the datasets the material derives from over the same route
   (an undeclared lineage, or a dataset whose determination does not approve the
   route, is refused, ADR 0016). Each refusal names its gate (``egress_*`` or
   ``licence_*``) and offers no alternative.
3. **Preflight the budget** for a metered call: the call's worst-case cost,
   plus what this attempt has already spent, must fit the reservation the
   durable layer granted. A metered call with no reservation is refused.
4. **Journal the dispatch** -- durably -- before anything is sent.
5. **Send** through the adapter bound to that route, and classify what comes back.
6. **Validate** structured output deterministically, allowing the agent's one
   same-model repair, recorded as its own call.
7. **Ledger** every call's terminal outcome, including failures and the
   uncertain case, with the provider request id wherever one exists.
8. **Fall back** only when the request carries an explicitly authorised
   :class:`FallbackPolicy`, only for the failure kinds it names, only when the
   failed call's billing outcome is known, and only to bindings the policy
   permits -- each alternate re-running steps 1-7.

What this gateway deliberately never does: retry on its own, pick a different
model or provider on its own, or estimate a cost optimistically. Each of those
is a way to spend a client's money, or change a finding's provenance, without
anybody deciding to.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Final

from aia_core.domain.ai_contracts import (
    AdapterRequest,
    AIUsageEvent,
    CallProvenance,
    CallPurpose,
    CostBasis,
    FinishReason,
    Message,
    ModelCallFailed,
    ModelRequest,
    ModelResult,
    ModelUsage,
    ProviderAdapter,
    ProviderError,
    ProviderErrorKind,
    UsageOutcome,
    canonical_json,
    input_fingerprint,
    new_call_id,
    new_usage_event_id,
    schema_fingerprint,
    schema_supports_strict,
    validate_structured_output,
)
from aia_core.domain.ai_execution import ExecutionContext
from aia_core.domain.ai_models import ModelRegistry, ModelResolution, ResolutionError
from aia_core.domain.licence import LicenceDenied, LicencePolicy
from aia_core.domain.providers import check_budget
from aia_core.domain.residency import EgressDecision, EgressDenied, EgressPolicy
from aia_core.domain.workflow import FailureClass

__all__ = ["REPAIR_PROMPT_VERSION", "GovernedModelGateway", "input_token_bound"]

#: Identity of the runtime's own schema-repair instruction. It is a prompt, so
#: it is versioned and recorded on every repair call like any other.
REPAIR_PROMPT_VERSION: Final = "schema-repair-v1"

# Framing allowance per message and per request, on top of content bytes.
_PER_MESSAGE_OVERHEAD_TOKENS: Final = 16
_PER_REQUEST_OVERHEAD_TOKENS: Final = 256
_UNSAFE_NAME: Final = re.compile(r"[^A-Za-z0-9_]")


def input_token_bound(request: AdapterRequest) -> int:
    """An upper bound on a request's input tokens, without a tokenizer.

    Byte-level BPE tokenizers emit at least one byte per token, so the UTF-8
    byte count of the content bounds its token count from above; framing is
    added per message. The bound is deliberately loose -- typically several
    times the real count -- because an estimate that can come in *under* the
    truth lets a call past a reservation that cannot cover it. The ledger
    records the real count afterwards.
    """
    content = [request.system, *(m.content for m in request.messages)]
    if request.output_schema is not None:
        content.append(canonical_json(request.output_schema))
    return (
        sum(len(part.encode("utf-8")) for part in content)
        + _PER_MESSAGE_OVERHEAD_TOKENS * (len(request.messages) + 1)
        + _PER_REQUEST_OVERHEAD_TOKENS
    )


def _schema_name(agent_id: str) -> str:
    """A provider-safe name for the output contract: ``[A-Za-z0-9_]{1,64}``."""
    return _UNSAFE_NAME.sub("_", agent_id)[:64] or "structured_output"


def _repair_message(violations: tuple[str, ...]) -> str:
    listed = "\n".join(f"- {v}" for v in violations)
    return (
        "Your previous answer did not satisfy the required output schema:\n"
        f"{listed}\n"
        "Return one JSON object that satisfies the schema exactly. "
        "Return only the JSON object."
    )


@dataclass(frozen=True, slots=True)
class _Lane:
    """One resolved binding being executed, with what it inherits from the plan."""

    resolution: ModelResolution
    egress: EgressDecision
    adapter: ProviderAdapter
    fallback_from: str | None
    fallback_authorised_by: str | None


class GovernedModelGateway:
    """The :class:`~aia_core.domain.ai_execution.ModelGateway` implementation."""

    def __init__(
        self,
        *,
        registry: ModelRegistry,
        egress: EgressPolicy,
        licence: LicencePolicy,
        adapters: Mapping[str, ProviderAdapter],
        call_ids: Callable[[], str] = new_call_id,
        event_ids: Callable[[], str] = new_usage_event_id,
    ) -> None:
        """``adapters`` is keyed by **route id**, not by provider.

        ``licence`` is the licence gate's policy -- in every composition root,
        :func:`aia_core.domain.licence_determinations.recorded_policy`; there is
        no default, so a gateway cannot be built without one.

        A route is the unit of residency approval (ADR 0008): the same provider
        over a different region, account, credential or transport is a different
        route. Selecting an adapter by provider would let a call authorised for
        one route leave over another route's transport, so each approved route
        names the adapter that carries it, and nothing else may.
        """
        for route_id, adapter in adapters.items():
            route = egress.route(route_id)
            if route is None:
                raise ValueError(f"adapter bound to unknown route {route_id!r}")
            if route.provider != adapter.provider.value:
                raise ValueError(
                    f"route {route_id} carries {route.provider}, but its adapter speaks "
                    f"{adapter.provider.value}"
                )
        self._registry = registry
        self._egress = egress
        self._licence = licence
        self._adapters = dict(adapters)
        self._call_ids = call_ids
        self._event_ids = event_ids

    # ------------------------------------------------------------ entry point --

    async def invoke(self, request: ModelRequest, context: ExecutionContext) -> ModelResult:
        """Run one logical request, or raise :class:`ModelCallFailed`."""
        if not isinstance(context, ExecutionContext):
            raise TypeError("invoke requires an ExecutionContext")
        events: list[AIUsageEvent] = []

        try:
            primary = self._registry.resolve(
                capability=request.capability,
                policy_version=request.policy_version,
                requested_provider=request.requested_provider,
                requested_model=request.requested_model,
            )
        except ResolutionError as exc:
            raise self._failed(
                str(exc),
                events,
                failure=FailureClass.MISSING_CONFIGURATION,
                reason=f"model_resolution_{exc.reason}",
            ) from exc

        try:
            return await self._execute(
                request, context, self._lane(request, context, primary, events), events
            )
        except ModelCallFailed as exc:
            last = exc

        policy = request.fallback_policy
        for alternate in policy.alternates:
            if not self._may_fall_back(last, request):
                break
            try:
                resolution = self._registry.resolve_binding(
                    capability=request.capability,
                    policy_version=request.policy_version,
                    binding=alternate,
                )
            except ResolutionError as exc:
                raise self._failed(
                    str(exc),
                    events,
                    failure=FailureClass.MISSING_CONFIGURATION,
                    reason=f"fallback_resolution_{exc.reason}",
                ) from exc
            try:
                lane = self._lane(
                    request,
                    context,
                    resolution,
                    events,
                    fallback_from=primary.binding.label(),
                    fallback_authorised_by=policy.authorised_by,
                )
                return await self._execute(request, context, lane, events)
            except ModelCallFailed as exc:
                last = exc

        raise self._failed(
            str(last),
            events,
            failure=last.failure,
            reason=last.reason,
            error_kind=last.error_kind,
            provider_request_id=last.provider_request_id,
            retry_after=last.retry_after,
            violations=last.violations,
        ) from last

    # ---------------------------------------------------------------- stages --

    def _lane(
        self,
        request: ModelRequest,
        context: ExecutionContext,
        resolution: ModelResolution,
        events: list[AIUsageEvent],
        *,
        fallback_from: str | None = None,
        fallback_authorised_by: str | None = None,
    ) -> _Lane:
        """Authorise egress and find the adapter for one resolved binding."""
        try:
            decision = self._egress.authorise(
                scope=context.scope,
                data_class=request.data_classification,
                route_id=resolution.route_id,
            )
        except EgressDenied as exc:
            raise self._failed(
                str(exc), events, failure=FailureClass.PERMISSION, reason=f"egress_{exc.reason}"
            ) from exc
        if decision.provider != resolution.provider.value:
            # A route is approved for one provider. Sending another provider's
            # traffic over it would borrow an approval nobody gave.
            raise self._failed(
                f"route {resolution.route_id} carries {decision.provider}, "
                f"not {resolution.provider.value}",
                events,
                failure=FailureClass.PERMISSION,
                reason="egress_route_provider_mismatch",
            )
        # Residency passed; the licence gate is separate and must pass as well.
        route = self._egress.route(resolution.route_id)
        if route is None:  # pragma: no cover - authorise() has just refused an unknown route
            raise self._failed(
                f"no approved route {resolution.route_id}",
                events,
                failure=FailureClass.PERMISSION,
                reason="egress_no_approved_route",
            )
        try:
            self._licence.authorise(lineage=request.data_lineage, route=route)
        except LicenceDenied as exc:
            raise self._failed(
                str(exc), events, failure=FailureClass.PERMISSION, reason=f"licence_{exc.reason}"
            ) from exc

        adapter = self._adapters.get(resolution.route_id)
        if adapter is None or adapter.provider is not resolution.provider:
            # No provider-wide default: an unbound route does not borrow another
            # route's adapter, even for the same provider.
            raise self._failed(
                f"no adapter bound to route {resolution.route_id}",
                events,
                failure=FailureClass.MISSING_CONFIGURATION,
                reason="no_adapter_for_route",
            )

        if request.output_token_limit > resolution.descriptor.max_output_tokens:
            # Refused rather than quietly capped: a lower cap changes where
            # output is truncated, which is a behaviour the caller did not ask for.
            raise self._failed(
                f"{request.output_token_limit} output tokens exceeds "
                f"{resolution.model}'s {resolution.descriptor.max_output_tokens}",
                events,
                failure=FailureClass.MISSING_CONFIGURATION,
                reason="output_limit_exceeds_model",
            )

        if resolution.descriptor.is_paid:
            if context.reservation is None:
                raise self._failed(
                    "a metered call requires a budget reservation",
                    events,
                    failure=FailureClass.MISSING_CONFIGURATION,
                    reason="paid_call_without_reservation",
                )
            if (
                request.budget_reservation_id is not None
                and request.budget_reservation_id != context.reservation.reservation_id
            ):
                raise self._failed(
                    "request names a different reservation than the attempt holds",
                    events,
                    failure=FailureClass.MISSING_CONFIGURATION,
                    reason="reservation_mismatch",
                )

        return _Lane(
            resolution=resolution,
            egress=decision,
            adapter=adapter,
            fallback_from=fallback_from,
            fallback_authorised_by=fallback_authorised_by,
        )

    async def _execute(
        self,
        request: ModelRequest,
        context: ExecutionContext,
        lane: _Lane,
        events: list[AIUsageEvent],
    ) -> ModelResult:
        """Run one lane: the call, and at most the agent's one schema repair."""
        agent = request.agent
        descriptor = lane.resolution.descriptor
        schema = agent.schema
        fingerprint = schema_fingerprint(schema) if schema is not None else None
        strict = (
            schema is not None
            and descriptor.supports_strict_schema
            and schema_supports_strict(schema)
        )

        messages = request.messages
        purpose = CallPurpose.FALLBACK if lane.fallback_from else CallPurpose.PRIMARY
        repairs_left = agent.schema_repair_attempts

        while True:
            outbound = AdapterRequest(
                call_id=self._call_ids(),
                provider=lane.resolution.provider,
                model=lane.resolution.model,
                system=request.system,
                messages=messages,
                max_output_tokens=request.output_token_limit,
                output_schema=schema,
                schema_name=_schema_name(agent.agent_id) if schema is not None else "",
                strict_schema=strict,
            )
            in_fp = input_fingerprint(outbound)
            ceiling = 0.0
            if descriptor.pricing is not None and descriptor.is_paid:
                ceiling = descriptor.pricing.ceiling_usd(
                    max_input_tokens=input_token_bound(outbound),
                    max_output_tokens=outbound.max_output_tokens,
                )
                assert context.reservation is not None  # checked in _lane
                budget = check_budget(
                    provider=lane.resolution.provider,
                    spent_usd=context.journal.committed_usd(),
                    estimate_usd=ceiling,
                    limit_usd=context.reservation.amount_usd,
                )
                if not budget.allowed:
                    raise self._failed(
                        f"call ceiling ${ceiling:.6f} does not fit the remaining reservation "
                        f"${budget.remaining_usd:.6f}",
                        events,
                        failure=FailureClass.BUDGET_EXCEEDED,
                        reason="reservation_exhausted",
                    )

            if context.is_cancelled():
                raise self._failed(
                    "cancelled before dispatch",
                    events,
                    failure=FailureClass.CANCELLED,
                    reason="cancelled_before_dispatch",
                )

            note = (
                f"repair_prompt={REPAIR_PROMPT_VERSION}"
                if purpose is CallPurpose.SCHEMA_REPAIR
                else ""
            )
            started = context.clock()
            dispatched = self._event(
                request,
                context,
                lane,
                call_id=outbound.call_id,
                input_fp=in_fp,
                outcome=UsageOutcome.DISPATCHED,
                purpose=purpose,
                cost_usd=0.0,
                cost_basis=CostBasis.SUBSCRIPTION if not descriptor.is_paid else CostBasis.CEILING,
                ceiling_usd=ceiling,
                schema_fp=fingerprint,
                at=started,
                note=note,
            )
            context.journal.record_dispatch(dispatched)
            events.append(dispatched)

            try:
                response = await lane.adapter.send(outbound)
            except ProviderError as exc:
                known = exc.delivery.outcome_known
                self._close(
                    context,
                    events,
                    self._event(
                        request,
                        context,
                        lane,
                        call_id=outbound.call_id,
                        input_fp=in_fp,
                        outcome=UsageOutcome.FAILED if known else UsageOutcome.UNCERTAIN,
                        purpose=purpose,
                        cost_usd=0.0 if known else ceiling,
                        cost_basis=(
                            CostBasis.SUBSCRIPTION
                            if not descriptor.is_paid
                            else (CostBasis.METERED if known else CostBasis.CEILING)
                        ),
                        ceiling_usd=ceiling,
                        schema_fp=fingerprint,
                        at=context.clock(),
                        started=started,
                        provider_request_id=exc.provider_request_id,
                        error_kind=exc.kind,
                        note=note,
                    ),
                )
                raise self._failed(
                    str(exc),
                    events,
                    failure=exc.kind.failure_class,
                    reason=f"provider_{exc.kind.value.lower()}",
                    error_kind=exc.kind,
                    provider_request_id=exc.provider_request_id,
                    retry_after=exc.retry_after,
                ) from exc
            except Exception as exc:
                # An adapter defect after dispatch. Nobody can say whether the
                # provider received the request, so it is uncertain -- never
                # "failed, safe to retry".
                self._close(
                    context,
                    events,
                    self._event(
                        request,
                        context,
                        lane,
                        call_id=outbound.call_id,
                        input_fp=in_fp,
                        outcome=UsageOutcome.UNCERTAIN,
                        purpose=purpose,
                        cost_usd=ceiling,
                        cost_basis=CostBasis.CEILING
                        if descriptor.is_paid
                        else CostBasis.SUBSCRIPTION,
                        ceiling_usd=ceiling,
                        schema_fp=fingerprint,
                        at=context.clock(),
                        started=started,
                        error_kind=ProviderErrorKind.OTHER,
                        note=f"adapter raised {type(exc).__name__}",
                    ),
                )
                raise self._failed(
                    f"adapter raised {type(exc).__name__}",
                    events,
                    failure=FailureClass.UNKNOWN,
                    reason="adapter_error",
                    error_kind=ProviderErrorKind.OTHER,
                ) from exc

            finished = context.clock()
            cost, basis = self._price(lane.resolution, response.usage, ceiling)

            violations: tuple[str, ...] = ()
            output = None
            if agent.output_contract is not None:
                if response.finish_reason is FinishReason.TRUNCATED:
                    violations = ("output truncated at the output token limit",)
                else:
                    verdict = validate_structured_output(
                        agent.output_contract,
                        structured=response.structured,
                        text=response.text,
                    )
                    violations, output = verdict.violations, verdict.value

            self._close(
                context,
                events,
                self._event(
                    request,
                    context,
                    lane,
                    call_id=outbound.call_id,
                    input_fp=in_fp,
                    outcome=UsageOutcome.FAILED if violations else UsageOutcome.SUCCEEDED,
                    purpose=purpose,
                    cost_usd=cost,
                    cost_basis=basis,
                    ceiling_usd=ceiling,
                    schema_fp=fingerprint,
                    at=finished,
                    started=started,
                    provider_request_id=response.provider_request_id,
                    error_kind=ProviderErrorKind.SCHEMA if violations else None,
                    finish_reason=response.finish_reason,
                    usage=response.usage,
                    served_model=response.served_model,
                    note=note,
                ),
            )

            if not violations:
                return ModelResult(
                    call_id=outbound.call_id,
                    resolved_provider=lane.resolution.provider,
                    resolved_model=lane.resolution.model,
                    served_model=response.served_model or lane.resolution.model,
                    provider_request_id=response.provider_request_id,
                    usage=response.usage,
                    actual_cost_usd=cost,
                    cost_basis=basis,
                    finish_reason=response.finish_reason,
                    latency_ms=_ms(started, finished),
                    provenance=self._provenance(
                        request, context, lane, fingerprint, started, finished, in_fp
                    ),
                    text=response.text
                    if response.structured is None
                    else canonical_json(response.structured),
                    output=output,
                    usage_events=tuple(events),
                )

            if repairs_left <= 0:
                raise self._failed(
                    "structured output failed validation",
                    events,
                    failure=FailureClass.SCHEMA_VIOLATION,
                    reason="structured_output_invalid",
                    error_kind=ProviderErrorKind.SCHEMA,
                    provider_request_id=response.provider_request_id,
                    violations=violations,
                )
            repairs_left -= 1
            purpose = CallPurpose.SCHEMA_REPAIR
            answer = (
                response.text
                if response.structured is None
                else canonical_json(response.structured)
            )
            messages = (
                *messages,
                Message(role="assistant", content=answer),
                Message(role="user", content=_repair_message(violations)),
            )

    # --------------------------------------------------------------- helpers --

    @staticmethod
    def _may_fall_back(failure: ModelCallFailed, request: ModelRequest) -> bool:
        """True when an explicit fallback covers this failure and nothing is uncertain."""
        policy = request.fallback_policy
        return (
            policy.is_explicit
            and failure.error_kind is not None
            and failure.error_kind in policy.on
            # A failed call whose billing is unknown must reach a person, not a
            # second provider: the first may already have done the work.
            and failure.outcome_known
        )

    @staticmethod
    def _price(
        resolution: ModelResolution, usage: ModelUsage, ceiling: float
    ) -> tuple[float, CostBasis]:
        """Cost of one answered call. Unreported usage is carried at the ceiling."""
        descriptor = resolution.descriptor
        if not descriptor.is_paid or descriptor.pricing is None:
            return 0.0, CostBasis.SUBSCRIPTION
        if usage.input_tokens is None or usage.output_tokens is None:
            return ceiling, CostBasis.CEILING
        # Unreported cache counts are zero *here* because the adapters put every
        # token they cannot attribute to a cache path into input_tokens, which is
        # charged at the full rate. Nothing unknown is priced as a discount.
        return (
            descriptor.pricing.cost_usd(
                input_tokens=usage.input_tokens,
                output_tokens=usage.output_tokens,
                cache_read_input_tokens=usage.cache_read_input_tokens or 0,
                cache_write_input_tokens=usage.cache_write_input_tokens or 0,
            ),
            CostBasis.METERED,
        )

    @staticmethod
    def _close(context: ExecutionContext, events: list[AIUsageEvent], event: AIUsageEvent) -> None:
        context.journal.record_outcome(event)
        events.append(event)

    @staticmethod
    def _failed(
        message: str,
        events: list[AIUsageEvent],
        *,
        failure: FailureClass,
        reason: str,
        error_kind: ProviderErrorKind | None = None,
        provider_request_id: str | None = None,
        retry_after: datetime | None = None,
        violations: tuple[str, ...] = (),
    ) -> ModelCallFailed:
        """Build the failure, with the billing facts taken from the ledger entries."""
        closed = {e.call_id for e in events if e.outcome.is_terminal}
        open_calls = {e.call_id for e in events if not e.outcome.is_terminal} - closed
        uncertain = any(e.outcome is UsageOutcome.UNCERTAIN for e in events) or bool(open_calls)
        return ModelCallFailed(
            message,
            failure=failure,
            reason=reason,
            error_kind=error_kind,
            provider_request_id=provider_request_id,
            retry_after=retry_after,
            paid_call_dispatched=any(
                e.outcome is UsageOutcome.DISPATCHED and e.cost_basis is not CostBasis.SUBSCRIPTION
                for e in events
            ),
            outcome_known=not uncertain,
            violations=violations,
            usage_events=events,
        )

    def _provenance(
        self,
        request: ModelRequest,
        context: ExecutionContext,
        lane: _Lane,
        fingerprint: str | None,
        started: datetime,
        finished: datetime,
        input_fp: str,
    ) -> CallProvenance:
        agent = request.agent
        return CallProvenance(
            agent_id=agent.agent_id,
            agent_version=agent.version,
            prompt_id=agent.prompt_id,
            prompt_version=agent.prompt_version,
            capability=request.capability,
            policy_version=lane.resolution.policy_version,
            runtime_version=context.runtime_version,
            route_id=lane.resolution.route_id,
            data_class=lane.egress.data_class,
            schema_fingerprint=fingerprint,
            substituted_from=lane.resolution.substituted_from,
            explicit_choice=lane.resolution.explicit_choice,
            fallback_from=lane.fallback_from,
            fallback_authorised_by=lane.fallback_authorised_by,
            started_at=started,
            finished_at=finished,
            input_fingerprint=input_fp,
        )

    def _event(
        self,
        request: ModelRequest,
        context: ExecutionContext,
        lane: _Lane,
        *,
        call_id: str,
        outcome: UsageOutcome,
        purpose: CallPurpose,
        cost_usd: float,
        cost_basis: CostBasis,
        ceiling_usd: float,
        schema_fp: str | None,
        at: datetime,
        started: datetime | None = None,
        provider_request_id: str | None = None,
        error_kind: ProviderErrorKind | None = None,
        finish_reason: FinishReason | None = None,
        usage: ModelUsage | None = None,
        served_model: str = "",
        input_fp: str | None = None,
        note: str = "",
    ) -> AIUsageEvent:
        agent = request.agent
        decision = lane.egress
        return AIUsageEvent(
            event_id=self._event_ids(),
            call_id=call_id,
            outcome=outcome,
            purpose=purpose,
            # Attribution from the egress decision, which came from the issued
            # scope -- never from the request.
            organization_id=decision.organization_id,
            client_id=decision.client_id,
            study_id=decision.study_id,
            actor_id=decision.actor_id,
            run_id=context.run_id,
            step_id=context.step_id,
            attempt_id=context.attempt_id,
            reservation_id=context.reservation.reservation_id if context.reservation else None,
            agent_id=agent.agent_id,
            agent_version=agent.version,
            prompt_id=agent.prompt_id,
            prompt_version=agent.prompt_version,
            capability=request.capability,
            policy_version=lane.resolution.policy_version,
            runtime_version=context.runtime_version,
            provider=lane.resolution.provider,
            model=lane.resolution.model,
            served_model=served_model,
            route_id=lane.resolution.route_id,
            data_class=decision.data_class,
            residency_zone=decision.zone.value,
            provider_request_id=provider_request_id,
            error_kind=error_kind,
            failure_class=error_kind.failure_class if error_kind else None,
            finish_reason=finish_reason,
            usage=usage or ModelUsage(),
            cost_usd=cost_usd,
            cost_basis=cost_basis,
            schema_fingerprint=schema_fp,
            substituted_from=lane.resolution.substituted_from,
            fallback_from=lane.fallback_from,
            fallback_authorised_by=lane.fallback_authorised_by,
            occurred_at=at,
            latency_ms=_ms(started, at) if started is not None else None,
            ceiling_usd=ceiling_usd,
            input_fingerprint=input_fp,
            note=note,
        )


def _ms(started: datetime, finished: datetime) -> int:
    return max(0, int((finished - started).total_seconds() * 1000))
