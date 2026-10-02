"""Client Knowledge (ADR 0015 decision 7): scoped, proposed, approved, revised.

The rules these tests pin: a client's knowledge never reaches another client;
retrieval takes an issued scope and nothing else; a study proposes but never
writes; a person decides (the proposer too, unless the client turned self-approval
off, ADR 0019); an approval appends a revision with its provenance and advances
the client's knowledge revision.
"""

from __future__ import annotations

import inspect
from typing import Any

import pytest

from aia_core.domain.knowledge import KnowledgeKind, ProposalStatus
from aia_core.domain.scope import (
    ClientContext,
    ScopeDenied,
    ScopeRole,
    SeparationOfDutiesViolation,
)
from aia_core.infrastructure.client_knowledge_repository import ClientKnowledgeRepository


@pytest.fixture
def knowledge(session: Any) -> ClientKnowledgeRepository:
    return ClientKnowledgeRepository(session)


def client_scope(scoped: Any, user: str, client: str = "primary") -> ClientContext:
    return scoped.resolver.client_context(
        scoped.principal(scoped.users[user]), client_id=scoped.clients[client].client_id
    )


def test_a_studys_finding_changes_nothing_until_a_person_approves_it(
    scoped: Any, knowledge: ClientKnowledgeRepository
) -> None:
    proposal = knowledge.propose_from_study(
        scoped.scope(user="researcher"),
        kind=KnowledgeKind.FINDING,
        title="Price sensitivity peaks at 25-34",
        summary="Seen in the brand study.",
        provenance={"project_id": "PRJ-1", "artifact_id": "ART-1"},
    )
    assert proposal.status is ProposalStatus.PROPOSED
    assert proposal.study_id == scoped.studies["primary"].study_id
    assert knowledge.items(client_scope(scoped, "lead")) == []

    decided = knowledge.decide(
        client_scope(scoped, "reviewer"), proposal_id=proposal.proposal_id, approve=True
    )
    assert decided.status is ProposalStatus.APPROVED and decided.revision == 1
    [item] = knowledge.items(client_scope(scoped, "lead"))
    assert item.title == "Price sensitivity peaks at 25-34"
    [rev] = knowledge.revisions(client_scope(scoped, "lead"), item_id=item.item_id)
    assert rev.context_revision == 1
    assert rev.provenance == {
        "project_id": "PRJ-1",
        "artifact_id": "ART-1",
        "study_id": scoped.studies["primary"].study_id,
        "origin": "STUDY",
        "proposal_id": proposal.proposal_id,
        "proposed_by": scoped.users["researcher"],
    }
    assert rev.approved_by == scoped.users["reviewer"]


def test_the_proposer_may_approve_their_own_proposal_by_default(
    scoped: Any, knowledge: ClientKnowledgeRepository
) -> None:
    """ADR 0019: self-approval is allowed unless the client turns it off."""
    lead = client_scope(scoped, "lead")
    proposal = knowledge.propose(lead, kind=KnowledgeKind.TERM, title="Fleet buyer")
    decided = knowledge.decide(lead, proposal_id=proposal.proposal_id, approve=True)
    assert decided.status is ProposalStatus.APPROVED
    [item] = knowledge.items(lead)
    [rev] = knowledge.revisions(lead, item_id=item.item_id)
    assert rev.approved_by == scoped.users["lead"]


def test_the_proposer_does_not_approve_their_own_proposal_where_the_client_turned_it_off(
    scoped: Any, knowledge: ClientKnowledgeRepository
) -> None:
    """A client that demands independent review gets it back through the setting."""
    scoped.scope_repo.set_self_approval(
        scoped.admin_context, allowed=False, client_id=scoped.clients["primary"].client_id
    )
    lead = client_scope(scoped, "lead")
    proposal = knowledge.propose(lead, kind=KnowledgeKind.TERM, title="Fleet buyer")
    with pytest.raises(SeparationOfDutiesViolation):
        knowledge.decide(lead, proposal_id=proposal.proposal_id, approve=True)
    assert knowledge.items(lead) == []

    decided = knowledge.decide(
        client_scope(scoped, "reviewer"), proposal_id=proposal.proposal_id, approve=True
    )
    assert decided.status is ProposalStatus.APPROVED


def test_what_a_person_adds_takes_effect_at_once_with_nobody_to_approve_it(
    scoped: Any, knowledge: ClientKnowledgeRepository
) -> None:
    """ADR 0019 decision 3: a source a person adds is knowledge, not a request for it."""
    researcher = client_scope(scoped, "researcher")
    added = knowledge.add(
        researcher, kind=KnowledgeKind.SOURCE, title="Starbucks annual report", summary="2025"
    )
    assert added.status is ProposalStatus.APPROVED and added.revision == 1
    assert knowledge.proposals(researcher, status=ProposalStatus.PROPOSED) == []
    [item] = knowledge.items(client_scope(scoped, "lead"))
    assert (item.title, item.kind) == ("Starbucks annual report", KnowledgeKind.SOURCE)
    [rev] = knowledge.revisions(researcher, item_id=item.item_id)
    assert rev.approved_by == scoped.users["researcher"]
    assert rev.provenance["authored"] == "person"
    assert rev.provenance["origin"] == "CLIENT"
    # A study of this client consumes it straight away.
    assert [i.title for i in knowledge.for_study(scoped.scope(user="researcher"))] == [
        "Starbucks annual report"
    ]


