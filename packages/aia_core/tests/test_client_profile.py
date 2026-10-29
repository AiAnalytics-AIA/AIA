"""A client's profile and contacts (client-workspace C5).

The rules these tests pin: the profile is the client's own and starts empty; a person
who may edit it replaces it, and only a real change enters its history; contacts are
the client's, validated, and found under no other client; and nothing a study reads or
sends to a model carries a contact.
"""

from __future__ import annotations

import dataclasses
import json
from typing import Any

import pytest
from pydantic import ValidationError

from aia_core.domain.client_profile import ClientProfile, ContactDraft
from aia_core.domain.knowledge import KnowledgeKind
from aia_core.domain.research_agents import context_snapshot
from aia_core.domain.scope import ClientContext, ClientPermission, ScopeDenied
from aia_core.infrastructure.client_knowledge_repository import ClientKnowledgeRepository
from aia_core.infrastructure.client_profile_repository import ClientProfileRepository
from aia_core.infrastructure.tables import AccessAuditRow, ClientRow


@pytest.fixture
def profiles(session: Any) -> ClientProfileRepository:
    return ClientProfileRepository(session)


def client_scope(scoped: Any, user: str, client: str = "primary") -> ClientContext:
    return scoped.resolver.client_context(
        scoped.principal(scoped.users[user]), client_id=scoped.clients[client].client_id
    )


def test_a_profile_is_trimmed_and_bounded_and_empty_means_not_filled_in() -> None:
    p = ClientProfile(
        short_code="  BH ", industry="Bankovnictví,   retail", description="\n Řádek\nDalší \n"
    )
    assert (p.short_code, p.industry, p.market, p.description) == (
        "BH",
        "Bankovnictví, retail",
        "",
        "Řádek\nDalší",
    )
    with pytest.raises(ValidationError):
        ClientProfile(short_code="x" * 17)
    with pytest.raises(ValidationError):
        ClientProfile(unknown="x")  # type: ignore[call-arg]


def test_a_contact_needs_a_name_and_a_real_looking_email_if_any() -> None:
    assert ContactDraft(name=" Jana  Nová ", email="").name == "Jana Nová"
    assert ContactDraft(name="Jana", email="jana@klient.cz").email == "jana@klient.cz"
    for bad in (
        {"name": "  "},
        {"name": "Jana", "email": "jana"},
        {"name": "Jana", "email": "a b@c.cz"},
    ):
        with pytest.raises(ValidationError):
            ContactDraft(**bad)


def test_the_profile_is_the_clients_own_and_only_a_change_enters_its_history(
    scoped: Any, profiles: ClientProfileRepository, session: Any
) -> None:
    lead = client_scope(scoped, "lead")
    row = session.get(ClientRow, lead.client_id)
    before = (row.name, row.status, row.allow_self_approval)
    assert profiles.profile(lead) == ClientProfile()
    saved = profiles.update_profile(lead, ClientProfile(industry="Bankovnictví", market="Česko"))
    assert (saved.industry, saved.market) == ("Bankovnictví", "Česko")
    # The same profile again changes nothing and writes no history.
    profiles.update_profile(lead, saved)
    [change] = profiles.history(lead)
    assert change.action == "CLIENT_PROFILE_CHANGED"
    assert set(change.fields) == {"industry", "market"}
    assert change.actor_id == scoped.users["lead"]
    # Name, status and the self-approval rule stay where they are set.
    session.refresh(row)
    assert (row.name, row.status, row.allow_self_approval) == before
    # Another client's profile is untouched and its history empty.
    globex = client_scope(scoped, "other_lead", "other")
    assert profiles.profile(globex) == ClientProfile()
    assert profiles.history(globex) == []


def test_contacts_are_the_clients_own_and_their_history_never_names_an_email(
    scoped: Any, profiles: ClientProfileRepository
) -> None:
    lead = client_scope(scoped, "lead")
    jana = profiles.add_contact(
        lead,
        ContactDraft(
            name="Jana Nová", role="Marketing", email="jana@klient.cz", receives_reports=True
        ),
    )
    profiles.add_contact(lead, ContactDraft(name="adam Starý"))
    assert [c.name for c in profiles.contacts(lead)] == ["adam Starý", "Jana Nová"]
    changed = profiles.update_contact(
        lead, contact_id=jana.contact_id, draft=ContactDraft(name="Jana Nová", role="Insights")
    )
    assert (changed.role, changed.email, changed.receives_reports) == ("Insights", "", False)

    globex = client_scope(scoped, "other_lead", "other")
    assert profiles.contacts(globex) == []
    with pytest.raises(ScopeDenied):
        profiles.update_contact(globex, contact_id=jana.contact_id, draft=ContactDraft(name="x"))
    with pytest.raises(ScopeDenied):
        profiles.remove_contact(globex, contact_id=jana.contact_id)

    profiles.remove_contact(lead, contact_id=jana.contact_id)
    assert [c.name for c in profiles.contacts(lead)] == ["adam Starý"]
    history = profiles.history(lead)
    assert [h.action for h in history] == [
        "CLIENT_CONTACT_REMOVED",
        "CLIENT_CONTACT_CHANGED",
        "CLIENT_CONTACT_ADDED",
        "CLIENT_CONTACT_ADDED",
    ]
    assert "jana@klient.cz" not in json.dumps([h.model_dump(mode="json") for h in history])


