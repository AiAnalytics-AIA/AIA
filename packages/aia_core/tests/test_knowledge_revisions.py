"""Typed knowledge revisions and decisions (client-knowledge-lifecycle K3).

The rules these tests pin: every proposal says who wrote it and every decision what was
decided; an approval is checked against the revision the reviewer named as well as the one
the edit was written from (F-K1, widened); an AI revision keeps the evidence it rested on
after it is accepted; a record from before these were kept reads unknown, never a guess.
"""

from __future__ import annotations

from typing import Any

import pytest
from sqlalchemy.orm import Session

from aia_core.domain.knowledge import (
    KnowledgeAuthor,
    KnowledgeDecision,
    KnowledgeKind,
    NoRevisionToReview,
    ProposalDraft,
    ProposalStatus,
    RevisionEvidence,
    StaleKnowledgeProposal,
    author_of,
    evidence_of,
    reviewed_decision,
    revision_sha256,
)
from aia_core.domain.scope import ClientContext
from aia_core.infrastructure.client_knowledge_repository import ClientKnowledgeRepository
from aia_core.infrastructure.tables import ClientKnowledgeProposalRow

# ------------------------------------------------------------------------- the pure rules


@pytest.mark.parametrize(
    ("base", "reviewed", "current", "expected"),
    [
        (2, None, 2, KnowledgeDecision.ACCEPTED),
        (2, 2, 2, KnowledgeDecision.ACCEPTED),
        (1, 2, 2, KnowledgeDecision.ACCEPTED_OVER),
        (None, 2, 2, KnowledgeDecision.ACCEPTED_OVER),
        (1, None, 2, "stale"),
        (None, None, 2, "stale"),
        (1, 1, 2, "stale"),
        # The edit is current, but the reviewer read an older item: stale (K3).
        (3, 2, 3, "stale"),
        (3, 4, 3, "stale"),
    ],
)
def test_an_approval_is_decided_against_the_base_and_the_revision_the_reviewer_named(
    base: int | None, reviewed: int | None, current: int, expected: object
) -> None:
    def decide() -> KnowledgeDecision:
        return reviewed_decision(
            item_id="KNW-1",
            base_revision=base,
            reviewed_revision=reviewed,
            current_revision=current,
        )

    if expected == "stale":
        with pytest.raises(StaleKnowledgeProposal) as refused:
            decide()
        assert refused.value.current_revision == current
        assert refused.value.reviewed_revision == reviewed
    else:
        assert decide() is expected


def test_a_new_item_has_no_revision_to_review() -> None:
    assert (
        reviewed_decision(
            item_id=None, base_revision=None, reviewed_revision=None, current_revision=None
        )
        is KnowledgeDecision.ACCEPTED
    )
    with pytest.raises(NoRevisionToReview):
        reviewed_decision(
            item_id=None, base_revision=None, reviewed_revision=1, current_revision=None
        )


def test_the_author_is_read_as_stored_else_from_explicit_markers_else_unknown() -> None:
    assert author_of("AI", {"authored": "person"}) is KnowledgeAuthor.AI
    assert author_of(None, {"authored": "ai"}) is KnowledgeAuthor.AI
    assert author_of(None, {"authored": "person"}) is KnowledgeAuthor.PERSON
    assert author_of(None, {"study_id": "STD-1"}) is KnowledgeAuthor.STUDY
    # Nothing said: unknown, never presumed a person's.
    assert author_of(None, {}) is KnowledgeAuthor.UNKNOWN
    assert author_of(None, {"authored": "robot", "study_id": ""}) is KnowledgeAuthor.UNKNOWN


