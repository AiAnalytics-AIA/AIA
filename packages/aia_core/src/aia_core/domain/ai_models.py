"""Model capabilities, the model catalog, model policy and the model registry.

Domain code asks for a **capability**, never a model name. A :class:`ModelPolicy`
maps each capability to a concrete ``(provider, model, route)`` binding, and the
:class:`ModelRegistry` resolves a request against one named policy version. That
is ADR 0005 decision A: choosing a model is a configuration decision made in one
place, not at hundreds of call sites.

Every lookup here **fails closed**:

* a capability the policy does not bind is refused -- it does not fall back to
  "whatever is available";
* a pinned model the policy does not permit is refused -- it is not quietly
  swapped for one that is;
* a provider outside the policy's allow-list cannot be bound at all, so the
  refusal happens when configuration is loaded rather than mid-study;
* a malformed configuration document is an error, never a default. The
  reference's ``edition_config`` reverted a malformed ``BUILD_EDITION.json`` to a
  default that enabled every provider (reference ``configuration-contract.md``,
  ``config.edition``); that is the failure this module exists not to repeat.

The one sanctioned substitution is a **retirement declared in the policy**: the
policy says "``old`` is retired, ``new`` replaces it", the resolution records
``substituted_from``, and the provenance of every call carries it. The reference
substituted retired ids after listing what an account could see; here a live
listing never changes what runs, because a finding produced by a different model
is a different finding.

No I/O. Catalog and policies come from trusted deployment configuration.
"""

from __future__ import annotations

import json
import math
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Final

from pydantic import BaseModel, ConfigDict, Field

from .providers import Provider, is_paid

__all__ = [
    "ModelBinding",
    "ModelCapability",
    "ModelConfigError",
    "ModelDescriptor",
    "ModelPolicy",
    "ModelPricing",
    "ModelRegistry",
    "ModelResolution",
    "ResolutionError",
    "parse_model_config",
]

_PER_MTOK: Final = 1_000_000


class ModelCapability(StrEnum):
    """A logical capability. What domain code asks for instead of a model name."""

    #: Cheap, high-volume structured extraction.
    FAST_EXTRACTION = "FAST_EXTRACTION"
    #: Long-context synthesis and study design.
    RESEARCH_REASONING = "RESEARCH_REASONING"
    #: Long-form prose in Czech.
    REPORT_WRITING = "REPORT_WRITING"
    #: Adversarial review of another agent's output.
    CRITIC = "CRITIC"
    #: Respondent and world simulation.
    SIMULATION = "SIMULATION"
    #: Vector embedding for retrieval.
    EMBEDDING = "EMBEDDING"


class ModelConfigError(ValueError):
    """Model catalog or policy configuration is unusable. Raised at load time."""


class ResolutionError(LookupError):
    """A request cannot be resolved to a model under the named policy.

    ``reason`` is a stable machine-readable code. There is deliberately no
    ``suggested_model`` field, for the same reason ``BudgetDecision`` carries no
    ``suggested_provider``: "this is refused, try that one" is how a policy becomes
    a formality.
    """

    def __init__(self, message: str, *, reason: str) -> None:
        super().__init__(message)
        self.reason = reason


