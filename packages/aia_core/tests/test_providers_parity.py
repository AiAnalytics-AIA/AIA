"""Parity and behaviour tests for provider resolution and budget control.

The product rule under test is **no silent paid fallback**. These tests exist so
that a future refactor cannot quietly introduce an automatic provider downgrade
or let a workflow spend past its budget.
"""

from __future__ import annotations

import itertools
from typing import Any

import pytest

from aia_core.domain.providers import (
    DEFAULT_MAX_API_COST_USD,
    PROJECT_PROVIDERS,
    Provider,
    ProviderPolicy,
    check_budget,
    is_paid,
    normalize_policy,
    normalize_provider,
    policy_for_provider,
    provider_for_stage,
    ui_label,
)

PROVIDER_SPELLINGS = [
    "claude_code_subscription",
    "claude_code",
    "subscription",
    "anthropic",
    "claude_api",
    "anthropic_api",
    "api",
    "openai",
    "openai_api",
    "CLAUDE_CODE",
    "  anthropic  ",
    "",
    None,
    "garbage",
    "local",
]

POLICY_SPELLINGS = [
    "CLAUDE_CODE_ONLY",
    "CLAUDE_API_ONLY",
    "OPENAI_ONLY",
    "CLAUDE_CODE_THEN_API",
    "claude_code_only",
    "",
    None,
    "NONSENSE",
]


# --------------------------------------------------------------------------- #
# Parity against the legacy prototype
# --------------------------------------------------------------------------- #


@pytest.mark.parity
def test_provider_ids_match_legacy(legacy_provider_runtime: Any) -> None:
    """Internal provider ids are persisted in provenance and must not drift."""
    lr = legacy_provider_runtime
    assert Provider.CLAUDE_CODE.value == lr.CLAUDE_CODE
    assert Provider.ANTHROPIC.value == lr.CLAUDE_API
    assert Provider.OPENAI.value == lr.OPENAI
    # Project-selectable providers are the prototype's LIVE_PROVIDERS exactly; a
    # route provider (Bedrock, ADR 0010) is AIA's own and is never a project choice.
    assert {p.value for p in PROJECT_PROVIDERS} == lr.LIVE_PROVIDERS
    assert {p.value for p in ProviderPolicy} == lr.POLICIES


@pytest.mark.parity
def test_ui_labels_match_legacy(legacy_provider_runtime: Any) -> None:
    """'anthropic' must keep displaying as 'Claude API', not 'Anthropic'."""
    for spelling in PROVIDER_SPELLINGS:
        assert ui_label(spelling) == legacy_provider_runtime.ui_provider(spelling)


@pytest.mark.parity
def test_normalize_provider_matches_legacy(legacy_provider_runtime: Any) -> None:
    """Every accepted alias must resolve the same way as legacy."""
    for spelling in PROVIDER_SPELLINGS:
        assert normalize_provider(spelling).value == (
            legacy_provider_runtime.normalize_live_provider(spelling)
        ), f"provider normalisation mismatch for {spelling!r}"


@pytest.mark.parity
def test_normalize_policy_matches_legacy(legacy_provider_runtime: Any) -> None:
    """Policy normalisation, including the fallback, must match legacy."""
    for spelling in POLICY_SPELLINGS:
        assert normalize_policy(spelling).value == (
            legacy_provider_runtime.normalize_policy(spelling)
        ), f"policy normalisation mismatch for {spelling!r}"


@pytest.mark.parity
def test_policy_for_provider_matches_legacy(legacy_provider_runtime: Any) -> None:
    """The implied single-provider policy must match legacy."""
    for spelling in PROVIDER_SPELLINGS:
        assert policy_for_provider(spelling).value == (
            legacy_provider_runtime.policy_for_provider(spelling)
        )


@pytest.mark.parity
def test_provider_for_stage_matches_legacy_for_known_inputs(
    legacy_provider_runtime: Any,
) -> None:
    """Stage provider resolution must match legacy across the full input matrix.

    Unrecognised stage overrides are excluded here and covered separately: that is
    our one documented deviation.
    """
    known_overrides = [
        None,
        "",
        "claude_code",
        "anthropic",
        "openai",
        "api",
        "claude_code_subscription",
    ]
    matrix = itertools.product(
        ["claude_code_subscription", "anthropic", "openai", None, "garbage"],
        POLICY_SPELLINGS,
        known_overrides,
        [False, True],
    )
    for preferred, policy, override, explicit in matrix:
        mine = provider_for_stage(
            preferred_provider=preferred,
            policy=policy,
            stage_override=override,
            explicit_api_continue=explicit,
        )
        theirs = legacy_provider_runtime.provider_for_stage(
            preferred_provider=preferred,
            policy=policy,
            stage_override=override,
            explicit_api_continue=explicit,
        )
        assert mine.value == theirs, (
            f"provider_for_stage mismatch: preferred={preferred!r} policy={policy!r} "
            f"override={override!r} explicit={explicit}"
        )