def test_evidence_is_an_ai_records_whole_grounding_or_none() -> None:
    provenance = {
        "source_id": "SRC-0000000000000001",
        "source_sha256": "a" * 64,
        "reading_sha256": "b" * 64,
        "segment": 3,
        "run_id": "RUN-1",
    }
    content = {"quote": "Klient vede trh.", "locator": {"page": 2}}
    assert evidence_of(KnowledgeAuthor.AI, provenance, content) == RevisionEvidence(
        source_id="SRC-0000000000000001",
        quote="Klient vede trh.",
        locator={"page": 2},
        source_sha256="a" * 64,
        reading_sha256="b" * 64,
        segment=3,
        run_id="RUN-1",
    )
    # A person's or a study's record has none, whatever it carries.
    assert evidence_of(KnowledgeAuthor.PERSON, provenance, content) is None
    # A part of a grounding is no grounding.
    assert evidence_of(KnowledgeAuthor.AI, provenance, {"quote": "Klient vede trh."}) is None
    assert evidence_of(KnowledgeAuthor.AI, {"run_id": "RUN-1"}, content) is None
    # A segment that is not a whole number is not kept as one.
    odd = evidence_of(KnowledgeAuthor.AI, {**provenance, "segment": True}, content)
    assert odd is not None and odd.segment is None


def test_a_revisions_hash_is_its_words_in_canonical_form() -> None:
    one = revision_sha256("Dealeři", "", {"b": 1, "a": [1, "ž"]})
    assert one == revision_sha256("Dealeři", "", {"a": [1, "ž"], "b": 1})
    assert one != revision_sha256("Dealeři", " ", {"a": [1, "ž"], "b": 1})
    assert one != revision_sha256("Dealeři", "", {"a": [1, "z"], "b": 1})
    # Pinned: the canonical form is a contract a frozen context (K4) relies on.
    assert revision_sha256("a", "", {}) == (
        "b1e4f0d425cd6c44cb3193f414ce7331c72a3d23393dc8046a1451b26cbcf1f0"
    )


# ---------------------------------------------------------------------- the repository


@pytest.fixture
def knowledge(session: Session) -> ClientKnowledgeRepository:
    return ClientKnowledgeRepository(session)


def client_scope(scoped: Any, user: str, client: str = "primary") -> ClientContext:
    return scoped.resolver.client_context(
        scoped.principal(scoped.users[user]), client_id=scoped.clients[client].client_id
    )


def test_every_proposal_says_who_wrote_it_and_every_decision_what_was_decided(
    scoped: Any, knowledge: ClientKnowledgeRepository
) -> None:
    researcher = client_scope(scoped, "researcher")
    reviewer = client_scope(scoped, "reviewer")
    written = knowledge.add(researcher, kind=KnowledgeKind.FACT, title="Dealeři: 120")
    assert (written.author, written.decision) == (
        KnowledgeAuthor.PERSON,
        KnowledgeDecision.AUTHORED,
    )
    from_study = knowledge.propose_from_study(
        scoped.scope(user="researcher"), kind=KnowledgeKind.FINDING, title="Cena rozhoduje"
    )
    assert (from_study.author, from_study.decision) == (KnowledgeAuthor.STUDY, None)
    accepted = knowledge.decide(reviewer, proposal_id=from_study.proposal_id, approve=True)
    assert accepted.decision is KnowledgeDecision.ACCEPTED
    proposed = knowledge.propose(researcher, kind=KnowledgeKind.TERM, title="Flotila")
    assert proposed.author is KnowledgeAuthor.PERSON
    rejected = knowledge.decide(reviewer, proposal_id=proposed.proposal_id, approve=False)
    assert (rejected.status, rejected.decision) == (
        ProposalStatus.REJECTED,
        KnowledgeDecision.REJECTED,
    )
    [revision] = knowledge.revisions(reviewer, item_id=accepted.item_id or "")
    assert (revision.author, revision.decision) == (
        KnowledgeAuthor.STUDY,
        KnowledgeDecision.ACCEPTED,
    )
    assert revision.evidence is None
    assert revision.sha256 == revision_sha256(revision.title, revision.summary, revision.content)


