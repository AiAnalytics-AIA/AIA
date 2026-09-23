"""Model catalog, policy and registry: capability resolution that fails closed.

The properties under test are the ones a convenient gateway library would
quietly give up: a capability with no configured model is refused rather than
served by "whatever is available"; a pinned model outside the policy is refused
rather than replaced; a malformed configuration is an error rather than a
permissive default.
"""

from __future__ import annotations

import math
from typing import Any

import pytest

from aia_core.domain.ai_models import (
    ModelBinding,
    ModelCapability,
    ModelConfigError,
    ModelDescriptor,
    ModelPolicy,
    ModelPricing,
    ModelRegistry,
    ResolutionError,
    parse_model_config,
)
from aia_core.domain.providers import Provider

POLICY = "policy-test-v1"


# --------------------------------------------------------------------------- #
# Pricing
# --------------------------------------------------------------------------- #


def test_cost_prices_each_token_path_separately() -> None:
    pricing = ModelPricing(
        input_usd_per_mtok=3.0,
        output_usd_per_mtok=15.0,
        cache_read_usd_per_mtok=0.3,
        cache_write_usd_per_mtok=3.75,
    )
    cost = pricing.cost_usd(
        input_tokens=1_000_000,
        output_tokens=100_000,
        cache_read_input_tokens=2_000_000,
        cache_write_input_tokens=400_000,
    )
    assert math.isclose(cost, 3.0 + 1.5 + 0.6 + 1.5)


def test_unknown_cache_discount_is_charged_at_the_full_input_rate() -> None:
    """An undeclared discount is not assumed. Unknown is not scored as good."""
    pricing = ModelPricing(input_usd_per_mtok=2.0, output_usd_per_mtok=8.0)
    cost = pricing.cost_usd(input_tokens=0, output_tokens=0, cache_read_input_tokens=1_000_000)
    assert math.isclose(cost, 2.0)


def test_ceiling_assumes_all_input_uncached_and_all_output_used() -> None:
    pricing = ModelPricing(
        input_usd_per_mtok=3.0, output_usd_per_mtok=15.0, cache_write_usd_per_mtok=3.75
    )
    # The dearest input path is the cache write, so the ceiling uses it.
    assert math.isclose(
        pricing.ceiling_usd(max_input_tokens=1_000_000, max_output_tokens=1_000_000), 18.75
    )


@pytest.mark.parametrize("bad", [-1.0, math.inf, math.nan])
def test_pricing_rejects_implausible_prices(bad: float) -> None:
    with pytest.raises(ModelConfigError):
        ModelPricing(input_usd_per_mtok=bad, output_usd_per_mtok=1.0)


def test_negative_token_counts_are_rejected() -> None:
    pricing = ModelPricing(input_usd_per_mtok=1.0, output_usd_per_mtok=1.0)
    with pytest.raises(ValueError):
        pricing.cost_usd(input_tokens=-1, output_tokens=0)


# --------------------------------------------------------------------------- #
# Catalog entries
# --------------------------------------------------------------------------- #


def test_metered_model_without_pricing_is_refused() -> None:
    """A paid model with no price would estimate every call at zero."""
    with pytest.raises(ModelConfigError, match="must declare pricing"):
        ModelDescriptor(
            provider=Provider.ANTHROPIC,
            model="m",
            capabilities=frozenset({ModelCapability.CRITIC}),
            max_output_tokens=10,
            context_window_tokens=100,
        )


def test_subscription_model_needs_no_pricing() -> None:
    descriptor = ModelDescriptor(
        provider=Provider.CLAUDE_CODE,
        model="m",
        capabilities=frozenset({ModelCapability.CRITIC}),
        max_output_tokens=10,
        context_window_tokens=100,
    )
    assert descriptor.is_paid is False


@pytest.mark.parametrize(
    "kwargs",
    [
        {"model": " "},
        {"capabilities": frozenset()},
        {"max_output_tokens": 0},
        {"context_window_tokens": -1},
    ],
)
def test_descriptor_rejects_unusable_entries(kwargs: dict[str, Any]) -> None:
    base: dict[str, Any] = {
        "provider": Provider.CLAUDE_CODE,
        "model": "m",
        "capabilities": frozenset({ModelCapability.CRITIC}),
        "max_output_tokens": 10,
        "context_window_tokens": 100,
    }
    with pytest.raises(ModelConfigError):
        ModelDescriptor(**{**base, **kwargs})