@pytest.mark.parity
def test_budget_check_matches_legacy_for_paid_providers(
    legacy_provider_runtime: Any,
) -> None:
    """Budget arithmetic must match legacy exactly, including the boundary."""
    cases = [
        (0.0, 0.0, 0.0, 10.0),
        (5.0, 0.0, 4.0, 10.0),
        (5.0, 0.0, 5.0, 10.0),  # exactly at the limit -> allowed
        (5.0, 0.0, 5.01, 10.0),
        (9.0, 1.0, 0.5, 10.0),
        (0.0, 0.0, 10.0, 10.0),
        (0.0, 0.0, 0.0, 0.0),
        (0.0, 0.0, 0.01, 0.0),
        (3.0, 3.0, 3.0, 10.0),
        (3.0, 3.0, 4.0, 10.0),
        (0.1, 0.2, 0.3, 0.6),  # float accumulation at the boundary
    ]
    for spent, reserved, estimate, limit in cases:
        mine = check_budget(
            provider=Provider.ANTHROPIC,
            spent_usd=spent,
            reserved_usd=reserved,
            estimate_usd=estimate,
            limit_usd=limit,
        )
        theirs = legacy_provider_runtime.api_budget_check(
            spent_usd=spent,
            reserved_usd=reserved,
            estimate_usd=estimate,
            max_api_cost_usd=limit,
        )
        assert mine.allowed == theirs["allowed"], (
            f"budget decision mismatch for spent={spent} reserved={reserved} "
            f"estimate={estimate} limit={limit}"
        )
        assert round(mine.projected_usd, 6) == theirs["projected_usd"]
        assert round(mine.remaining_usd, 6) == theirs["remaining_usd"]
        assert round(mine.limit_usd, 6) == theirs["max_api_cost_usd"]


@pytest.mark.parity
@pytest.mark.parametrize(
    ("spent", "reserved", "estimate", "limit"),
    [(-3.0, 0.0, 1.0, 10.0), (1.0, -2.0, 1.0, 10.0), (-5.0, -5.0, 0.0, 10.0)],
)
def test_negative_cost_records_do_not_inflate_remaining_budget(
    legacy_provider_runtime: Any, spent: float, reserved: float, estimate: float, limit: float
) -> None:
    """A corrupt negative cost record must not create budget headroom.

    DEVIATION from legacy api_budget_check: legacy clamped negatives when computing
    ``projected_usd`` but not when computing ``remaining_usd``, so a spend of -3.0
    against a $10 cap reported $13 remaining -- more headroom than the cap allows.
    The allow/deny decision was unaffected, but the figure is surfaced to users and
    to cost dashboards, so we clamp consistently and never report more than the cap.
    """
    theirs = legacy_provider_runtime.api_budget_check(
        spent_usd=spent, reserved_usd=reserved, estimate_usd=estimate, max_api_cost_usd=limit
    )
    mine = check_budget(
        provider=Provider.ANTHROPIC,
        spent_usd=spent,
        reserved_usd=reserved,
        estimate_usd=estimate,
        limit_usd=limit,
    )

    # The decision itself still agrees; only the reported headroom differs.
    assert mine.allowed == theirs["allowed"]
    assert theirs["remaining_usd"] > limit, "legacy behaviour changed; revisit deviation"
    assert mine.remaining_usd <= limit


@pytest.mark.parity
def test_default_budget_matches_product_policy(legacy_provider_runtime: Any) -> None:
    """The default ceiling comes from PRODUCT_POLICY.json and must not drift."""
    assert DEFAULT_MAX_API_COST_USD == 10.0
    signature = legacy_provider_runtime.api_budget_check.__defaults__
    assert signature is None or DEFAULT_MAX_API_COST_USD == 10.0


# --------------------------------------------------------------------------- #
# Documented deviation
# --------------------------------------------------------------------------- #


@pytest.mark.parity
def test_unknown_stage_override_no_longer_breaks_policy(
    legacy_provider_runtime: Any,
) -> None:
    """An unrecognised stage override must not silently retarget the provider.

    Legacy normalised any truthy override to Claude Code, so a typo on a project
    pinned to CLAUDE_API_ONLY silently moved that stage onto the subscription
    runtime -- changing both cost and provenance. We ignore the bad override and
    honour the policy instead.
    """
    legacy = legacy_provider_runtime.provider_for_stage(
        preferred_provider="anthropic", policy="CLAUDE_API_ONLY", stage_override="typo"
    )
    assert legacy == Provider.CLAUDE_CODE.value, "legacy behaviour changed; revisit deviation"

    mine = provider_for_stage(
        preferred_provider="anthropic", policy="CLAUDE_API_ONLY", stage_override="typo"
    )
    assert mine is Provider.ANTHROPIC


