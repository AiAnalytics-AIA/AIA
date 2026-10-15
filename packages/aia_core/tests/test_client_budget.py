"""A client's own budget (client-budget CB1).

The rules these tests pin: a client's budget starts at 0, so client-paid work waits for a
person rather than presuming an allowance; it is read only behind VIEW_CLIENT_COSTS and set
only behind MANAGE_CLIENT_BUDGET; every real change is audited with the old and new value;
and it is the client's alone, never its studies' budgets and never another client's.
"""

from __future__ import annotations

import dataclasses
from typing import Any

import pytest
from pydantic import ValidationError
from sqlalchemy import select

from aia_core.domain.scope import ClientBudget, ClientContext, ClientPermission, ScopeDenied
from aia_core.infrastructure.scope_repository import ScopeRepository
from aia_core.infrastructure.tables import AccessAuditRow, StudyRow


def client_scope(scoped: Any, user: str = "lead", client: str = "primary") -> ClientContext:
    return scoped.resolver.client_context(
        scoped.principal(scoped.users[user]), client_id=scoped.clients[client].client_id
    )


def test_available_is_what_is_left_after_spend_and_holds_never_below_zero() -> None:
    assert ClientBudget(budget_usd=10, spent_usd=3, reserved_usd=2).available_usd == 5
    assert ClientBudget(budget_usd=1, spent_usd=3).available_usd == 0
    with pytest.raises(ValidationError):
        ClientBudget(budget_usd=-1, spent_usd=0)


def test_a_client_starts_with_nothing_to_spend(scoped: Any, session: Any) -> None:
    budget = ScopeRepository(session).client_budget(client_scope(scoped))
    assert budget == ClientBudget(budget_usd=0, spent_usd=0, reserved_usd=0)
    assert budget.available_usd == 0


def test_setting_it_is_audited_once_per_real_change_and_touches_no_study(
    scoped: Any, session: Any
) -> None:
    repo = ScopeRepository(session)
    lead = client_scope(scoped)
    studies_before = {
        r.study_id: r.budget_usd
        for r in session.scalars(select(StudyRow).where(StudyRow.client_id == lead.client_id))
    }
    assert repo.set_client_budget(lead, 25.5).budget_usd == 25.5
    repo.set_client_budget(lead, 25.5)  # the same value again is not a change
    repo.set_client_budget(lead, 0)  # lowering it is allowed
    audits = session.scalars(
        select(AccessAuditRow)
        .where(AccessAuditRow.action == "CLIENT_BUDGET_CHANGED")
        .order_by(AccessAuditRow.event_id)
    ).all()
    assert [(a.reason, a.client_id, a.study_id, a.actor_id) for a in audits] == [
        ("0.0 -> 25.5", lead.client_id, None, scoped.users["lead"]),
        ("25.5 -> 0.0", lead.client_id, None, scoped.users["lead"]),
    ]
    studies_after = {
        r.study_id: r.budget_usd
        for r in session.scalars(select(StudyRow).where(StudyRow.client_id == lead.client_id))
    }
    assert studies_after == studies_before
    with pytest.raises(ValueError):
        repo.set_client_budget(lead, -1)


def test_it_is_the_clients_own(scoped: Any, session: Any) -> None:
    repo = ScopeRepository(session)
    repo.set_client_budget(client_scope(scoped), 40)
    other = client_scope(scoped, "other_lead", "other")
    assert repo.client_budget(other).budget_usd == 0


def test_reading_and_setting_need_their_permissions(scoped: Any, session: Any) -> None:
    repo = ScopeRepository(session)
    lead = client_scope(scoped)
    assert lead.has(ClientPermission.VIEW_CLIENT_COSTS)
    assert lead.has(ClientPermission.MANAGE_CLIENT_BUDGET)
    blind = dataclasses.replace(lead, permissions=frozenset({ClientPermission.VIEW_CLIENT}))
    with pytest.raises(ScopeDenied):
        repo.client_budget(blind)
    viewer = dataclasses.replace(
        lead,
        permissions=frozenset({ClientPermission.VIEW_CLIENT, ClientPermission.VIEW_CLIENT_COSTS}),
    )
    assert repo.client_budget(viewer).budget_usd == 0
    with pytest.raises(ScopeDenied):
        repo.set_client_budget(viewer, 5)