def test_a_person_editing_an_item_appends_a_revision_without_a_proposal_to_decide(
    scoped: Any, knowledge: ClientKnowledgeRepository
) -> None:
    researcher = client_scope(scoped, "researcher")
    first = knowledge.add(researcher, kind=KnowledgeKind.FACT, title="Dealers: 120")
    assert first.item_id is not None
    second = knowledge.add(
        researcher, kind=KnowledgeKind.FACT, title="Dealers: 134", item_id=first.item_id
    )
    assert second.status is ProposalStatus.APPROVED and second.revision == 2
    [item] = knowledge.items(researcher)
    assert (item.title, item.revision) == ("Dealers: 134", 2)
    assert knowledge.summary(researcher).context_revision == 2
    with pytest.raises(ValueError):
        knowledge.add(researcher, kind=KnowledgeKind.TERM, title="x", item_id=first.item_id)
    with pytest.raises(ScopeDenied):
        knowledge.add(researcher, kind=KnowledgeKind.FACT, title="x", item_id="KNW-00000000000000")


def test_where_the_client_turned_self_approval_off_a_persons_addition_still_waits_for_someone(
    scoped: Any, knowledge: ClientKnowledgeRepository
) -> None:
    """The setting survives: a client that demands independent review keeps it for people too."""
    scoped.scope_repo.set_self_approval(
        scoped.admin_context, allowed=False, client_id=scoped.clients["primary"].client_id
    )
    researcher = client_scope(scoped, "researcher")
    added = knowledge.add(researcher, kind=KnowledgeKind.SOURCE, title="Annual report")
    assert added.status is ProposalStatus.PROPOSED
    assert knowledge.items(researcher) == []
    decided = knowledge.decide(
        client_scope(scoped, "reviewer"), proposal_id=added.proposal_id, approve=True
    )
    assert decided.status is ProposalStatus.APPROVED
    assert [i.title for i in knowledge.items(researcher)] == ["Annual report"]


def test_a_persons_addition_is_scoped_to_their_own_client(
    scoped: Any, knowledge: ClientKnowledgeRepository
) -> None:
    knowledge.add(client_scope(scoped, "lead"), kind=KnowledgeKind.SOURCE, title="Only A")
    assert knowledge.items(client_scope(scoped, "other_lead", "other")) == []
    with pytest.raises(ScopeDenied):
        knowledge.add(scoped.scope(user="researcher"), kind=KnowledgeKind.SOURCE, title="x")  # type: ignore[arg-type]


def test_a_revision_appends_and_advances_the_clients_knowledge_revision(
    scoped: Any, knowledge: ClientKnowledgeRepository
) -> None:
    first = knowledge.propose(
        client_scope(scoped, "researcher"), kind=KnowledgeKind.FACT, title="Dealers: 120"
    )
    knowledge.decide(client_scope(scoped, "reviewer"), proposal_id=first.proposal_id, approve=True)
    [item] = knowledge.items(client_scope(scoped, "lead"))
    second = knowledge.propose(
        client_scope(scoped, "researcher"),
        kind=KnowledgeKind.FACT,
        title="Dealers: 134",
        item_id=item.item_id,
    )
    knowledge.decide(client_scope(scoped, "reviewer"), proposal_id=second.proposal_id, approve=True)
    [now] = knowledge.items(client_scope(scoped, "lead"))
    assert (now.item_id, now.title, now.revision) == (item.item_id, "Dealers: 134", 2)
    history = knowledge.revisions(client_scope(scoped, "lead"), item_id=item.item_id)
    assert [(r.revision, r.context_revision, r.title) for r in history] == [
        (1, 1, "Dealers: 120"),
        (2, 2, "Dealers: 134"),
    ]
    assert knowledge.summary(client_scope(scoped, "lead")).context_revision == 2
    with pytest.raises(ValueError):
        knowledge.propose(
            client_scope(scoped, "researcher"),
            kind=KnowledgeKind.TERM,
            title="x",
            item_id=item.item_id,
        )


def test_a_rejection_changes_nothing_and_a_decision_is_final(
    scoped: Any, knowledge: ClientKnowledgeRepository
) -> None:
    proposal = knowledge.propose(
        client_scope(scoped, "researcher"), kind=KnowledgeKind.ENTITY, title="Competitor X"
    )
    rejected = knowledge.decide(
        client_scope(scoped, "reviewer"),
        proposal_id=proposal.proposal_id,
        approve=False,
        note="unverified",
    )
    assert (rejected.status, rejected.decision_note, rejected.revision) == (
        ProposalStatus.REJECTED,
        "unverified",
        None,
    )
    assert knowledge.items(client_scope(scoped, "lead")) == []
    with pytest.raises(ValueError):
        knowledge.decide(
            client_scope(scoped, "lead"), proposal_id=proposal.proposal_id, approve=True
        )


