"""Hatching with the person's yes (lead-identity LI1; ADR 0030 decision 2): a pending hatch is no
Lead until "Přijmout", is checked again as it is kept, can be set aside, and the request is
refused by name until the AIA organization exists to pay for it."""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError
from sqlalchemy import select

from aia_core.application.membership import deactivate_member
from aia_core.application.research_lead import (
    LeadHatchRefused,
    LeadHatchUnavailable,
    LeadProfile,
)
from aia_core.infrastructure.researcher_lead_repository import (
    LeadAlreadyHatched,
    LeadHatchNotPending,
    ResearcherLeadRepository,
)
from aia_core.infrastructure.tables import AccessAuditRow, utcnow

TRAITS = {"tone": "vecny", "answers": "strucne", "initiative": "ceka", "numbers": "vzdy_nejistota"}
WRITTEN = {"name": "Ada", "traits": TRAITS, "brief": "Buď věcná.", "about": ""}
ANSWER = {"soul": "# Ada\n- Mluvím věcně.", "user": "", "greeting": "Ahoj, jsem Ada."}


def _org(scoped: Any, user: str = "lead") -> Any:
    return scoped.resolver.organization_context(scoped.principal(scoped.users[user]))


def _pending(scoped: Any, session: Any, answer: dict[str, Any] | None = ANSWER) -> tuple[Any, str]:
    org = _org(scoped)
    repo = ResearcherLeadRepository(session, org)
    hatch = repo.record_hatch(WRITTEN)
    if answer is not None:
        repo.answer_hatch(hatch.hatch_id, answer, run_id="RUN-test0001")
    return org, hatch.hatch_id


def test_a_pending_hatch_is_no_lead_until_the_person_accepts(scoped: Any, session: Any) -> None:
    org, hatch_id = _pending(scoped, session)
    profile = LeadProfile(session, org)
    read = profile.read()
    assert read["hatched"] is False and read["lead"] is None
    assert read["pending_hatch"]["hatch_id"] == hatch_id
    assert read["pending_hatch"]["output"] == ANSWER
    assert ResearcherLeadRepository(session, org).get() is None

    accepted = profile.accept_hatch(hatch_id)
    assert accepted["greeting"] == "Ahoj, jsem Ada."
    lead = accepted["lead"]
    assert (lead["name"], lead["files"]["soul"], lead["files"]["user"]) == (
        "Ada",
        ANSWER["soul"],
        "",
    )
    assert profile.read()["hatched"] is True
    assert session.scalars(
        select(AccessAuditRow.action).where(AccessAuditRow.action == "LEAD_HATCH_ACCEPTED")
    ).all() == ["LEAD_HATCH_ACCEPTED"]
    # Accepted once: the hatch no longer waits, and a Lead is hatched once.
    with pytest.raises(LeadHatchNotPending):
        profile.accept_hatch(hatch_id)
    with pytest.raises(LeadAlreadyHatched):
        ResearcherLeadRepository(session, org).record_hatch(WRITTEN)


def test_a_hatch_the_model_has_not_answered_cannot_be_accepted(scoped: Any, session: Any) -> None:
    org, hatch_id = _pending(scoped, session, answer=None)
    with pytest.raises(LeadHatchNotPending):
        LeadProfile(session, org).accept_hatch(hatch_id)


def test_a_file_naming_a_client_is_refused_as_it_is_kept(scoped: Any, session: Any) -> None:
    # "Acme Corp" is a client of the fixture's organization.
    org, hatch_id = _pending(scoped, session, {**ANSWER, "user": "Pracuje pro Acme Corp."})
    with pytest.raises(LeadHatchRefused) as refused:
        LeadProfile(session, org).accept_hatch(hatch_id)
    assert refused.value.files == {"user": "client_fact_in_personal_file"}
    assert ResearcherLeadRepository(session, org).get() is None


def test_zadat_znovu_sets_the_hatch_aside_and_keeps_nothing(scoped: Any, session: Any) -> None:
    org, hatch_id = _pending(scoped, session)
    read = LeadProfile(session, org).discard_hatch(hatch_id)
    assert read == {"hatched": False, "lead": None, "pending_hatch": None}
    with pytest.raises(LeadHatchNotPending):
        LeadProfile(session, org).accept_hatch(hatch_id)
    # The person may write again.
    assert ResearcherLeadRepository(session, org).record_hatch(WRITTEN).hatch_id != hatch_id


def test_one_hatch_waits_at_a_time_and_only_the_callers(scoped: Any, session: Any) -> None:
    org, hatch_id = _pending(scoped, session)
    with pytest.raises(LeadHatchNotPending):
        ResearcherLeadRepository(session, org).record_hatch(WRITTEN)
    other = _org(scoped, "researcher")
    assert LeadProfile(session, other).read()["pending_hatch"] is None
    with pytest.raises(LeadHatchNotPending):
        LeadProfile(session, other).accept_hatch(hatch_id)
    with pytest.raises(LeadHatchNotPending):
        LeadProfile(session, other).discard_hatch(hatch_id)


def test_asking_the_model_is_refused_by_name_with_nothing_kept(scoped: Any, session: Any) -> None:
    org = _org(scoped)
    with pytest.raises(LeadHatchUnavailable):
        LeadProfile(session, org).request_hatch(WRITTEN)
    assert ResearcherLeadRepository(session, org).pending_hatch() is None
    # A wrong input is said before the missing payer.
    with pytest.raises(ValidationError):
        LeadProfile(session, org).request_hatch({**WRITTEN, "traits": {**TRAITS, "tone": "x"}})


def test_a_deactivated_members_hatch_goes_with_their_membership(scoped: Any, session: Any) -> None:
    org, _ = _pending(scoped, session)
    deactivate_member(session, scoped.admin_context, user_id=org.actor_id, now=utcnow())
    assert ResearcherLeadRepository(session, org).pending_hatch() is None


def test_a_chosen_name_naming_a_client_is_refused_as_it_is_kept(scoped: Any, session: Any) -> None:
    """Review of #919 (Codex): the name goes into every study's context with the files, so ADR
    0030 decision 3's check holds it too, however clean the model's answer is."""
    org = _org(scoped)
    repo = ResearcherLeadRepository(session, org)
    hatch = repo.record_hatch({**WRITTEN, "name": "Acme Corp"})
    repo.answer_hatch(hatch.hatch_id, ANSWER, run_id="RUN-test0001")
    with pytest.raises(LeadHatchRefused) as refused:
        LeadProfile(session, org).accept_hatch(hatch.hatch_id)
    assert refused.value.files == {"name": "client_fact_in_personal_file"}
    assert ResearcherLeadRepository(session, org).get() is None