def _edit_of_the_current_revision(
    scoped: Any, knowledge: ClientKnowledgeRepository
) -> tuple[str, str]:
    """A FACT corrected to revision 2, then a study's edit written from revision 2."""
    researcher = client_scope(scoped, "researcher")
    first = knowledge.add(researcher, kind=KnowledgeKind.FACT, title="Dealeři: 120")
    assert first.item_id is not None
    knowledge.add(researcher, kind=KnowledgeKind.FACT, title="Dealeři: 134", item_id=first.item_id)
    edit = knowledge.propose_from_study(
        scoped.scope(user="researcher"),
        kind=KnowledgeKind.FACT,
        title="Dealeři: 140",
        item_id=first.item_id,
    )
    assert edit.base_revision == 2
    return first.item_id, edit.proposal_id


def test_a_reviewer_who_read_an_older_revision_is_refused_even_when_the_edit_is_current(
    scoped: Any, knowledge: ClientKnowledgeRepository
) -> None:
    item_id, proposal_id = _edit_of_the_current_revision(scoped, knowledge)
    reviewer = client_scope(scoped, "reviewer")
    with pytest.raises(StaleKnowledgeProposal) as refused:
        knowledge.decide(reviewer, proposal_id=proposal_id, approve=True, reviewed_revision=1)
    assert (refused.value.base_revision, refused.value.current_revision) == (2, 2)
    assert refused.value.reviewed_revision == 1
    [item] = knowledge.items(reviewer)
    assert (item.title, item.revision) == ("Dealeři: 134", 2)
    [pending] = knowledge.proposals(reviewer, status=ProposalStatus.PROPOSED)
    assert (pending.decision, pending.reviewed_revision) == (None, None)

    decided = knowledge.decide(reviewer, proposal_id=proposal_id, approve=True, reviewed_revision=2)
    assert (decided.decision, decided.reviewed_revision) == (KnowledgeDecision.ACCEPTED, 2)
    latest = knowledge.revisions(reviewer, item_id=item_id)[-1]
    assert (latest.revision, latest.base_revision, latest.reviewed_revision) == (3, 2, 2)


def test_an_accept_over_a_newer_revision_reads_back_as_one(
    scoped: Any, knowledge: ClientKnowledgeRepository
) -> None:
    researcher = client_scope(scoped, "researcher")
    first = knowledge.add(researcher, kind=KnowledgeKind.FACT, title="Dealeři: 120")
    assert first.item_id is not None
    edit = knowledge.propose_from_study(
        scoped.scope(user="researcher"),
        kind=KnowledgeKind.FACT,
        title="Dealeři: 125",
        item_id=first.item_id,
    )
    knowledge.add(researcher, kind=KnowledgeKind.FACT, title="Dealeři: 134", item_id=first.item_id)
    reviewer = client_scope(scoped, "reviewer")
    decided = knowledge.decide(
        reviewer, proposal_id=edit.proposal_id, approve=True, reviewed_revision=2
    )
    assert decided.decision is KnowledgeDecision.ACCEPTED_OVER
    history = knowledge.revisions(reviewer, item_id=first.item_id)
    assert [(r.revision, r.decision) for r in history] == [
        (1, KnowledgeDecision.AUTHORED),
        (2, KnowledgeDecision.AUTHORED),
        (3, KnowledgeDecision.ACCEPTED_OVER),
    ]
    assert (history[-1].base_revision, history[-1].reviewed_revision) == (1, 2)
    # The two hashes of different words differ; the history is three distinct texts.
    assert len({r.sha256 for r in history}) == 3


def test_naming_a_revision_for_a_new_item_is_refused_and_decides_nothing(
    scoped: Any, knowledge: ClientKnowledgeRepository
) -> None:
    proposal = knowledge.propose_from_study(
        scoped.scope(user="researcher"), kind=KnowledgeKind.FINDING, title="Cena rozhoduje"
    )
    reviewer = client_scope(scoped, "reviewer")
    for approve in (True, False):
        with pytest.raises(NoRevisionToReview):
            knowledge.decide(
                reviewer, proposal_id=proposal.proposal_id, approve=approve, reviewed_revision=1
            )
    [pending] = knowledge.proposals(reviewer, status=ProposalStatus.PROPOSED)
    assert pending.proposal_id == proposal.proposal_id


