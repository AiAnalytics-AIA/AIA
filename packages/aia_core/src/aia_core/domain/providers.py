"""AI provider identity, policy and budget rules.

Typed port of the prototype's ``provider_runtime.py``. The central product rule
this module enforces is **no silent paid fallback**: when a provider cannot serve
a request, work parks in a waiting state and asks the user rather than quietly
moving to a different provider that costs money or changes provenance.

Nothing here talks to a provider SDK. Transport lives in the infrastructure layer
behind a gateway interface so that domain code never imports ``anthropic`` or
``openai`` directly.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Final

__all__ = [
    "DEFAULT_MAX_API_COST_USD",
    "PROJECT_PROVIDERS",
    "BudgetDecision",
    "ModelRole",
    "Provider",
    "ProviderPolicy",
    "check_budget",
    "normalize_policy",
    "normalize_provider",
    "policy_for_provider",
    "provider_for_stage",
    "ui_label",
]


class Provider(StrEnum):
    """Live AI providers.

    The value is the stable internal id persisted in the database and in artifact
    provenance; it must not change. The user-facing name comes from
    :func:`ui_label` -- notably ``ANTHROPIC`` is shown as "Claude API" to
    distinguish it from the Claude Code subscription runtime.
    """

    CLAUDE_CODE = "claude_code_subscription"
    ANTHROPIC = "anthropic"
    OPENAI = "openai"
    #: Amazon Bedrock, reached only over an approved route (ADR 0010). A *route*
    #: provider, not a project choice: it has no project policy and no project
    #: spelling, so a project's ``preferred_provider`` can never name it.
    AWS_BEDROCK = "aws_bedrock"


#: The providers a project may prefer and a stage may run on -- the prototype's
#: ``LIVE_PROVIDERS``. Route providers (Bedrock) are resolved by model policy, never
#: chosen per project.
PROJECT_PROVIDERS: Final[frozenset[Provider]] = frozenset(
    {Provider.CLAUDE_CODE, Provider.ANTHROPIC, Provider.OPENAI}
)


class ProviderPolicy(StrEnum):
    """How a project is permitted to choose providers across stages.

    ``CLAUDE_CODE_THEN_API`` is the only policy allowing a provider transition, and
    even then the transition is an explicit, audited user action -- it is not an
    automatic retry path.
    """

    CLAUDE_CODE_ONLY = "CLAUDE_CODE_ONLY"
    CLAUDE_API_ONLY = "CLAUDE_API_ONLY"
    OPENAI_ONLY = "OPENAI_ONLY"
    CLAUDE_CODE_THEN_API = "CLAUDE_CODE_THEN_API"


class ModelRole(StrEnum):
    """Per-stage model slots a project may configure independently."""

    RESEARCH = "research_model"
    DESIGN = "design_model"
    RESPONDENT = "respondent_model"
    ANALYSIS = "analysis_model"
    REPORT_POLISH = "report_polish_model"


DEFAULT_PROVIDER: Final = Provider.CLAUDE_CODE
DEFAULT_POLICY: Final = ProviderPolicy.CLAUDE_CODE_ONLY

# Default ceiling on paid API spend per project, from PRODUCT_POLICY.json
# (ai_runtime.default_max_api_cost_usd).
DEFAULT_MAX_API_COST_USD: Final = 10.0

_UI_LABELS: Final[dict[Provider, str]] = {
    Provider.CLAUDE_CODE: "Claude Code",
    Provider.ANTHROPIC: "Claude API",
    Provider.OPENAI: "OpenAI API",
    Provider.AWS_BEDROCK: "Amazon Bedrock",
}

# Accepted spellings for each provider. The prototype accumulated several aliases
# across builds and persisted rows may contain any of them, so normalisation has
# to keep accepting them.
_PROVIDER_ALIASES: Final[dict[str, Provider]] = {
    "claude_code_subscription": Provider.CLAUDE_CODE,
    "claude_code": Provider.CLAUDE_CODE,
    "subscription": Provider.CLAUDE_CODE,
    "anthropic": Provider.ANTHROPIC,
    "claude_api": Provider.ANTHROPIC,
    "anthropic_api": Provider.ANTHROPIC,
    "api": Provider.ANTHROPIC,
    "openai": Provider.OPENAI,
    "openai_api": Provider.OPENAI,
}

# Providers that bill per token. Claude Code runs on a subscription, so its
# marginal API cost is zero and budget checks do not apply to it.
_PAID_PROVIDERS: Final[frozenset[Provider]] = frozenset(
    {Provider.ANTHROPIC, Provider.OPENAI, Provider.AWS_BEDROCK}
)

_POLICY_FOR_PROVIDER: Final[dict[Provider, ProviderPolicy]] = {
    Provider.CLAUDE_CODE: ProviderPolicy.CLAUDE_CODE_ONLY,
    Provider.ANTHROPIC: ProviderPolicy.CLAUDE_API_ONLY,
    Provider.OPENAI: ProviderPolicy.OPENAI_ONLY,
}


def normalize_provider(value: Any, default: Provider = DEFAULT_PROVIDER) -> Provider:
    """Map any accepted spelling to a :class:`Provider`, falling back to ``default``.

    Unrecognised values resolve to the default rather than raising, but callers
    that accept user input should compare the result against the input and emit a
    ``CONFIG_NORMALIZED`` audit event when they differ -- silently retargeting a
    provider would break provenance.

    A project-selectable :class:`Provider` is returned as itself; a route provider
    (:data:`PROJECT_PROVIDERS` excludes it) has no project spelling and resolves to
    ``default`` like any unknown value, so a project can never prefer Bedrock.
    Use :func:`is_paid` and :func:`ui_label` for route providers: they take a
    :class:`Provider` as it is.
    """
    return _PROVIDER_ALIASES.get(str(value or "").strip().lower(), default)


def is_known_provider(value: Any) -> bool:
    """True when ``value`` is a spelling this system recognises."""
    return str(value or "").strip().lower() in _PROVIDER_ALIASES


def normalize_policy(value: Any, default: ProviderPolicy = DEFAULT_POLICY) -> ProviderPolicy:
    """Map a policy name to a :class:`ProviderPolicy`, falling back to ``default``."""
    try:
        return ProviderPolicy(str(value or "").strip().upper())
    except ValueError:
        return default


def policy_for_provider(provider: Any) -> ProviderPolicy:
    """Return the single-provider policy implied by a provider choice."""
    return _POLICY_FOR_PROVIDER[normalize_provider(provider)]


def _as_provider(provider: Any) -> Provider:
    """A :class:`Provider` as itself (route providers included); a spelling normalised."""
    return provider if isinstance(provider, Provider) else normalize_provider(provider)


def ui_label(provider: Any) -> str:
    """Return the user-facing provider name."""
    return _UI_LABELS[_as_provider(provider)]


def is_paid(provider: Any) -> bool:
    """True when the provider bills per token and is therefore budget-controlled.

    A route provider is judged as itself: Bedrock is metered, and normalising it
    as a project spelling would score it as the free subscription runtime.
    """
    return _as_provider(provider) in _PAID_PROVIDERS


def provider_for_stage(
    *,
    preferred_provider: Any = None,
    policy: Any = None,
    stage_override: Any = None,
    explicit_api_continue: bool = False,
) -> Provider:
    """Resolve which provider a stage runs on.

    Precedence: an explicit per-stage override, then an explicit user-authorised
    API continuation under ``CLAUDE_CODE_THEN_API``, then the policy's mandated
    provider, then the project preference.

    ``explicit_api_continue`` may only be set from a deliberate user action such as
    "continue this project on the Claude API after hitting the subscription limit".
    It is never set by a retry or an error handler; that would be exactly the
    silent paid fallback the product forbids.
    """
    resolved_policy = normalize_policy(policy)

    # DEVIATION from legacy provider_runtime.provider_for_stage: legacy accepted any
    # truthy stage_override and normalised an unrecognised one to Claude Code, which
    # could silently override an explicit CLAUDE_API_ONLY / OPENAI_ONLY policy. We
    # honour only a recognised override and otherwise let the policy decide, so a
    # typo can never retarget a project's provider. workflow_engine already emits a
    # CONFIG_NORMALIZED warning for unsupported overrides, so normalise-and-warn --
    # not break-the-policy -- is the documented intent.
    # Covered by tests/test_providers_parity.py::test_unknown_stage_override_*.
    if is_known_provider(stage_override):
        return normalize_provider(stage_override)

    if resolved_policy is ProviderPolicy.CLAUDE_API_ONLY:
        return Provider.ANTHROPIC
    if resolved_policy is ProviderPolicy.OPENAI_ONLY:
        return Provider.OPENAI
    if resolved_policy is ProviderPolicy.CLAUDE_CODE_ONLY:
        return Provider.CLAUDE_CODE
    if resolved_policy is ProviderPolicy.CLAUDE_CODE_THEN_API and explicit_api_continue:
        return Provider.ANTHROPIC

    # Under CLAUDE_CODE_THEN_API without an authorised continuation, the project's
    # own preference still chooses the starting runtime.
    return normalize_provider(preferred_provider)


@dataclass(frozen=True, slots=True)
class BudgetDecision:
    """Outcome of a pre-flight budget check for one paid call.

    ``allowed is False`` means the caller must park the job in ``WAITING_USER`` and
    request approval. It must not make the call and it must not downgrade to a
    cheaper provider on its own.
    """

    allowed: bool
    spent_usd: float
    reserved_usd: float
    estimate_usd: float
    limit_usd: float
    reason: str = ""

    @property
    def projected_usd(self) -> float:
        """Total spend if this call were to proceed."""
        return self.spent_usd + self.reserved_usd + self.estimate_usd

    @property
    def remaining_usd(self) -> float:
        """Budget headroom before this call."""
        return max(0.0, self.limit_usd - self.spent_usd - self.reserved_usd)


def check_budget(
    *,
    provider: Any,
    spent_usd: float = 0.0,
    reserved_usd: float = 0.0,
    estimate_usd: float = 0.0,
    limit_usd: float = DEFAULT_MAX_API_COST_USD,
) -> BudgetDecision:
    """Decide whether a paid call may proceed without exceeding the project budget.

    Reservations are counted as already spent so that concurrent workers cannot
    each individually pass the check and collectively overspend. Subscription
    runtimes are always allowed because they incur no marginal API cost.
    """
    resolved = _as_provider(provider)

    # Negatives are clamped rather than trusted: a bad cost record must not create
    # phantom headroom. Matches legacy api_budget_check.
    spent = max(0.0, float(spent_usd))
    reserved = max(0.0, float(reserved_usd))
    limit = max(0.0, float(limit_usd))

    if resolved not in _PAID_PROVIDERS:
        return BudgetDecision(
            allowed=True,
            spent_usd=spent,
            reserved_usd=reserved,
            estimate_usd=0.0,
            limit_usd=limit,
            reason="subscription_runtime_no_marginal_cost",
        )

    estimate = max(0.0, float(estimate_usd))
    # Spending exactly the budget is permitted; the epsilon keeps float arithmetic
    # from rejecting an exact-limit call.
    allowed = (spent + reserved + estimate) <= limit + 1e-9

    return BudgetDecision(
        allowed=allowed,
        spent_usd=spent,
        reserved_usd=reserved,
        estimate_usd=estimate,
        limit_usd=limit,
        reason="within_budget" if allowed else "budget_exceeded_requires_user_approval",
    )