# --------------------------------------------------------------------------- #
# Policy
# --------------------------------------------------------------------------- #


def _binding(provider: Provider = Provider.ANTHROPIC, model: str = "m") -> ModelBinding:
    return ModelBinding(provider=provider, model=model, route_id="r")


def test_empty_provider_allow_list_is_not_all_providers() -> None:
    """The reference's malformed edition file enabled everything. An empty list
    here enables nothing, and is refused so nobody mistakes it for a default."""
    with pytest.raises(ModelConfigError, match="allows no providers"):
        ModelPolicy(version="v", allowed_providers=frozenset(), bindings={})


def test_policy_cannot_bind_a_provider_outside_its_allow_list() -> None:
    with pytest.raises(ModelConfigError, match="allow-list"):
        ModelPolicy(
            version="v",
            allowed_providers=frozenset({Provider.CLAUDE_CODE}),
            bindings={ModelCapability.CRITIC: _binding(Provider.OPENAI)},
        )


def test_policy_cannot_bind_a_retired_model() -> None:
    with pytest.raises(ModelConfigError, match="retired"):
        ModelPolicy(
            version="v",
            allowed_providers=frozenset({Provider.ANTHROPIC}),
            bindings={ModelCapability.CRITIC: _binding(model="old")},
            retirements={(Provider.ANTHROPIC, "old"): "new"},
        )


def test_retirement_chains_are_refused() -> None:
    """A chain would make the effective model depend on lookup order."""
    with pytest.raises(ModelConfigError, match="itself retired"):
        ModelPolicy(
            version="v",
            allowed_providers=frozenset({Provider.ANTHROPIC}),
            bindings={},
            retirements={(Provider.ANTHROPIC, "a"): "b", (Provider.ANTHROPIC, "b"): "c"},
        )


def test_a_model_cannot_retire_to_itself() -> None:
    with pytest.raises(ModelConfigError):
        ModelPolicy(
            version="v",
            allowed_providers=frozenset({Provider.ANTHROPIC}),
            bindings={},
            retirements={(Provider.ANTHROPIC, "a"): "a"},
        )


def test_binding_needs_model_and_route() -> None:
    with pytest.raises(ModelConfigError):
        ModelBinding(provider=Provider.ANTHROPIC, model="m", route_id=" ")


# --------------------------------------------------------------------------- #
# Registry construction
# --------------------------------------------------------------------------- #


def test_registry_refuses_a_binding_to_a_model_not_in_the_catalog(
    model_config_document: dict[str, Any],
) -> None:
    model_config_document["policies"][0]["bindings"]["CRITIC"]["model"] = "not-in-catalog"
    with pytest.raises(ModelConfigError, match="not in the catalog"):
        parse_model_config(model_config_document)


def test_registry_refuses_a_capability_the_model_does_not_declare(
    model_config_document: dict[str, Any],
) -> None:
    """extraction-small does not declare REPORT_WRITING, so it cannot serve it."""
    model_config_document["policies"][0]["bindings"]["REPORT_WRITING"] = {
        "provider": "openai",
        "model": "extraction-small",
        "route_id": "openai-direct",
    }
    with pytest.raises(ModelConfigError, match="does not declare"):
        parse_model_config(model_config_document)


def test_registry_refuses_a_retirement_to_an_unknown_model(
    model_config_document: dict[str, Any],
) -> None:
    model_config_document["policies"][0]["retirements"][0]["replacement"] = "ghost"
    with pytest.raises(ModelConfigError, match="not in the catalog"):
        parse_model_config(model_config_document)


def test_registry_refuses_duplicates(model_config_document: dict[str, Any]) -> None:
    doubled = dict(model_config_document)
    doubled["models"] = [*model_config_document["models"], model_config_document["models"][0]]
    with pytest.raises(ModelConfigError, match="duplicate catalog"):
        parse_model_config(doubled)

    doubled = dict(model_config_document)
    doubled["policies"] = [*model_config_document["policies"] * 2]
    with pytest.raises(ModelConfigError, match="duplicate policy"):
        parse_model_config(doubled)


