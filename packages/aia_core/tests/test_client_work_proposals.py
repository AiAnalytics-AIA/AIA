"""What a run of the client's own work reads and files (lifecycle K2d2).

It reads exactly the reading it was queued with -- a source read again since is refused,
another client's source is not found -- and files its proposals once: proposals, never
knowledge, marked as the AI's, naming the run; a retried step files nothing twice.
"""

from __future__ import annotations

from typing import Any

import pytest
from sqlalchemy.orm import Session

from aia_core.domain.client_sources import SourceFamily
from aia_core.domain.knowledge import KnowledgeKind, ProposalDraft, ProposalOrigin, ProposalStatus
from aia_core.domain.scope import ClientContext, ClientWorkContext, ScopeDenied
from aia_core.infrastructure.client_knowledge_repository import ClientKnowledgeRepository
from aia_core.infrastructure.client_source_repository import (
    ClientSourceRepository,
    SourceReadingChanged,
)
from aia_core.infrastructure.storage import InMemoryArtifactStore
from aia_core.infrastructure.tables import ClientSourceRow


def scopes(
    scoped: Any, user: str = "lead", client: str = "primary"
) -> tuple[ClientContext, ClientWorkContext]:
    principal = scoped.principal(scoped.users[user])
    client_id = scoped.clients[client].client_id
    return (
        scoped.resolver.client_context(principal, client_id=client_id),
        scoped.resolver.client_work_context(principal, client_id=client_id),
    )


def test_a_run_reads_exactly_the_reading_it_was_queued_with(scoped: Any, session: Session) -> None:
    sources = ClientSourceRepository(session, InMemoryArtifactStore())
    person, work = scopes(scoped)
    kept, _ = sources.add(person, filename="zadani.md", data="Klient vede trh pojištění.".encode())
    pin = sources.reading_pin(person, kept.source_id)
    assert (pin.family, pin.segments) == (SourceFamily.DOCUMENT, 1)
    assert pin.reading_sha256 is not None

    record, reading = sources.pinned_reading(
        work, kept.source_id, reading_sha256=pin.reading_sha256
    )
    assert record.source_id == kept.source_id
    assert [s.text for s in reading.segments] == ["Klient vede trh pojištění."]

    # Read again since: the run is not handed a reading nobody asked about.
    row = session.get(ClientSourceRow, kept.source_id)
    assert row is not None
    row.reading_sha256 = "0" * 64
    session.flush()
    with pytest.raises(SourceReadingChanged):
        sources.pinned_reading(work, kept.source_id, reading_sha256=pin.reading_sha256)

    # Another client's work does not find it; a person's scope does not read here.
    _, other = scopes(scoped, "other_lead", "other")
    with pytest.raises(ScopeDenied):
        sources.pinned_reading(other, kept.source_id, reading_sha256="0" * 64)
    with pytest.raises(ScopeDenied):
        sources.pinned_reading(person, kept.source_id, reading_sha256="0" * 64)  # type: ignore[arg-type]


def draft(title: str) -> ProposalDraft:
    return ProposalDraft(
        kind=KnowledgeKind.FACT,
        title=title,
        summary="Shrnutí.",
        content={"quote": "Klient vede trh.", "locator": {"page": 1}},
        provenance={"source_id": "SRC-0000000000000001", "locator": {"page": 1}},
    )


def test_a_run_files_its_proposals_once_as_the_ais_and_never_as_knowledge(
    scoped: Any, session: Session
) -> None:
    knowledge = ClientKnowledgeRepository(session)
    person, work = scopes(scoped)
    filed = knowledge.propose_from_client_work(
        work, run_id="RUN-aaaa", drafts=[draft("Vede trh"), draft("Druhý")]
    )
    assert [p.title for p in filed] == ["Vede trh", "Druhý"]
    for p in filed:
        assert (p.status, p.origin, p.study_id, p.item_id) == (
            ProposalStatus.PROPOSED,
            ProposalOrigin.CLIENT,
            None,
            None,
        )
        assert p.provenance["authored"] == "ai"
        assert p.provenance["run_id"] == "RUN-aaaa"
        assert p.proposed_by == scoped.users["lead"]
    assert knowledge.items(person) == []

    # The step retried: what the run filed comes back, nothing is written twice.
    again = knowledge.propose_from_client_work(work, run_id="RUN-aaaa", drafts=[draft("Nový")])
    assert [p.proposal_id for p in again] == [p.proposal_id for p in filed]
    assert len(knowledge.proposals(person, status=ProposalStatus.PROPOSED)) == 2

    with pytest.raises(ScopeDenied):
        knowledge.propose_from_client_work(person, run_id="RUN-b", drafts=[draft("x")])  # type: ignore[arg-type]
