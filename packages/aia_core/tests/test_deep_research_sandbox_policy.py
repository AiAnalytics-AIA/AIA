"""A test approval reaches exactly one fictional study and leaves normal policy intact."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from sqlalchemy import select

from aia_core.domain.deep_research.settings import CATALOGUE, SettingType, pin, read_pin
from aia_core.infrastructure.deep_research_settings_repository import (
    DeepResearchSettingsReader,
    DeepResearchSettingsRepository,
    SettingRefused,
    settings_in_force_for_study,
)
from aia_core.infrastructure.deep_research_settings_repository import (
    test_approval_receipt_for_study as receipt,
)
from aia_core.infrastructure.tables import (
    AccessAuditRow,
    DeepResearchTestApprovalRow,
    DeepResearchTestPolicyRow,
    StudyRow,
)


def _values() -> dict[str, Any]:
    values: dict[str, Any] = {}
    for d in CATALOGUE:
        if not d.required_for_live:
            continue
        if d.type is SettingType.STATUS:
            values[d.key] = "approved"
        elif d.default is not None:
            values[d.key] = d.default
        elif d.type is SettingType.DECISION:
            values[d.key] = d.key.endswith("storage_and_ai_use_granted")
        elif d.type is SettingType.URL:
            values[d.key] = "https://example.org/test-permission"
        elif d.type is SettingType.DATE:
            values[d.key] = "2026-10-10"
        elif d.type is SettingType.MODEL_ID:
            values[d.key] = "eu.anthropic.claude-sonnet-4-5-20250929-v1:0"
        elif d.type is SettingType.TEXT:
            values[d.key] = "test-only"
        else:
            values[d.key] = 1
    for preset in ("standard", "deep", "exhaustive"):
        values[f"budgets.run_limit.{preset}"] = 20
    return values


@pytest.fixture
def sandbox(scoped: Any, session: Any, monkeypatch: Any) -> Any:
    scope = scoped.scope()
    monkeypatch.setenv("AIA_ENV", "develop")
    monkeypatch.setenv("AIA_AI_FICTIONAL_CLIENT_IDS", scope.client_id)
    session.get(StudyRow, scope.study_id).budget_usd = 20
    scoped.scope_repo.set_self_approval(scoped.admin_context, allowed=True)
    session.flush()
    return scope


def _propose(scoped: Any, session: Any, sandbox: Any, **changes: Any) -> str:
    args = {
        "values": _values(),
        "expires_at": datetime.now(UTC) + timedelta(hours=24),
        "budget_cap_usd": 20,
        "provider_permission": "Account owner reports provider email permits testing",
    }
    args.update(changes)
    return DeepResearchSettingsRepository(session, scoped.admin_context).propose_test_policy(
        sandbox, **args
    )


def _approve(scoped: Any, session: Any, sandbox: Any, policy_id: str, **kw: Any) -> None:
    DeepResearchSettingsRepository(session, scoped.admin_context).approve_test_policy(
        sandbox, policy_id, reason="Human authorizes this fictional study only", **kw
    )


def test_sandbox_approval_is_audited_scoped_and_pinned(
    scoped: Any, session: Any, sandbox: Any
) -> None:
    normal = DeepResearchSettingsReader(session, scoped.admin_context).effective()
    policy_id = _propose(scoped, session, sandbox)
    assert settings_in_force_for_study(session, sandbox) == normal
    _approve(scoped, session, sandbox, policy_id)
    active = settings_in_force_for_study(session, sandbox)
    assert not active.missing_for_live()
    assert read_pin(pin(active)) == active
    assert receipt(session, sandbox)["policy_id"] == policy_id
    assert receipt(session, sandbox)["budget_cap_usd"] == 20
    assert DeepResearchSettingsReader(session, scoped.admin_context).effective() == normal
    assert settings_in_force_for_study(session, scoped.scope(study="sibling")) == normal
    assert settings_in_force_for_study(session, scoped.scope(study="other_client")) == normal
    audit = list(
        session.scalars(select(AccessAuditRow).where(AccessAuditRow.action.like("DR_TEST_%")))
    )
    assert [a.action for a in audit] == ["DR_TEST_POLICY_PROPOSED", "DR_TEST_POLICY_APPROVED"]
    assert (
        audit[0].payload["values"] == session.get(DeepResearchTestPolicyRow, policy_id).values_json
    )


def test_withdrawal_never_resurrects_older_approval(
    scoped: Any, session: Any, sandbox: Any
) -> None:
    first = _propose(scoped, session, sandbox)
    _approve(scoped, session, sandbox, first)
    frozen = pin(settings_in_force_for_study(session, sandbox))
    second = _propose(scoped, session, sandbox)
    _approve(scoped, session, sandbox, second)
    _approve(scoped, session, sandbox, second, approved=False)
    assert receipt(session, sandbox) is None
    assert settings_in_force_for_study(session, sandbox).missing_for_live()
    assert not read_pin(frozen).missing_for_live()
    assert len(list(session.scalars(select(DeepResearchTestApprovalRow)))) == 3


@pytest.mark.parametrize(
    "condition",
    ["expired", "budget_raised", "allowlist_removed", "production", "staging", "unknown"],
)
def test_test_approval_refuses_when_its_conditions_cease(
    scoped: Any,
    session: Any,
    sandbox: Any,
    monkeypatch: Any,
    condition: str,
) -> None:
    policy_id = _propose(scoped, session, sandbox)
    _approve(scoped, session, sandbox, policy_id)
    if condition == "expired":
        monkeypatch.setattr(
            "aia_core.infrastructure.deep_research_settings_repository.utcnow",
            lambda: datetime.now(UTC) + timedelta(days=2),
        )
    elif condition == "budget_raised":
        session.get(StudyRow, sandbox.study_id).budget_usd = 21
        session.flush()
    elif condition == "allowlist_removed":
        monkeypatch.setenv("AIA_AI_FICTIONAL_CLIENT_IDS", "")
    else:
        monkeypatch.setenv("AIA_ENV", condition)
    assert receipt(session, sandbox) is None
    assert settings_in_force_for_study(session, sandbox).missing_for_live()


@pytest.mark.parametrize(
    "change",
    [
        "incomplete",
        "storage_false",
        "unknown_key",
        "invalid_value",
        "large_run_cap",
        "large_study_cap",
        "no_permission",
        "long_expiry",
        "naive_expiry",
    ],
)
def test_invalid_test_proposals_leave_no_record(
    scoped: Any, session: Any, sandbox: Any, change: str
) -> None:
    values = _values()
    kwargs: dict[str, Any] = {"values": values}
    if change == "incomplete":
        values.pop("provider.search.plan")
    elif change == "storage_false":
        values["provider.search.storage_and_ai_use_granted"] = False
    elif change == "unknown_key":
        values["invented"] = 1
    elif change == "invalid_value":
        values["quotas.model_input_per_minute"] = -1
    elif change == "large_run_cap":
        values["budgets.run_limit.deep"] = 21
    elif change == "large_study_cap":
        kwargs["budget_cap_usd"] = 21
    elif change == "no_permission":
        kwargs["provider_permission"] = ""
    elif change == "long_expiry":
        kwargs["expires_at"] = datetime.now(UTC) + timedelta(days=8)
    else:
        kwargs["expires_at"] = datetime.now() + timedelta(days=1)
    with pytest.raises(SettingRefused):
        _propose(scoped, session, sandbox, **kwargs)
    assert list(session.scalars(select(DeepResearchTestPolicyRow))) == []


def test_independent_review_is_preserved(scoped: Any, session: Any, sandbox: Any) -> None:
    scoped.scope_repo.set_self_approval(scoped.admin_context, allowed=False)
    policy_id = _propose(scoped, session, sandbox)
    with pytest.raises(SettingRefused, match="independent"):
        _approve(scoped, session, sandbox, policy_id)
    assert receipt(session, sandbox) is None


def test_another_study_cannot_approve_this_policy(scoped: Any, session: Any, sandbox: Any) -> None:
    policy_id = _propose(scoped, session, sandbox)
    with pytest.raises(SettingRefused):
        _approve(scoped, session, scoped.scope(study="sibling"), policy_id)


def test_tampered_policy_is_refused(scoped: Any, session: Any, sandbox: Any) -> None:
    policy_id = _propose(scoped, session, sandbox)
    _approve(scoped, session, sandbox, policy_id)
    session.get(DeepResearchTestPolicyRow, policy_id).values_json = {
        **_values(),
        "retention.snapshots": 2,
    }
    session.flush()
    with pytest.raises(SettingRefused, match="seal changed"):
        settings_in_force_for_study(session, sandbox)


def test_an_independent_admin_can_approve_without_changing_organization_policy(
    scoped: Any,
    session: Any,
    sandbox: Any,
) -> None:
    from aia_core.domain.scope import OrganizationRole

    scoped.scope_repo.set_self_approval(scoped.admin_context, allowed=False)
    policy_id = _propose(scoped, session, sandbox)
    reviewer = scoped.scope_repo.add_member(
        scoped.admin_context, email="review@example.org", role=OrganizationRole.ADMIN
    )
    context = scoped.resolver.organization_context(scoped.principal(reviewer.user_id))
    DeepResearchSettingsRepository(session, context).approve_test_policy(
        sandbox, policy_id, reason="Independent review of the scoped test permission"
    )
    assert not settings_in_force_for_study(session, sandbox).missing_for_live()
    assert receipt(session, sandbox)["approved_by"] == reviewer.user_id
    assert DeepResearchSettingsReader(session, context).effective().missing_for_live()


def test_a_run_carries_the_test_authority_receipt(scoped: Any, session: Any, sandbox: Any) -> None:
    from aia_core.application.deep_research import DeepResearchRuns, run_settings
    from aia_core.infrastructure.study_design_repository import StudyDesignRepository

    policy_id = _propose(scoped, session, sandbox)
    _approve(scoped, session, sandbox, policy_id)
    revision, _ = StudyDesignRepository(session, sandbox).submit(
        content={
            "title": "Fictional drinks",
            "goal": "Explore plant drinks",
            "research_plan": {"research_questions": ["What are plant drinks?"]},
            "sections": [
                {
                    "type": "questions",
                    "questions": [
                        {"id": "q1", "text": "Do you drink them?", "kategorie": ["Yes", "No"]}
                    ],
                }
            ],
        },
        source_stage="brief",
    )
    started = DeepResearchRuns(session, sandbox).start(
        design_revision_id=revision.revision_id, preset_name="QUICK"
    )
    metadata = started.run["metadata"]
    assert metadata["test_policy_approval"] == receipt(session, sandbox)
    assert not run_settings(metadata).missing_for_live()
    _approve(scoped, session, sandbox, policy_id, approved=False)
    assert receipt(session, sandbox) is None
    assert not run_settings(
        DeepResearchRuns(session, sandbox).get(started.run_id)["metadata"]
    ).missing_for_live()


def test_paid_enqueue_rechecks_the_study_grant(scoped: Any, session: Any, sandbox: Any) -> None:
    from aia_core.application.deep_research import DeepResearchRuns, LiveNotApproved
    from aia_core.domain.deep_research.budgets import MODEL_KINDS, CallKind, ResearchMode
    from aia_core.domain.run_cost import DeepResearchPrices, RoutePrice
    from aia_core.infrastructure.study_design_repository import StudyDesignRepository

    routes = {
        k: RoutePrice.per_call(0.001) if k in MODEL_KINDS else RoutePrice.off() for k in CallKind
    }
    routes[CallKind.SEARCH] = RoutePrice.per_call(0.005)
    routes[CallKind.FETCH] = RoutePrice.per_call(0.0)
    prices = DeepResearchPrices(routes)
    policy_id = _propose(scoped, session, sandbox)
    revision, _ = StudyDesignRepository(session, sandbox).submit(
        content={
            "title": "Fictional drinks",
            "goal": "Explore plant drinks",
            "research_plan": {"research_questions": ["What are plant drinks?"]},
            "sections": [
                {
                    "type": "questions",
                    "questions": [
                        {"id": "q1", "text": "Do you drink them?", "kategorie": ["Yes", "No"]}
                    ],
                }
            ],
        },
        source_stage="brief",
    )
    service = DeepResearchRuns(session, sandbox)

    def start() -> Any:
        return service.start(
            design_revision_id=revision.revision_id,
            preset_name="QUICK",
            prices=prices,
            modes=(ResearchMode.AGENT_DIRECTED,),
        )

    with pytest.raises(LiveNotApproved):
        start()
    _approve(scoped, session, sandbox, policy_id)
    assert start().created
    _approve(scoped, session, sandbox, policy_id, approved=False)
    with pytest.raises(LiveNotApproved):
        start()