def test_a_rejection_records_the_revision_it_names_and_is_never_stale(
    scoped: Any, knowledge: ClientKnowledgeRepository
) -> None:
    _, proposal_id = _edit_of_the_current_revision(scoped, knowledge)
    reviewer = client_scope(scoped, "reviewer")
    # A bool is not a revision, though Python counts True as 1.
    with pytest.raises(NoRevisionToReview):
        knowledge.decide(
            reviewer,
            proposal_id=proposal_id,
            approve=False,
            reviewed_revision=True,
        )
    # A revision the item never had is not recorded, on a rejection either (item at 2).
    for never in (3, 99):
        with pytest.raises(NoRevisionToReview):
            knowledge.decide(
                reviewer, proposal_id=proposal_id, approve=False, reviewed_revision=never
            )
    [pending] = knowledge.proposals(reviewer, status=ProposalStatus.PROPOSED)
    assert pending.proposal_id == proposal_id
    # An older revision the item did have is recorded as named: a rejection is never stale.
    rejected = knowledge.decide(
        reviewer, proposal_id=proposal_id, approve=False, reviewed_revision=1
    )
    assert (rejected.decision, rejected.reviewed_revision) == (KnowledgeDecision.REJECTED, 1)


def test_an_ai_revision_keeps_its_evidence_after_it_is_accepted(
    scoped: Any, knowledge: ClientKnowledgeRepository
) -> None:
    """F089: the quote, its place and its document survive the accept, typed."""
    person = client_scope(scoped, "lead")
    work = scoped.resolver.client_work_context(
        scoped.principal(scoped.users["lead"]), client_id=scoped.clients["primary"].client_id
    )
    [filed] = knowledge.propose_from_client_work(
        work,
        run_id="RUN-aaaa",
        drafts=[
            ProposalDraft(
                kind=KnowledgeKind.FACT,
                title="Vede trh",
                summary="Klient je jedničkou trhu.",
                content={"quote": "Klient vede trh.", "locator": {"page": 1}},
                provenance={
                    "source_id": "SRC-0000000000000001",
                    "source_sha256": "a" * 64,
                    "reading_sha256": "b" * 64,
                    "segment": 0,
                },
            )
        ],
    )
    assert filed.author is KnowledgeAuthor.AI
    decided = knowledge.decide(person, proposal_id=filed.proposal_id, approve=True)
    assert decided.decision is KnowledgeDecision.ACCEPTED
    [revision] = knowledge.revisions(person, item_id=decided.item_id or "")
    assert revision.author is KnowledgeAuthor.AI
    assert revision.evidence == RevisionEvidence(
        source_id="SRC-0000000000000001",
        quote="Klient vede trh.",
        locator={"page": 1},
        source_sha256="a" * 64,
        reading_sha256="b" * 64,
        segment=0,
        run_id="RUN-aaaa",
    )
    [recent] = knowledge.recent_revisions(person)
    assert recent.evidence == revision.evidence


def test_a_record_from_before_k3_reads_unknown_never_a_guess(
    scoped: Any, knowledge: ClientKnowledgeRepository, session: Session
) -> None:
    reviewer = client_scope(scoped, "reviewer")
    proposal = knowledge.propose(reviewer, kind=KnowledgeKind.TERM, title="Flotila")
    decided = knowledge.decide(reviewer, proposal_id=proposal.proposal_id, approve=True)
    row = session.get(ClientKnowledgeProposalRow, proposal.proposal_id)
    assert row is not None
    row.author = None
    row.decision = None
    session.flush()
    [old] = knowledge.proposals(reviewer)
    # A person's proposal in the client workspace carried no marker before K3.
    assert (old.author, old.decision, old.status) == (
        KnowledgeAuthor.UNKNOWN,
        None,
        ProposalStatus.APPROVED,
    )
    [revision] = knowledge.revisions(reviewer, item_id=decided.item_id or "")
    assert (revision.author, revision.decision) == (KnowledgeAuthor.UNKNOWN, None)