def test_changing_the_profile_needs_its_permission(
    scoped: Any, profiles: ClientProfileRepository
) -> None:
    lead = client_scope(scoped, "lead")
    # Every member holds it today (ADR 0019); a narrower context is what a reader-only
    # role would be issued, so the rule is pinned against one.
    reader = dataclasses.replace(
        lead,
        permissions=frozenset(
            p for p in lead.permissions if p is not ClientPermission.EDIT_CLIENT_PROFILE
        ),
    )
    with pytest.raises(ScopeDenied):
        profiles.update_profile(reader, ClientProfile(industry="x"))
    with pytest.raises(ScopeDenied):
        profiles.add_contact(reader, ContactDraft(name="x"))
    assert profiles.profile(reader) == ClientProfile()


def test_nothing_a_study_reads_or_sends_to_a_model_carries_a_contact(
    scoped: Any, profiles: ClientProfileRepository, session: Any
) -> None:
    lead = client_scope(scoped, "lead")
    profiles.add_contact(lead, ContactDraft(name="Jana Tajná", email="jana.tajna@klient.cz"))
    knowledge = ClientKnowledgeRepository(session)
    knowledge.add(lead, kind=KnowledgeKind.FACT, title="Fakt")
    consumed = knowledge.for_study(scoped.scope(user="researcher"))
    snapshot = context_snapshot({"title": "Studie"}, consumed)
    dumped = json.dumps(snapshot, ensure_ascii=False)
    assert "jana.tajna@klient.cz" not in dumped and "Jana Tajná" not in dumped


def test_the_history_reads_budget_and_rules_by_name_and_the_budget_only_with_its_permission(
    scoped: Any, profiles: ClientProfileRepository, session: Any
) -> None:
    """CPR3: budget and rule changes join the profile's history, each naming who made it."""
    lead = client_scope(scoped, "lead")
    scoped.scope_repo.set_client_budget(lead, 25.0)
    scoped.scope_repo.set_self_approval(
        scoped.admin_context, allowed=False, client_id=lead.client_id
    )
    scoped.scope_repo.set_self_approval(
        scoped.admin_context, allowed=True, study_id=scoped.studies["primary"].study_id
    )
    history = profiles.history(lead)
    assert [h.action for h in history] == ["SELF_APPROVAL_CONFIGURED", "CLIENT_BUDGET_CHANGED"]
    [approval] = history[0].changes
    assert (approval.after, approval.before_known) == (False, False)
    [budget] = history[1].changes
    assert (budget.field, budget.before, budget.after) == ("budget_usd", 0.0, 25.0)
    assert history[1].actor_id == scoped.users["lead"]
    assert history[1].actor_name is not None and "@" not in history[1].actor_name

    # Without the budget's own permission its changes are not read.
    blind = dataclasses.replace(
        lead,
        permissions=frozenset(
            p for p in lead.permissions if p is not ClientPermission.VIEW_CLIENT_COSTS
        ),
    )
    assert [h.action for h in profiles.history(blind)] == ["SELF_APPROVAL_CONFIGURED"]
    assert profiles.history(client_scope(scoped, "other_lead", "other")) == []


def test_the_history_reads_every_value_the_writers_store_and_never_fails_on_an_odd_one(
    scoped: Any, profiles: ClientProfileRepository, session: Any
) -> None:
    """CPR3: a budget as str(float) wrote it, an inherited rule, and a value it cannot read."""
    lead = client_scope(scoped, "lead")
    scoped.scope_repo.set_client_budget(lead, 0.00001)  # its reason reads "0.0 -> 1e-05"
    scoped.scope_repo.set_self_approval(
        scoped.admin_context, allowed=None, client_id=lead.client_id
    )
    session.add(
        AccessAuditRow(
            organization_id=lead.organization_id,
            client_id=lead.client_id,
            actor_id=scoped.users["owner"],
            action="CLIENT_RULES_CHANGED",
            payload={"data_posture": {"from": ["?"], "to": "OPEN"}},
        )
    )
    session.flush()
    odd, inherit, budget = profiles.history(lead)
    assert odd.changes == ()
    assert [(c.after, c.before_known) for c in inherit.changes] == [("inherit", False)]
    assert [(c.before, c.after) for c in budget.changes] == [(0.0, 0.00001)]