def test_unknown_stage_override_falls_back_to_policy() -> None:
    """The deviation applies to every policy, not just CLAUDE_API_ONLY."""
    assert provider_for_stage(policy="OPENAI_ONLY", stage_override="nope") is Provider.OPENAI
    assert (
        provider_for_stage(policy="CLAUDE_CODE_ONLY", stage_override="nope") is Provider.CLAUDE_CODE
    )


# --------------------------------------------------------------------------- #
# Behaviour tests
# --------------------------------------------------------------------------- #


def test_no_silent_fallback_from_claude_code_to_paid_api() -> None:
    """Under CLAUDE_CODE_THEN_API, paid API use requires an explicit continuation.

    This is the anti-fallback guarantee. Without ``explicit_api_continue`` the
    resolver must stay on the subscription runtime even though the policy permits
    an eventual transition.
    """
    stay = provider_for_stage(
        preferred_provider="claude_code_subscription", policy="CLAUDE_CODE_THEN_API"
    )
    assert stay is Provider.CLAUDE_CODE

    move = provider_for_stage(
        preferred_provider="claude_code_subscription",
        policy="CLAUDE_CODE_THEN_API",
        explicit_api_continue=True,
    )
    assert move is Provider.ANTHROPIC


def test_single_provider_policies_ignore_preference() -> None:
    """A pinned policy must win over a conflicting project preference."""
    assert provider_for_stage(preferred_provider="openai", policy="CLAUDE_API_ONLY") is (
        Provider.ANTHROPIC
    )
    assert provider_for_stage(preferred_provider="anthropic", policy="OPENAI_ONLY") is (
        Provider.OPENAI
    )
    assert provider_for_stage(preferred_provider="openai", policy="CLAUDE_CODE_ONLY") is (
        Provider.CLAUDE_CODE
    )


def test_subscription_runtime_is_never_budget_blocked() -> None:
    """Claude Code has no marginal API cost, so budget never blocks it."""
    decision = check_budget(
        provider=Provider.CLAUDE_CODE, spent_usd=999.0, estimate_usd=999.0, limit_usd=1.0
    )
    assert decision.allowed
    assert decision.reason == "subscription_runtime_no_marginal_cost"


def test_reservations_prevent_concurrent_overspend() -> None:
    """Reserved funds count as spent so parallel workers cannot both pass.

    Without this, two workers each seeing $6 spent against a $10 cap would both
    approve a $3 call and together spend $12.
    """
    decision = check_budget(
        provider=Provider.ANTHROPIC,
        spent_usd=6.0,
        reserved_usd=3.0,
        estimate_usd=3.0,
        limit_usd=10.0,
    )
    assert not decision.allowed
    assert decision.reason == "budget_exceeded_requires_user_approval"
    assert decision.remaining_usd == pytest.approx(1.0)


def test_budget_denial_is_explicit_not_a_downgrade() -> None:
    """A denied budget check reports a reason for user approval, not an alternative.

    The decision object intentionally carries no 'suggested_provider' field: the
    caller must park the job and ask, never choose a cheaper provider on its own.
    """
    decision = check_budget(provider=Provider.OPENAI, spent_usd=50.0, estimate_usd=1.0)
    assert not decision.allowed
    assert not hasattr(decision, "suggested_provider")
    assert not hasattr(decision, "fallback_provider")


def test_paid_provider_classification() -> None:
    """Only token-billed providers are budget-controlled."""
    assert is_paid(Provider.ANTHROPIC)
    assert is_paid(Provider.OPENAI)
    assert not is_paid(Provider.CLAUDE_CODE)


def test_budget_decision_is_immutable() -> None:
    """A budget decision must not be mutated after the fact."""
    decision = check_budget(provider=Provider.ANTHROPIC, estimate_usd=1.0)
    with pytest.raises((AttributeError, TypeError)):
        decision.allowed = False  # type: ignore[misc]


# --------------------------------------------------------------------------- #
# Route providers (ADR 0010): metered, never a project choice
# --------------------------------------------------------------------------- #


def test_bedrock_is_metered_and_budget_checked() -> None:
    assert is_paid(Provider.AWS_BEDROCK)
    refused = check_budget(
        provider=Provider.AWS_BEDROCK, spent_usd=0.9, estimate_usd=0.2, limit_usd=1
    )
    assert not refused.allowed
    assert ui_label(Provider.AWS_BEDROCK) == "Amazon Bedrock"


def test_a_project_can_never_prefer_bedrock() -> None:
    assert Provider.AWS_BEDROCK not in PROJECT_PROVIDERS
    for spelling in ("aws_bedrock", "bedrock", Provider.AWS_BEDROCK):
        assert normalize_provider(spelling) is Provider.CLAUDE_CODE
