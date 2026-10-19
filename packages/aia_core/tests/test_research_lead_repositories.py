"""The Research Lead's two repositories: one researcher's turns, one researcher's Lead.

Every read and write is the calling researcher's (the product owner, 2026-10-19), and a
client note reaches only its own client's Study, by the query.
"""

from __future__ import annotations

import dataclasses
from typing import Any

import pytest
from sqlalchemy import select

from aia_core.domain.research_lead import DEFAULT_LEAD_NAME, DEFAULT_SOUL, RememberNote, SelfUpdate
from aia_core.domain.scope import ScopeDenied
from aia_core.infrastructure.researcher_lead_repository import (
    LeadAlreadyHatched,
    LeadNotHatched,
    ResearcherLeadRepository,
)
from aia_core.infrastructure.study_lead_repository import StudyLeadRepository
from aia_core.infrastructure.tables import ResearcherLeadMemoryRow, StudyLeadTurnRow


def _say(scope: Any, session: Any, text: str = "Ahoj") -> Any:
    return StudyLeadRepository(session, scope).append(
        actor="person", kind="message", stage="brief", text=text
    )


def test_turns_are_numbered_per_researcher_and_study(scoped: Any, session: Any) -> None:
    lead = scoped.scope(user="lead")
    other = scoped.scope(user="researcher")
    first = _say(lead, session, "jedna")
    second = _say(lead, session, "dvě")
    theirs = _say(other, session, "jejich")
    assert (first.sequence_no, second.sequence_no, theirs.sequence_no) == (1, 2, 1)
    assert first.turn_id.startswith("LDT-") and first.user_id == lead.actor_id
    assert [t.text for t in StudyLeadRepository(session, lead).turns()] == ["jedna", "dvě"]
    assert [t.text for t in StudyLeadRepository(session, other).turns()] == ["jejich"]


def test_nobody_reads_another_researchers_turns_or_another_studys(
    scoped: Any, session: Any
) -> None:
    lead = scoped.scope(user="lead")
    turn = _say(lead, session)
    for scope in (
        scoped.scope(user="researcher"),
        scoped.scope(user="lead", study="sibling"),
        scoped.scope(user="other_lead", study="other_client"),
    ):
        repo = StudyLeadRepository(session, scope)
        assert repo.turns() == [] and repo.get(turn.turn_id) is None
        assert repo.latest_lead_turn() is None
    assert StudyLeadRepository(session, lead).get(turn.turn_id) == turn


def test_turns_are_append_only(scoped: Any, session: Any) -> None:
    turn = _say(scoped.scope(), session)
    row = session.scalar(select(StudyLeadTurnRow).where(StudyLeadTurnRow.turn_id == turn.turn_id))
    row.text = "přepsáno"
    with pytest.raises(RuntimeError, match="immutable"):
        session.flush()
    session.rollback()


def test_the_turn_repository_takes_only_an_issued_study_context(scoped: Any, session: Any) -> None:
    with pytest.raises(TypeError):
        StudyLeadRepository(session, scoped.admin_context)


def test_a_lead_is_hatched_once_with_the_defaults(scoped: Any, session: Any) -> None:
    org = scoped.resolver.organization_context(scoped.principal(scoped.users["lead"]))
    repo = ResearcherLeadRepository(session, org)
    assert repo.get() is None
    lead = repo.hatch()
    assert lead.lead_id.startswith("LEAD-")
    assert (lead.name, lead.soul, lead.user) == (DEFAULT_LEAD_NAME, DEFAULT_SOUL, "")
    with pytest.raises(LeadAlreadyHatched):
        repo.hatch()
    # Another researcher's Lead is theirs: not hatched yet, and not this one.
    theirs = scoped.resolver.organization_context(scoped.principal(scoped.users["researcher"]))
    assert ResearcherLeadRepository(session, theirs).get() is None
    # Reached from a Study, it is the same researcher's Lead.
    assert ResearcherLeadRepository(session, scoped.scope(user="lead")).get() == lead


def test_a_runs_worker_actor_cannot_hatch(scoped: Any, session: Any) -> None:
    worker = dataclasses.replace(scoped.scope(), actor_id="worker:w1")
    with pytest.raises(ScopeDenied):
        ResearcherLeadRepository(session, worker).hatch()


def _hatched(scoped: Any, session: Any, user: str = "lead") -> None:
    org = scoped.resolver.organization_context(scoped.principal(scoped.users[user]))
    ResearcherLeadRepository(session, org).hatch()


def _remember(scope: Any, session: Any, *notes: tuple[str, str]) -> Any:
    update = SelfUpdate(remember=[RememberNote(scope=s, text=t) for s, t in notes])
    return ResearcherLeadRepository(session, scope).apply_self_update(
        update, source_turn_id="LDT-x"
    )