@dataclass(frozen=True, slots=True)
class ModelPricing:
    """Per-million-token prices in USD.

    A cache rate of ``None`` means the provider offers no discount on that path,
    so those tokens are charged at the full input rate. Charging the undiscounted
    rate when nothing says otherwise over-states cost rather than under-stating
    it: an unknown discount is not scored as a good one.
    """

    input_usd_per_mtok: float
    output_usd_per_mtok: float
    cache_read_usd_per_mtok: float | None = None
    cache_write_usd_per_mtok: float | None = None

    def __post_init__(self) -> None:
        for name in (
            "input_usd_per_mtok",
            "output_usd_per_mtok",
            "cache_read_usd_per_mtok",
            "cache_write_usd_per_mtok",
        ):
            value = getattr(self, name)
            if value is None:
                continue
            if not math.isfinite(value) or value < 0:
                raise ModelConfigError(f"{name} must be a finite, non-negative price")

    def cost_usd(
        self,
        *,
        input_tokens: int,
        output_tokens: int,
        cache_read_input_tokens: int = 0,
        cache_write_input_tokens: int = 0,
    ) -> float:
        """Exact cost of one call from provider-reported usage.

        ``input_tokens`` is the *uncached* input. Providers report cached tokens
        separately (or inside the input count, which the adapter separates), and
        each path has its own price.
        """
        counts = (input_tokens, output_tokens, cache_read_input_tokens, cache_write_input_tokens)
        if any(c < 0 for c in counts):
            raise ValueError("token counts cannot be negative")
        read_rate = (
            self.input_usd_per_mtok
            if self.cache_read_usd_per_mtok is None
            else self.cache_read_usd_per_mtok
        )
        write_rate = (
            self.input_usd_per_mtok
            if self.cache_write_usd_per_mtok is None
            else self.cache_write_usd_per_mtok
        )
        return (
            input_tokens * self.input_usd_per_mtok
            + output_tokens * self.output_usd_per_mtok
            + cache_read_input_tokens * read_rate
            + cache_write_input_tokens * write_rate
        ) / _PER_MTOK

    def ceiling_usd(self, *, max_input_tokens: int, max_output_tokens: int) -> float:
        """Worst-case cost of one call: all input uncached, all output used.

        This is what the budget preflight checks. An optimistic estimate would let
        a call through that the reservation cannot cover.
        """
        write_rate = max(
            self.input_usd_per_mtok,
            self.cache_write_usd_per_mtok or 0.0,
        )
        return (
            max(0, max_input_tokens) * write_rate
            + max(0, max_output_tokens) * self.output_usd_per_mtok
        ) / _PER_MTOK


@dataclass(frozen=True, slots=True)
class ModelDescriptor:
    """One model in the catalog: what it can do and what it costs.

    A paid provider's model **must** declare pricing. A metered model with no
    price would estimate every call at zero and pass every budget check -- the
    textbook case of scoring unknown as good.
    """

    provider: Provider
    model: str
    capabilities: frozenset[ModelCapability]
    max_output_tokens: int
    context_window_tokens: int
    pricing: ModelPricing | None = None
    #: The provider can enforce a JSON Schema in strict mode for this model.
    supports_strict_schema: bool = False

    def __post_init__(self) -> None:
        if not self.model.strip():
            raise ModelConfigError("model id is required")
        if not self.capabilities:
            raise ModelConfigError(f"{self.model} declares no capabilities")
        if self.max_output_tokens <= 0 or self.context_window_tokens <= 0:
            raise ModelConfigError(f"{self.model} token limits must be positive")
        if is_paid(self.provider) and self.pricing is None:
            raise ModelConfigError(
                f"{self.provider.value}:{self.model} is metered and must declare pricing"
            )

    @property
    def key(self) -> tuple[Provider, str]:
        """Catalog identity."""
        return (self.provider, self.model)

    @property
    def is_paid(self) -> bool:
        """True when calls to this model are metered and budget-controlled."""
        return is_paid(self.provider)


@dataclass(frozen=True, slots=True)
class ModelBinding:
    """A concrete ``(provider, model)`` reached over one approved route.

    The route is part of the binding because a provider is not a route: the same
    provider over a different transport, account or region is a different
    residency answer (ADR 0008).
    """

    provider: Provider
    model: str
    route_id: str

    def __post_init__(self) -> None:
        if not self.model.strip() or not self.route_id.strip():
            raise ModelConfigError("a binding needs a model and a route")

    def label(self) -> str:
        """``provider:model@route`` for messages and audit."""
        return f"{self.provider.value}:{self.model}@{self.route_id}"