# --------------------------------------------------------------------------- #
# Configuration parsing fails closed
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "mutate",
    [
        pytest.param(lambda d: d.pop("policies"), id="missing-policies"),
        pytest.param(lambda d: d.update(extra=True), id="unknown-top-level-key"),
        pytest.param(
            lambda d: d["models"][0].update(provider="claude_api_typo"), id="unknown-provider"
        ),
        pytest.param(
            lambda d: d["models"][0].update(max_output_tokens="8192"), id="numeric-string"
        ),
        pytest.param(
            lambda d: d["models"][2].update(supports_strict_schema="yes"), id="truthy-string"
        ),
        pytest.param(
            lambda d: d["policies"][0]["bindings"].update(TELEPATHY={}),
            id="unknown-capability",
        ),
        pytest.param(lambda d: d["policies"][0].pop("allowed_providers"), id="missing-allow-list"),
        pytest.param(
            lambda d: d["policies"][0].update(allowed_providers=[]), id="empty-allow-list"
        ),
        pytest.param(lambda d: d["models"][0].pop("pricing"), id="paid-model-unpriced"),
    ],
)
def test_malformed_configuration_is_an_error_not_a_default(
    model_config_document: dict[str, Any], mutate: Any
) -> None:
    """Every one of these, in the reference's edition loader, became 'all on'."""
    mutate(model_config_document)
    with pytest.raises(ModelConfigError):
        parse_model_config(model_config_document)


def test_unserialisable_configuration_is_an_error() -> None:
    with pytest.raises(ModelConfigError):
        parse_model_config({"models": [object()], "policies": []})


# --------------------------------------------------------------------------- #
# Resolution
# --------------------------------------------------------------------------- #


def test_default_binding_resolves(model_registry: ModelRegistry) -> None:
    resolution = model_registry.resolve(
        capability=ModelCapability.RESEARCH_REASONING, policy_version=POLICY
    )
    assert resolution.provider is Provider.ANTHROPIC
    assert resolution.model == "reasoning-large-v2"
    assert resolution.route_id == "anthropic-direct"
    assert resolution.policy_version == POLICY
    assert resolution.substituted_from is None
    assert resolution.explicit_choice is False
    assert resolution.descriptor.is_paid is True


def test_unconfigured_capability_fails_closed(model_registry: ModelRegistry) -> None:
    """No model for EMBEDDING means no call -- not 'whatever is available'."""
    with pytest.raises(ResolutionError) as exc:
        model_registry.resolve(capability=ModelCapability.EMBEDDING, policy_version=POLICY)
    assert exc.value.reason == "capability_not_configured"


def test_unknown_policy_version_fails_closed(model_registry: ModelRegistry) -> None:
    with pytest.raises(ResolutionError) as exc:
        model_registry.resolve(capability=ModelCapability.CRITIC, policy_version="nope")
    assert exc.value.reason == "unknown_policy"


def test_pinned_model_resolves_when_permitted(model_registry: ModelRegistry) -> None:
    resolution = model_registry.resolve(
        capability=ModelCapability.CRITIC,
        policy_version=POLICY,
        requested_model="reasoning-large-v2",
    )
    assert resolution.provider is Provider.ANTHROPIC
    assert resolution.explicit_choice is True


def test_pinned_model_outside_the_policy_is_refused_not_replaced(
    model_registry: ModelRegistry,
) -> None:
    """extraction-small exists in the catalog but is not permitted for research."""
    with pytest.raises(ResolutionError) as exc:
        model_registry.resolve(
            capability=ModelCapability.RESEARCH_REASONING,
            policy_version=POLICY,
            requested_model="extraction-small",
        )
    assert exc.value.reason == "model_not_permitted"
    assert not hasattr(exc.value, "suggested_model")


def test_retired_pin_is_substituted_only_by_declared_retirement_and_recorded(
    model_registry: ModelRegistry,
) -> None:
    resolution = model_registry.resolve(
        capability=ModelCapability.RESEARCH_REASONING,
        policy_version=POLICY,
        requested_model="reasoning-large",
    )
    assert resolution.model == "reasoning-large-v2"
    assert resolution.substituted_from == "reasoning-large"