def test_every_member_proposes_and_approves_and_an_outsider_does_neither(
    scoped: Any, knowledge: ClientKnowledgeRepository
) -> None:
    """ADR 0019: one role holds every Knowledge permission; no grant holds none.

    The matrix used to split propose, approve and manage across four roles. Now a
    former viewer proposes, a former reviewer proposes, anyone approves, and the
    one boundary left is having no grant on the client, which issues no context.
    """
    proposed = [
        knowledge.propose(client_scope(scoped, user), kind=KnowledgeKind.TERM, title=f"x-{user}")
        for user in ("viewer", "reviewer", "researcher")
    ]
    for user, proposal in zip(("viewer", "researcher", "reviewer"), proposed, strict=True):
        decided = knowledge.decide(
            client_scope(scoped, user), proposal_id=proposal.proposal_id, approve=True
        )
        assert decided.status is ProposalStatus.APPROVED
    assert knowledge.propose_from_study(
        scoped.scope(user="viewer"), kind=KnowledgeKind.FINDING, title="y"
    )

    with pytest.raises(ScopeDenied):
        client_scope(scoped, "outsider")
    with pytest.raises(ScopeDenied):
        scoped.scope(user="outsider")


def test_client_a_knowledge_never_appears_under_client_b(
    scoped: Any, knowledge: ClientKnowledgeRepository
) -> None:
    proposal = knowledge.propose(
        client_scope(scoped, "researcher"), kind=KnowledgeKind.FACT, title="Acme only"
    )
    knowledge.decide(
        client_scope(scoped, "reviewer"), proposal_id=proposal.proposal_id, approve=True
    )
    [acme_item] = knowledge.items(client_scope(scoped, "lead"))

    globex = client_scope(scoped, "other_lead", "other")
    assert knowledge.items(globex) == []
    assert knowledge.items(globex, text="acme") == []
    assert knowledge.proposals(globex) == []
    assert knowledge.revisions(globex, item_id=acme_item.item_id) == []
    assert knowledge.summary(globex).items_by_kind == {}
    assert knowledge.for_study(scoped.scope(user="other_lead", study="other_client")) == []
    # Direct attempts across the boundary fail closed.
    with pytest.raises(ScopeDenied):
        knowledge.decide(globex, proposal_id=proposal.proposal_id, approve=False)
    with pytest.raises(ScopeDenied):
        knowledge.propose(
            globex, kind=KnowledgeKind.FACT, title="hijack", item_id=acme_item.item_id
        )
    with pytest.raises(ScopeDenied):
        client_scope(scoped, "other_lead", "primary")


def test_a_study_consumes_its_own_clients_approved_knowledge_only(
    scoped: Any, knowledge: ClientKnowledgeRepository
) -> None:
    for title in ("Fleet buyers renew every 4 years", "Dealer network is shrinking"):
        p = knowledge.propose(
            client_scope(scoped, "researcher"), kind=KnowledgeKind.FINDING, title=title
        )
        knowledge.decide(client_scope(scoped, "reviewer"), proposal_id=p.proposal_id, approve=True)
    pending = knowledge.propose(
        client_scope(scoped, "researcher"), kind=KnowledgeKind.FINDING, title="Not yet approved"
    )
    consumed = knowledge.for_study(scoped.scope(user="viewer", study="sibling"))
    assert {i.title for i in consumed} == {
        "Fleet buyers renew every 4 years",
        "Dealer network is shrinking",
    }
    assert pending.title not in {i.title for i in consumed}
    assert [i.title for i in knowledge.for_study(scoped.scope(), text="dealer")] == [
        "Dealer network is shrinking"
    ]
    assert knowledge.for_study(scoped.scope(), kinds=[KnowledgeKind.TERM]) == []


def test_a_study_only_grantee_sees_no_client_knowledge(
    scoped: Any, knowledge: ClientKnowledgeRepository
) -> None:
    member = scoped.scope_repo.add_member(scoped.admin_context, email="guest@art-chain.io")
    scoped.resolver.grant_study_access(
        scoped.scope(), user_id=member.user_id, role=ScopeRole.RESEARCHER
    )
    ctx = scoped.resolver.client_context(
        scoped.principal(member.user_id), client_id=scoped.clients["primary"].client_id
    )
    for read in (knowledge.items, knowledge.proposals, knowledge.summary):
        with pytest.raises(ScopeDenied):
            read(ctx)


def test_retrieval_takes_an_issued_scope_and_nothing_else(
    scoped: Any, knowledge: ClientKnowledgeRepository
) -> None:
    for wrong in (scoped.admin_context, {"client_id": scoped.clients["primary"].client_id}, None):
        with pytest.raises(ScopeDenied) as denied:
            knowledge.items(wrong)
        assert denied.value.reason == "forged_scope"
        with pytest.raises(ScopeDenied):
            knowledge.for_study(wrong)
    # Every public method's first argument is the scope; none takes a client id.
    for name, method in inspect.getmembers(ClientKnowledgeRepository, inspect.isfunction):
        if name.startswith("_"):
            continue
        params = list(inspect.signature(method).parameters)
        assert params[1] == "scope", name
        assert "client_id" not in params, name
