"""Live needs approval: a run on a priced live route waits for its organization's sign-off.

ADR 0022 decision 6, plan ``deep-research-web-search.md`` chunk 44. A route needs the sign-off
when it is live and priced (the owner's call of 2026-10-09: the fee-free routes -- Czech
Wikipedia, the public fetch, the connectors -- run as they do). At enqueue a new run is refused,
naming every key live still needs, until the enqueuing organization has approved them; another
organization's approvals never count; a withdrawal refuses again. The worker checks the run's pin
once more before anything is asked (``test_deep_research_journey.py``).
"""

from __future__ import annotations

from typing import Any

import pytest

from aia_core.application.deep_research import DeepResearchRuns, LiveNotApproved
from aia_core.domain.deep_research.budgets import MODEL_KINDS, CallKind
from aia_core.domain.deep_research.contracts import RetrievalMode
from aia_core.domain.deep_research.settings import (
    CATALOGUE,
    SettingDefinition,
    SettingType,
    effective,
)
from aia_core.domain.deep_research.tooling import ToolKind, ToolRoute
from aia_core.domain.residency import ProviderRoute
from aia_core.domain.run_cost import DeepResearchPrices, RoutePrice
from aia_core.infrastructure.deep_research_settings_repository import (
    DeepResearchSettingsRepository,
)
from aia_core.infrastructure.study_design_repository import StudyDesignRepository

DESIGN: dict[str, Any] = {
    "title": "Rostlinné nápoje",
    "goal": "Zjistit, kdo v Česku pije rostlinné nápoje a proč.",
    "research_plan": {"research_questions": ["Jak roste trh rostlinných nápojů v Česku?"]},
    "sections": [],
}

REQUIRED = effective({}).missing_for_live()
#: A setting live needs that shapes no result: withdrawing it changes no request.
TERMS = "provider.search.terms_url"


def _prices(search_usd: float) -> DeepResearchPrices:
    every = {k: RoutePrice.per_call(0.5) for k in MODEL_KINDS}
    every.update({k: RoutePrice.off() for k in CallKind if k not in MODEL_KINDS})
    every[CallKind.SEARCH] = RoutePrice.per_call(search_usd)
    every[CallKind.FETCH] = RoutePrice.per_call(0.0)
    return DeepResearchPrices(every)


PAID, FREE = _prices(0.005), _prices(0.0)


def _valid(defn: SettingDefinition) -> Any:
    """A value the catalogue accepts for ``defn``: fictional, for these tests only."""
    by_type: dict[SettingType, Any] = {
        SettingType.TEXT: "Fiktivní plán",
        SettingType.URL: "https://example.org/terms",
        SettingType.DATE: "2026-10-09",
        SettingType.USD: 1.0,
        SettingType.DAYS: 30,
        SettingType.INTEGER: 10,
        SettingType.DECISION: True,
        SettingType.STATUS: "approved",
        SettingType.MODEL_ID: "eu.anthropic.example-model-v1:0",
    }
    if defn.default is not None:
        return "approved" if defn.type is SettingType.STATUS else defn.default
    return by_type[defn.type]


def _approve(scoped: Any, session: Any, keys: tuple[str, ...], admin: Any = None) -> None:
    repo = DeepResearchSettingsRepository(session, admin or scoped.admin_context)
    by_key = {d.key: d for d in CATALOGUE}
    for key in keys:
        repo.approve(key, repo.propose(key, _valid(by_key[key])).version_number)


@pytest.fixture
def start(session: Any, scoped: Any) -> Any:
    def go(prices: DeepResearchPrices | None, title: str = "Rostlinné nápoje") -> Any:
        scope = scoped.scope(user="lead")
        revision, _ = StudyDesignRepository(session, scope).submit(
            content={**DESIGN, "title": title}, source_stage="brief"
        )
        return DeepResearchRuns(session, scope).start(
            design_revision_id=revision.revision_id, preset_name="QUICK", prices=prices
        )

    return go


# ------------------------------------------------------------------ the routes


def _route(mode: RetrievalMode, price: float) -> ToolRoute:
    return ToolRoute(
        route=ProviderRoute(route_id="example-search", provider="example"),
        tool=ToolKind.WEB_SEARCH,
        adapter_id="example-search-1",
        retrieval_mode=mode,
        price_usd_per_call=price,
    )


def test_only_a_live_route_with_a_price_needs_the_sign_off() -> None:
    assert _route(RetrievalMode.LIVE, 0.005).needs_sign_off
    assert not _route(RetrievalMode.LIVE, 0.0).needs_sign_off  # Wikipedia, the connectors
    assert not _route(RetrievalMode.RECORDED, 0.0).needs_sign_off
    assert PAID.paid_routes() == (CallKind.SEARCH,)
    assert FREE.paid_routes() == ()


def test_the_catalogue_names_what_live_needs() -> None:
    assert REQUIRED  # the provider's terms and price, the sign-offs, budgets, the light model
    assert (
        "provider.search.terms_url" in REQUIRED and "limits.verifier.answer_tokens" not in REQUIRED
    )


# ------------------------------------------------------------------ at enqueue


def test_a_paid_route_is_refused_until_every_live_setting_is_approved(
    start: Any, scoped: Any, session: Any
) -> None:
    with pytest.raises(LiveNotApproved) as refused:
        start(PAID)
    assert refused.value.missing == REQUIRED and refused.value.kinds == ("search",)
    _approve(scoped, session, REQUIRED[:-1])
    with pytest.raises(LiveNotApproved) as still:
        start(PAID)
    assert still.value.missing == REQUIRED[-1:]
    _approve(scoped, session, REQUIRED[-1:])
    assert start(PAID).created


def test_a_withdrawal_refuses_the_next_start_again(start: Any, scoped: Any, session: Any) -> None:
    _approve(scoped, session, REQUIRED)
    assert start(PAID).created
    DeepResearchSettingsRepository(session, scoped.admin_context).approve(TERMS, None)
    with pytest.raises(LiveNotApproved) as refused:
        start(PAID, title="Rostlinné nápoje II")
    assert refused.value.missing == (TERMS,)


def test_fee_free_and_unpriced_starts_need_no_sign_off(start: Any) -> None:
    assert start(FREE).created
    assert start(None, title="Bez cen").created


def test_another_organizations_approvals_never_admit_this_one(
    start: Any, scoped: Any, session: Any
) -> None:
    from dataclasses import replace

    other_org, other_owner = scoped.scope_repo.create_organization(
        slug="other", name="Other", owner_email="o@example.org", owner_name="O"
    )
    owner = scoped.resolver.organization_context(
        replace(scoped.principal(other_owner.user_id), organization_id=other_org.organization_id)
    )
    _approve(scoped, session, REQUIRED, admin=owner)
    with pytest.raises(LiveNotApproved):
        start(PAID)


def test_a_start_that_finds_its_run_asks_nothing(start: Any, scoped: Any, session: Any) -> None:
    """The refusal is for creating a run: one already enqueued is returned as it is."""
    _approve(scoped, session, REQUIRED)
    first = start(PAID)
    DeepResearchSettingsRepository(session, scoped.admin_context).approve(TERMS, None)
    again = start(PAID)
    assert again.run_id == first.run_id and not again.created