def test_retirement_does_not_cross_providers(model_registry: ModelRegistry) -> None:
    """The retirement is declared for anthropic. Pinning the same id against
    another provider is not a retirement, it is an unknown model."""
    with pytest.raises(ResolutionError) as exc:
        model_registry.resolve(
            capability=ModelCapability.RESEARCH_REASONING,
            policy_version=POLICY,
            requested_provider=Provider.CLAUDE_CODE,
            requested_model="reasoning-large",
        )
    assert exc.value.reason == "model_not_permitted"


def test_explicit_provider_choice_resolves_to_that_providers_candidate(
    model_registry: ModelRegistry,
) -> None:
    resolution = model_registry.resolve(
        capability=ModelCapability.RESEARCH_REASONING,
        policy_version=POLICY,
        requested_provider=Provider.CLAUDE_CODE,
    )
    assert resolution.provider is Provider.CLAUDE_CODE
    assert resolution.route_id == "claude-code-cli"
    assert resolution.explicit_choice is True


def test_explicit_provider_with_no_candidate_is_refused(model_registry: ModelRegistry) -> None:
    """OpenAI is allowed by the policy but serves no research model. The request
    is refused; the anthropic default is not silently used instead."""
    with pytest.raises(ResolutionError) as exc:
        model_registry.resolve(
            capability=ModelCapability.RESEARCH_REASONING,
            policy_version=POLICY,
            requested_provider=Provider.OPENAI,
        )
    assert exc.value.reason == "provider_not_permitted_for_capability"


def test_provider_outside_the_allow_list_is_refused(
    model_config_document: dict[str, Any],
) -> None:
    policy = model_config_document["policies"][0]
    policy["allowed_providers"] = ["anthropic", "openai"]
    policy["permitted"].pop("RESEARCH_REASONING")
    registry = parse_model_config(model_config_document)
    with pytest.raises(ResolutionError) as exc:
        registry.resolve(
            capability=ModelCapability.RESEARCH_REASONING,
            policy_version=POLICY,
            requested_provider=Provider.CLAUDE_CODE,
        )
    assert exc.value.reason == "provider_not_allowed"


def test_capability_with_only_explicit_candidates_requires_a_choice() -> None:
    registry = ModelRegistry(
        models=[
            ModelDescriptor(
                provider=Provider.CLAUDE_CODE,
                model="m",
                capabilities=frozenset({ModelCapability.CRITIC}),
                max_output_tokens=10,
                context_window_tokens=100,
            )
        ],
        policies=[
            ModelPolicy(
                version="v",
                allowed_providers=frozenset({Provider.CLAUDE_CODE}),
                bindings={},
                permitted={ModelCapability.CRITIC: (_binding(Provider.CLAUDE_CODE),)},
            )
        ],
    )
    with pytest.raises(ResolutionError) as exc:
        registry.resolve(capability=ModelCapability.CRITIC, policy_version="v")
    assert exc.value.reason == "capability_not_configured"
    chosen = registry.resolve(
        capability=ModelCapability.CRITIC,
        policy_version="v",
        requested_provider=Provider.CLAUDE_CODE,
    )
    assert chosen.model == "m"


def test_resolve_binding_accepts_only_policy_candidates(model_registry: ModelRegistry) -> None:
    ok = model_registry.resolve_binding(
        capability=ModelCapability.CRITIC,
        policy_version=POLICY,
        binding=ModelBinding(
            provider=Provider.ANTHROPIC, model="reasoning-large-v2", route_id="anthropic-direct"
        ),
    )
    assert ok.explicit_choice is True

    with pytest.raises(ResolutionError) as exc:
        model_registry.resolve_binding(
            capability=ModelCapability.CRITIC,
            policy_version=POLICY,
            # Right model, different route: a different residency answer.
            binding=ModelBinding(
                provider=Provider.ANTHROPIC, model="reasoning-large-v2", route_id="elsewhere"
            ),
        )
    assert exc.value.reason == "model_not_permitted"


def test_coverage_lists_default_capabilities(model_registry: ModelRegistry) -> None:
    assert model_registry.coverage(POLICY) == frozenset(
        {
            ModelCapability.RESEARCH_REASONING,
            ModelCapability.FAST_EXTRACTION,
            ModelCapability.CRITIC,
        }
    )
    assert model_registry.descriptor(Provider.OPENAI, "extraction-small") is not None
    assert model_registry.descriptor(Provider.OPENAI, "ghost") is None