@dataclass(frozen=True, slots=True)
class ModelPolicy:
    """Which model serves each capability, under one versioned name.

    ``bindings`` are the defaults. ``permitted`` lists further bindings a user may
    choose explicitly (a pinned model for a reproducible run, or a provider the
    user selected); nothing outside those two sets can run under this policy.
    ``retirements`` maps a retired model id to its declared replacement, per
    provider.

    ``policy_version`` is recorded on every call because changing the policy
    changes results.
    """

    version: str
    allowed_providers: frozenset[Provider]
    bindings: Mapping[ModelCapability, ModelBinding]
    permitted: Mapping[ModelCapability, tuple[ModelBinding, ...]] = field(default_factory=dict)
    retirements: Mapping[tuple[Provider, str], str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.version.strip():
            raise ModelConfigError("a model policy needs a version")
        if not self.allowed_providers:
            raise ModelConfigError(
                f"policy {self.version} allows no providers; an empty allow-list is not "
                "'all providers'"
            )
        for capability, binding in self.bindings.items():
            self._check_provider(capability, binding)
        for capability, extra in self.permitted.items():
            for binding in extra:
                self._check_provider(capability, binding)
        for (provider, old), new in self.retirements.items():
            if old == new:
                raise ModelConfigError(f"{old} cannot retire to itself")
            if (provider, new) in self.retirements:
                # A chain would make the effective model depend on lookup order.
                raise ModelConfigError(f"retirement target {new} is itself retired")
        for capability, binding in self.all_bindings():
            if (binding.provider, binding.model) in self.retirements:
                raise ModelConfigError(
                    f"policy {self.version} binds retired model {binding.model} "
                    f"for {capability.value}"
                )

    def _check_provider(self, capability: ModelCapability, binding: ModelBinding) -> None:
        if binding.provider not in self.allowed_providers:
            raise ModelConfigError(
                f"policy {self.version} binds {binding.label()} for {capability.value}, "
                "but that provider is not on its allow-list"
            )

    def all_bindings(self) -> Iterable[tuple[ModelCapability, ModelBinding]]:
        """Every binding this policy can run, defaults first."""
        for capability, binding in self.bindings.items():
            yield capability, binding
        for capability, extra in self.permitted.items():
            for binding in extra:
                yield capability, binding

    def candidates(self, capability: ModelCapability) -> tuple[ModelBinding, ...]:
        """Bindings that may serve ``capability``, default first."""
        default = self.bindings.get(capability)
        extra = tuple(self.permitted.get(capability, ()))
        return ((default,) if default else ()) + extra


@dataclass(frozen=True, slots=True)
class ModelResolution:
    """The concrete model a request will run on, and how it was chosen."""

    capability: ModelCapability
    policy_version: str
    binding: ModelBinding
    descriptor: ModelDescriptor
    #: The retired model id the caller asked for, when a declared retirement
    #: replaced it. ``None`` when no substitution happened.
    substituted_from: str | None = None
    #: True when the caller pinned a provider or model rather than taking the
    #: policy default.
    explicit_choice: bool = False

    @property
    def provider(self) -> Provider:
        """Resolved provider."""
        return self.binding.provider

    @property
    def model(self) -> str:
        """Resolved model id."""
        return self.binding.model

    @property
    def route_id(self) -> str:
        """The approved route this call must use."""
        return self.binding.route_id


class ModelRegistry:
    """The catalog plus the named policies, validated together at load time.

    Construction fails if any policy binds a model the catalog does not contain,
    or binds a model to a capability it does not declare. That is deliberate: a
    capability that cannot actually be served should stop a deploy, not a study.
    """

    def __init__(
        self,
        *,
        models: Iterable[ModelDescriptor],
        policies: Iterable[ModelPolicy],
    ) -> None:
        catalog: dict[tuple[Provider, str], ModelDescriptor] = {}
        for descriptor in models:
            if descriptor.key in catalog:
                raise ModelConfigError(
                    f"duplicate catalog entry {descriptor.provider.value}:{descriptor.model}"
                )
            catalog[descriptor.key] = descriptor

        by_version: dict[str, ModelPolicy] = {}
        for policy in policies:
            if policy.version in by_version:
                raise ModelConfigError(f"duplicate policy version {policy.version}")
            for capability, binding in policy.all_bindings():
                entry = catalog.get((binding.provider, binding.model))
                if entry is None:
                    raise ModelConfigError(
                        f"policy {policy.version} binds {binding.label()}, "
                        "which is not in the catalog"
                    )
                if capability not in entry.capabilities:
                    raise ModelConfigError(
                        f"policy {policy.version} binds {binding.label()} for "
                        f"{capability.value}, which that model does not declare"
                    )
            for (provider, _old), new in policy.retirements.items():
                if (provider, new) not in catalog:
                    raise ModelConfigError(
                        f"policy {policy.version} retires to {new}, which is not in the catalog"
                    )
            by_version[policy.version] = policy

        self._catalog = catalog
        self._policies = by_version

    # ------------------------------------------------------------- queries --

    def policy(self, version: str) -> ModelPolicy:
        """Return the named policy, or raise."""
        policy = self._policies.get(version)
        if policy is None:
            raise ResolutionError(f"unknown model policy {version!r}", reason="unknown_policy")
        return policy

    def descriptor(self, provider: Provider, model: str) -> ModelDescriptor | None:
        """Return a catalog entry, or None."""
        return self._catalog.get((provider, model))

    def coverage(self, version: str) -> frozenset[ModelCapability]:
        """Capabilities the named policy can serve by default.

        Used to answer "can this study run at all" before it starts, the same
        question ``EgressPolicy.routes_for`` answers for residency.
        """
        return frozenset(self.policy(version).bindings)

    # ---------------------------------------------------------- resolution --

    def resolve(
        self,
        *,
        capability: ModelCapability,
        policy_version: str,
        requested_provider: Provider | None = None,
        requested_model: str | None = None,
    ) -> ModelResolution:
        """Resolve a capability to one concrete model, or raise :class:`ResolutionError`.

        Precedence: an explicit model pin, then an explicit provider choice, then
        the policy default. An explicit choice outside the policy's candidates is
        refused -- it is never replaced by the default, because that would be the
        silent substitution this whole module exists to prevent.
        """
        policy = self.policy(policy_version)
        candidates = policy.candidates(capability)
        if not candidates:
            raise ResolutionError(
                f"policy {policy_version} configures no model for {capability.value}",
                reason="capability_not_configured",
            )

        if requested_provider is not None and requested_provider not in policy.allowed_providers:
            raise ResolutionError(
                f"provider {requested_provider.value} is not allowed by policy {policy_version}",
                reason="provider_not_allowed",
            )

        substituted_from: str | None = None
        if requested_model is not None:
            wanted = requested_model.strip()
            matches = [
                b
                for b in candidates
                if requested_provider is None or b.provider is requested_provider
            ]
            chosen = next((b for b in matches if b.model == wanted), None)
            if chosen is None:
                retired_to = {
                    policy.retirements.get((b.provider, wanted))
                    for b in matches
                    if (b.provider, wanted) in policy.retirements
                }
                replacement = next(
                    (b for b in matches if b.model in retired_to),
                    None,
                )
                if replacement is None:
                    raise ResolutionError(
                        f"model {wanted!r} is not permitted for {capability.value} "
                        f"under policy {policy_version}",
                        reason="model_not_permitted",
                    )
                chosen, substituted_from = replacement, wanted
            return self._resolution(
                capability, policy, chosen, substituted_from=substituted_from, explicit=True
            )

        if requested_provider is not None:
            chosen = next((b for b in candidates if b.provider is requested_provider), None)
            if chosen is None:
                raise ResolutionError(
                    f"no {requested_provider.value} model is permitted for "
                    f"{capability.value} under policy {policy_version}",
                    reason="provider_not_permitted_for_capability",
                )
            return self._resolution(capability, policy, chosen, explicit=True)

        default = policy.bindings.get(capability)
        if default is None:
            # Only explicit choices exist for this capability. Taking the first of
            # them would be choosing on the caller's behalf.
            raise ResolutionError(
                f"policy {policy_version} has no default model for {capability.value}; "
                "an explicit choice is required",
                reason="capability_not_configured",
            )
        return self._resolution(capability, policy, default)

    def resolve_binding(
        self,
        *,
        capability: ModelCapability,
        policy_version: str,
        binding: ModelBinding,
    ) -> ModelResolution:
        """Resolve one specific binding -- used for explicitly authorised fallback.

        The binding must be a candidate of the policy for this capability. An
        authorisation to fall back does not extend to a model the policy never
        permitted.
        """
        policy = self.policy(policy_version)
        if binding not in policy.candidates(capability):
            raise ResolutionError(
                f"{binding.label()} is not permitted for {capability.value} "
                f"under policy {policy_version}",
                reason="model_not_permitted",
            )
        return self._resolution(capability, policy, binding, explicit=True)

    def _resolution(
        self,
        capability: ModelCapability,
        policy: ModelPolicy,
        binding: ModelBinding,
        *,
        substituted_from: str | None = None,
        explicit: bool = False,
    ) -> ModelResolution:
        descriptor = self._catalog[(binding.provider, binding.model)]
        return ModelResolution(
            capability=capability,
            policy_version=policy.version,
            binding=binding,
            descriptor=descriptor,
            substituted_from=substituted_from,
            explicit_choice=explicit,
        )


# --------------------------------------------------------------------------- #
# Configuration document
#
# Parsed strictly: an unknown key, a missing key or a wrong type is an error.
# Nothing is defaulted that could widen what may run.
# --------------------------------------------------------------------------- #


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class _PricingDoc(_Strict):
    input_usd_per_mtok: float
    output_usd_per_mtok: float
    cache_read_usd_per_mtok: float | None = None
    cache_write_usd_per_mtok: float | None = None


class _ModelDoc(_Strict):
    provider: Provider
    model: str
    capabilities: list[ModelCapability]
    max_output_tokens: int
    context_window_tokens: int
    pricing: _PricingDoc | None = None
    supports_strict_schema: bool = False


class _BindingDoc(_Strict):
    provider: Provider
    model: str
    route_id: str


class _RetirementDoc(_Strict):
    provider: Provider
    retired: str
    replacement: str


class _PolicyDoc(_Strict):
    version: str
    allowed_providers: list[Provider]
    bindings: dict[ModelCapability, _BindingDoc]
    permitted: dict[ModelCapability, list[_BindingDoc]] = Field(default_factory=dict)
    retirements: list[_RetirementDoc] = Field(default_factory=list)


class _ConfigDoc(_Strict):
    models: list[_ModelDoc]
    policies: list[_PolicyDoc]


def _binding(doc: _BindingDoc) -> ModelBinding:
    return ModelBinding(provider=doc.provider, model=doc.model, route_id=doc.route_id)


def parse_model_config(document: Mapping[str, Any]) -> ModelRegistry:
    """Build a :class:`ModelRegistry` from a configuration document, or raise.

    **Fails closed.** Every problem -- a malformed document, an unknown provider
    spelling, a capability bound to a model that does not declare it, an empty
    allow-list -- raises :class:`ModelConfigError`. There is no default document
    to fall back to, because the default is exactly what a broken edition file
    silently became in the reference.

    The document is validated in Pydantic's strict *JSON* mode: enum values are
    accepted as their strings, but ``"12"`` is not an integer and ``"yes"`` is not
    a boolean. A lenient parse is how a typo becomes a plausible-looking number.
    """
    try:
        doc = _ConfigDoc.model_validate_json(json.dumps(document), strict=True)
    except (TypeError, ValueError) as exc:
        # ValidationError is a ValueError; TypeError covers a document json cannot
        # serialise at all.
        raise ModelConfigError(f"invalid model configuration: {exc}") from exc

    models = [
        ModelDescriptor(
            provider=m.provider,
            model=m.model,
            capabilities=frozenset(m.capabilities),
            max_output_tokens=m.max_output_tokens,
            context_window_tokens=m.context_window_tokens,
            pricing=ModelPricing(**m.pricing.model_dump()) if m.pricing else None,
            supports_strict_schema=m.supports_strict_schema,
        )
        for m in doc.models
    ]
    policies = [
        ModelPolicy(
            version=p.version,
            allowed_providers=frozenset(p.allowed_providers),
            bindings={cap: _binding(b) for cap, b in p.bindings.items()},
            permitted={cap: tuple(_binding(b) for b in bs) for cap, bs in p.permitted.items()},
            retirements={(r.provider, r.retired): r.replacement for r in p.retirements},
        )
        for p in doc.policies
    ]
    return ModelRegistry(models=models, policies=policies)