def test_a_client_note_reaches_only_its_own_clients_studies(scoped: Any, session: Any) -> None:
    """The hard rule: a client-A note never reaches a client-B turn's context."""
    _hatched(scoped, session, "lead")
    acme = scoped.scope(user="lead", study="primary")
    applied = _remember(
        acme, session, ("client", "Acme chce výsledky v pondělí."), ("personal", "Píše stručně.")
    )
    assert len(applied.remembered) == 2
    row = session.get(ResearcherLeadMemoryRow, applied.remembered[0])
    assert (row.scope, row.client_id, row.created_by) == ("client", acme.client_id, "lead")

    acme_sibling = scoped.scope(user="lead", study="sibling")
    globex = scoped.scope(user="lead", study="other_client")
    assert {n.text for n in ResearcherLeadRepository(session, acme_sibling).notes_for_study()} == {
        "Acme chce výsledky v pondělí.",
        "Píše stručně.",
    }
    assert [n.text for n in ResearcherLeadRepository(session, globex).notes_for_study()] == [
        "Píše stručně."
    ]
    # The researcher reads all of their Lead's notes, each client note with its client's name.
    org = scoped.resolver.organization_context(scoped.principal(scoped.users["lead"]))
    notes = {n.text: n for n in ResearcherLeadRepository(session, org).active_notes()}
    assert notes["Acme chce výsledky v pondělí."].client_name == "Acme Corp"
    assert notes["Píše stručně."].client_name is None


def test_a_forget_reaches_only_this_researchers_notes_this_study_may_load(
    scoped: Any, session: Any
) -> None:
    _hatched(scoped, session, "lead")
    _hatched(scoped, session, "researcher")
    acme = scoped.scope(user="lead", study="primary")
    globex = scoped.scope(user="lead", study="other_client")
    acme_note = _remember(acme, session, ("client", "Acme poznámka")).remembered[0]
    mine = _remember(acme, session, ("personal", "Moje")).remembered[0]
    theirs = _remember(scoped.scope(user="researcher"), session, ("personal", "Cizí")).remembered[0]

    # From Globex's study: Acme's note and another researcher's note are out of reach.
    applied = ResearcherLeadRepository(session, globex).apply_self_update(
        SelfUpdate(forget=[acme_note, theirs, mine]), source_turn_id="LDT-y"
    )
    assert applied.forgotten == [mine]
    assert session.get(ResearcherLeadMemoryRow, acme_note).forgotten_at is None
    assert session.get(ResearcherLeadMemoryRow, theirs).forgotten_at is None
    forgotten = session.get(ResearcherLeadMemoryRow, mine)
    assert forgotten.forgotten_at is not None  # forgetting deletes nothing
    assert mine not in {
        n.memory_id for n in ResearcherLeadRepository(session, acme).notes_for_study()
    }


def test_a_file_change_keeps_the_text_it_replaced(scoped: Any, session: Any) -> None:
    _hatched(scoped, session)
    scope = scoped.scope()
    repo = ResearcherLeadRepository(session, scope)
    applied = repo.apply_self_update(
        SelfUpdate(name="Můj vedoucí", soul="# Nová povaha", user="Pracuje ráno."),
        source_turn_id="LDT-z",
    )
    assert (applied.name, applied.soul, applied.user) == (True, True, True)
    lead = repo.get()
    assert lead is not None and (lead.name, lead.soul, lead.user) == (
        "Můj vedoucí",
        "# Nová povaha",
        "Pracuje ráno.",
    )
    revisions = repo.revisions()
    assert [(r["field"], r["previous"], r["value"]) for r in revisions] == [
        ("name", DEFAULT_LEAD_NAME, "Můj vedoucí"),
        ("soul", DEFAULT_SOUL, "# Nová povaha"),
        ("user", "", "Pracuje ráno."),
    ]
    assert {r["source_turn_id"] for r in revisions} == {"LDT-z"}
    # The same value again changes nothing and writes no revision.
    again = repo.apply_self_update(SelfUpdate(soul="# Nová povaha"), source_turn_id="LDT-w")
    assert not again.soul and len(repo.revisions()) == 3


def test_a_self_update_needs_a_hatched_lead_and_a_study(scoped: Any, session: Any) -> None:
    with pytest.raises(LeadNotHatched):
        ResearcherLeadRepository(session, scoped.scope()).apply_self_update(
            SelfUpdate(user="x"), source_turn_id="LDT-1"
        )
    _hatched(scoped, session)
    org = scoped.resolver.organization_context(scoped.principal(scoped.users["lead"]))
    with pytest.raises(TypeError):
        ResearcherLeadRepository(session, org).apply_self_update(
            SelfUpdate(user="x"), source_turn_id="LDT-1"
        )
    with pytest.raises(TypeError):
        ResearcherLeadRepository(session, org).notes_for_study()
