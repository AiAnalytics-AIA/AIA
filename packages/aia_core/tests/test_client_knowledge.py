"""Client Knowledge (ADR 0015 decision 7): scoped, proposed, approved, revised.

The rules these tests pin: a client's knowledge never reaches another client;
retrieval takes an issued scope and nothing else; a study proposes but never
writes; a person decides (the proposer too, unless the client turned self-approval
off, ADR 0019); an approval appends a revision with its provenance and advances
the client's knowledge revision.
"""

from __future__ import annotations

import dataclasses
import inspect
from typing import Any

import pytest

from aia_core.domain.knowledge import (
    KnowledgeKind,
    LabelColour,
    OrganizerNameTaken,
    ProposalStatus,
    StaleKnowledgeProposal,
    source_ref,
)
from aia_core.domain.scope import (
    ClientContext,
    ClientPermission,
    ScopeDenied,
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


def test_every_member_proposes_and_approves_including_one_with_no_grant(
    scoped: Any, knowledge: ClientKnowledgeRepository
) -> None:
    """ADR 0019: one role holds every Knowledge permission, with or without a grant.

    The matrix used to split propose, approve and manage across four roles, and a member
    with no grant on the client had none of them. Membership of the organization is the
    access now, so the "outsider" of the old fixture proposes, approves and offers a
    study's finding like everyone else.
    """
    users = ("viewer", "reviewer", "researcher", "outsider")
    proposed = [
        knowledge.propose(client_scope(scoped, user), kind=KnowledgeKind.TERM, title=f"x-{user}")
        for user in users
    ]
    for user, proposal in zip(
        ("outsider", "viewer", "researcher", "reviewer"), proposed, strict=True
    ):
        decided = knowledge.decide(
            client_scope(scoped, user), proposal_id=proposal.proposal_id, approve=True
        )
        assert decided.status is ProposalStatus.APPROVED
    assert knowledge.propose_from_study(
        scoped.scope(user="outsider"), kind=KnowledgeKind.FINDING, title="y"
    )
    assert {i.title for i in knowledge.items(client_scope(scoped, "outsider"))} == {
        f"x-{user}" for user in users
    }


def test_each_study_counts_what_it_proposed_by_status_within_its_own_client(
    scoped: Any, knowledge: ClientKnowledgeRepository
) -> None:
    """What a study brought into the client's knowledge, for the studies list."""
    study = scoped.scope(user="researcher")
    taken = knowledge.propose_from_study(study, kind=KnowledgeKind.FINDING, title="Taken")
    knowledge.propose_from_study(study, kind=KnowledgeKind.FINDING, title="Waiting")
    dropped = knowledge.propose_from_study(study, kind=KnowledgeKind.TERM, title="Dropped")
    lead = client_scope(scoped, "lead")
    knowledge.decide(lead, proposal_id=taken.proposal_id, approve=True)
    knowledge.decide(lead, proposal_id=dropped.proposal_id, approve=False)
    # A person's own addition belongs to no study and is not counted against one.
    knowledge.propose(lead, kind=KnowledgeKind.FACT, title="Typed in the workspace")

    assert knowledge.proposal_counts_by_study(lead) == {
        scoped.studies["primary"].study_id: {
            ProposalStatus.APPROVED: 1,
            ProposalStatus.PROPOSED: 1,
            ProposalStatus.REJECTED: 1,
        }
    }
    assert knowledge.proposal_counts_by_study(client_scope(scoped, "other_lead", "other")) == {}


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
    # Direct attempts through the other client's context fail closed: knowledge is read and
    # written by the client the context was issued for, whoever holds it.
    with pytest.raises(ScopeDenied):
        knowledge.decide(globex, proposal_id=proposal.proposal_id, approve=False)
    with pytest.raises(ScopeDenied):
        knowledge.propose(
            globex, kind=KnowledgeKind.FACT, title="hijack", item_id=acme_item.item_id
        )
    # Globex's lead may open Acme's workspace too (ADR 0019), and then sees Acme's knowledge
    # there: through the Acme context, not through Globex's.
    via_acme = client_scope(scoped, "other_lead", "primary")
    assert [i.item_id for i in knowledge.items(via_acme)] == [acme_item.item_id]
    assert knowledge.items(globex) == []


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


def test_a_new_member_reads_the_clients_knowledge_like_any_member(
    scoped: Any, knowledge: ClientKnowledgeRepository
) -> None:
    """ADR 0019: the study-only grantee, who read none of it, is gone with the grants."""
    knowledge.add(client_scope(scoped, "lead"), kind=KnowledgeKind.FACT, title="Dealers: 134")
    member = scoped.scope_repo.add_member(scoped.admin_context, email="guest@art-chain.io")
    ctx = scoped.resolver.client_context(
        scoped.principal(member.user_id), client_id=scoped.clients["primary"].client_id
    )
    assert [i.title for i in knowledge.items(ctx)] == ["Dealers: 134"]
    assert [p.status for p in knowledge.proposals(ctx)] == [ProposalStatus.APPROVED]
    assert knowledge.summary(ctx).items_by_kind == {KnowledgeKind.FACT: 1}


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


# --------------------------------------------------------------------------- #
# Folders and labels (client-workspace C3): organization, not knowledge
# --------------------------------------------------------------------------- #


def _two_items(knowledge: ClientKnowledgeRepository, scope: ClientContext) -> tuple[str, str]:
    for title in ("Výroční zpráva 2025", "Hlavní konkurenti"):
        knowledge.add(scope, kind=KnowledgeKind.SOURCE, title=title)
    a, b = sorted(i.item_id for i in knowledge.items(scope))
    return a, b


def test_a_folder_name_is_the_clients_own_once_whatever_its_case_and_spacing(
    scoped: Any, knowledge: ClientKnowledgeRepository
) -> None:
    lead = client_scope(scoped, "lead")
    made = knowledge.create_folder(lead, name="  Trh a   konkurence ")
    assert made.name == "Trh a konkurence"
    with pytest.raises(OrganizerNameTaken):
        knowledge.create_folder(lead, name="TRH A KONKURENCE")
    with pytest.raises(ValueError):
        knowledge.create_folder(lead, name="   ")
    with pytest.raises(ValueError):
        knowledge.create_folder(lead, name="x" * 81)
    # Accents count: in Czech they change the word.
    knowledge.create_folder(lead, name="Trh a konkurencé")
    # Another client may use the same name; it never sees this one.
    globex = client_scope(scoped, "other_lead", "other")
    knowledge.create_folder(globex, name="Trh a konkurence")
    assert [f.name for f in knowledge.folders(globex)] == ["Trh a konkurence"]
    assert len(knowledge.folders(lead)) == 2
    renamed = knowledge.rename_folder(lead, folder_id=made.folder_id, name="Konkurence")
    assert renamed.name == "Konkurence"
    with pytest.raises(OrganizerNameTaken):
        knowledge.rename_folder(lead, folder_id=made.folder_id, name="trh a konkurencé")
    # Renaming to its own name in another case is not a clash.
    assert knowledge.rename_folder(lead, folder_id=made.folder_id, name="KONKURENCE").name == (
        "KONKURENCE"
    )


def test_filing_writes_no_revision_and_moves_no_dates(
    scoped: Any, knowledge: ClientKnowledgeRepository
) -> None:
    """D4: folders and labels are organization; the knowledge itself does not change."""
    lead = client_scope(scoped, "lead")
    a, b = _two_items(knowledge, lead)
    before = {i.item_id: i for i in knowledge.items(lead)}
    context_before = knowledge.summary(lead).context_revision
    folder = knowledge.create_folder(lead, name="Minulé výzkumy")
    label = knowledge.create_label(lead, name="2025", colour=LabelColour.BLUE)

    placed = knowledge.place(
        lead, item_ids=[a, b, a], folder_id=folder.folder_id, add_labels=[label.label_id]
    )
    assert [(i.item_id, i.folder_id, i.label_ids) for i in placed] == [
        (a, folder.folder_id, (label.label_id,)),
        (b, folder.folder_id, (label.label_id,)),
    ]
    for item in knowledge.items(lead):
        assert item.revision == before[item.item_id].revision
        assert item.modified_at == before[item.item_id].modified_at
    assert knowledge.summary(lead).context_revision == context_before
    assert [len(knowledge.revisions(lead, item_id=i)) for i in (a, b)] == [1, 1]
    # Adding the same label again changes nothing; the folder is kept unless named.
    knowledge.place(lead, item_ids=[a], add_labels=[label.label_id])
    [again] = knowledge.items(lead, label_id=label.label_id, text="výroční")
    assert again.label_ids == (label.label_id,) and again.folder_id == folder.folder_id


def test_items_are_found_by_folder_by_label_and_by_having_no_folder(
    scoped: Any, knowledge: ClientKnowledgeRepository
) -> None:
    lead = client_scope(scoped, "lead")
    a, b = _two_items(knowledge, lead)
    folder = knowledge.create_folder(lead, name="Značka")
    label = knowledge.create_label(lead, name="ověřit", colour=LabelColour.ORANGE)
    knowledge.place(lead, item_ids=[a], folder_id=folder.folder_id)
    knowledge.place(lead, item_ids=[b], add_labels=[label.label_id])
    assert [i.item_id for i in knowledge.items(lead, folder_id=folder.folder_id)] == [a]
    assert [i.item_id for i in knowledge.items(lead, unfiled=True)] == [b]
    assert [i.item_id for i in knowledge.items(lead, label_id=label.label_id)] == [b]
    assert [f.item_count for f in knowledge.folders(lead)] == [1]
    assert [lb.item_count for lb in knowledge.labels(lead)] == [1]
    # Out of the folder, a label off: back where it started.
    knowledge.place(lead, item_ids=[a], folder_id=None)
    knowledge.place(lead, item_ids=[b], remove_labels=[label.label_id])
    assert {i.item_id for i in knowledge.items(lead, unfiled=True)} == {a, b}
    assert knowledge.items(lead, label_id=label.label_id) == []


def test_deleting_a_folder_or_a_label_keeps_the_items(
    scoped: Any, knowledge: ClientKnowledgeRepository
) -> None:
    lead = client_scope(scoped, "lead")
    a, b = _two_items(knowledge, lead)
    folder = knowledge.create_folder(lead, name="Dočasná")
    label = knowledge.create_label(lead, name="koncept", colour=LabelColour.SLATE)
    knowledge.place(lead, item_ids=[a, b], folder_id=folder.folder_id, add_labels=[label.label_id])
    knowledge.delete_folder(lead, folder_id=folder.folder_id)
    knowledge.delete_label(lead, label_id=label.label_id)
    items = knowledge.items(lead)
    assert {i.item_id for i in items} == {a, b}
    assert all(i.folder_id is None and i.label_ids == () for i in items)
    assert knowledge.folders(lead) == [] and knowledge.labels(lead) == []
    with pytest.raises(ScopeDenied):
        knowledge.delete_folder(lead, folder_id=folder.folder_id)


def test_filing_is_all_or_nothing_and_never_crosses_clients(
    scoped: Any, knowledge: ClientKnowledgeRepository
) -> None:
    lead = client_scope(scoped, "lead")
    a, _ = _two_items(knowledge, lead)
    mine = knowledge.create_folder(lead, name="Moje")
    label = knowledge.create_label(lead, name="moje", colour=LabelColour.GREEN)
    globex = client_scope(scoped, "other_lead", "other")
    knowledge.add(globex, kind=KnowledgeKind.FACT, title="Globex only")
    [theirs] = knowledge.items(globex)
    their_folder = knowledge.create_folder(globex, name="Jejich")

    for attempt in (
        {"item_ids": [a, theirs.item_id], "folder_id": mine.folder_id},
        {"item_ids": [a], "folder_id": their_folder.folder_id},
        {"item_ids": [a], "add_labels": [label.label_id, "KNL-00000000000000"]},
    ):
        with pytest.raises(ScopeDenied):
            knowledge.place(lead, **attempt)  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        knowledge.place(
            lead, item_ids=[a], add_labels=[label.label_id], remove_labels=[label.label_id]
        )
    with pytest.raises(ValueError):
        knowledge.place(lead, item_ids=[])
    # Nothing of the refused attempts was written.
    [item] = [i for i in knowledge.items(lead) if i.item_id == a]
    assert item.folder_id is None and item.label_ids == ()
    # Through another client's context, this client's folders are not found.
    with pytest.raises(ScopeDenied):
        knowledge.rename_folder(globex, folder_id=mine.folder_id, name="hijack")
    assert knowledge.items(globex, folder_id=mine.folder_id) == []


def test_what_a_study_reads_never_carries_folders_or_labels(
    scoped: Any, knowledge: ClientKnowledgeRepository
) -> None:
    """D4: no model sees how people filed the knowledge."""
    lead = client_scope(scoped, "lead")
    a, b = _two_items(knowledge, lead)
    folder = knowledge.create_folder(lead, name="Interní")
    label = knowledge.create_label(lead, name="citlivé", colour=LabelColour.VIOLET)
    knowledge.place(lead, item_ids=[a, b], folder_id=folder.folder_id, add_labels=[label.label_id])
    consumed = knowledge.for_study(scoped.scope(user="researcher"))
    assert {i.item_id for i in consumed} == {a, b}
    assert all(i.folder_id is None and i.label_ids == () for i in consumed)


def test_organizing_needs_the_permission_to_propose_and_is_audited(
    scoped: Any, knowledge: ClientKnowledgeRepository, session: Any
) -> None:
    from sqlalchemy import select

    from aia_core.infrastructure.tables import AccessAuditRow

    lead = client_scope(scoped, "lead")
    a, _ = _two_items(knowledge, lead)
    folder = knowledge.create_folder(lead, name="Audit")
    knowledge.place(lead, item_ids=[a], folder_id=folder.folder_id)
    actions = session.scalars(
        select(AccessAuditRow.action).where(AccessAuditRow.action.like("CLIENT_KNOWLEDGE_%"))
    ).all()
    assert "CLIENT_KNOWLEDGE_FOLDER_CREATED" in actions
    assert "CLIENT_KNOWLEDGE_ORGANIZED" in actions

    # Every member holds every permission today (ADR 0019); a narrower context is what a
    # future reader-only role would be issued, so the rule is pinned against it.
    reader = dataclasses.replace(
        lead,
        permissions=frozenset(
            p for p in lead.permissions if p is not ClientPermission.PROPOSE_CLIENT_KNOWLEDGE
        ),
    )
    with pytest.raises(ScopeDenied):
        knowledge.create_folder(reader, name="Bez práva")
    with pytest.raises(ScopeDenied):
        knowledge.place(reader, item_ids=[a], folder_id=None)
    assert [f.name for f in knowledge.folders(reader)] == ["Audit"]


# --------------------------------------------------------------------------- #
# Přehled (client-workspace C10): what wants a person's attention, what changed
# --------------------------------------------------------------------------- #


def test_health_counts_items_unchanged_for_a_year_and_items_in_no_folder(
    scoped: Any, knowledge: ClientKnowledgeRepository, session: Any
) -> None:
    from datetime import UTC, datetime, timedelta

    from sqlalchemy import update

    from aia_core.infrastructure.tables import ClientKnowledgeItemRow

    lead = client_scope(scoped, "lead")
    a, b = _two_items(knowledge, lead)
    now = datetime.now(UTC)
    assert knowledge.health(lead, now=now).model_dump() == {"stale": 0, "unfiled": 2}
    folder = knowledge.create_folder(lead, name="Archiv")
    knowledge.place(lead, item_ids=[a], folder_id=folder.folder_id)
    session.execute(
        update(ClientKnowledgeItemRow)
        .where(ClientKnowledgeItemRow.item_id == b)
        .values(modified_at=now - timedelta(days=400))
    )
    assert knowledge.health(lead, now=now).model_dump() == {"stale": 1, "unfiled": 1}
    # A day short of the year is not stale yet.
    assert knowledge.health(lead, now=now - timedelta(days=36)).stale == 0
    assert knowledge.health(client_scope(scoped, "other_lead", "other"), now=now).model_dump() == {
        "stale": 0,
        "unfiled": 0,
    }


def test_recent_revisions_are_the_clients_latest_changes_newest_first(
    scoped: Any, knowledge: ClientKnowledgeRepository
) -> None:
    lead = client_scope(scoped, "lead")
    first = knowledge.add(lead, kind=KnowledgeKind.FACT, title="První")
    knowledge.add(lead, kind=KnowledgeKind.TERM, title="Druhý")
    knowledge.add(lead, kind=KnowledgeKind.FACT, title="První, opravený", item_id=first.item_id)
    recent = knowledge.recent_revisions(lead, limit=2)
    assert [(r.title, r.revision) for r in recent] == [("První, opravený", 2), ("Druhý", 1)]
    assert knowledge.recent_revisions(client_scope(scoped, "other_lead", "other")) == []


# ---------------------------------------------------------------- F-K1: stale revisions


def _fact_corrected_after_a_study_proposed(
    scoped: Any, knowledge: ClientKnowledgeRepository
) -> tuple[str, str]:
    """A FACT at revision 1, a study's edit of it, then a person's correction (revision 2)."""
    researcher = client_scope(scoped, "researcher")
    first = knowledge.add(researcher, kind=KnowledgeKind.FACT, title="Dealers: 120")
    assert first.item_id is not None
    edit = knowledge.propose_from_study(
        scoped.scope(user="researcher"),
        kind=KnowledgeKind.FACT,
        title="Dealers: 125",
        item_id=first.item_id,
    )
    assert edit.base_revision == 1
    knowledge.add(researcher, kind=KnowledgeKind.FACT, title="Dealers: 134", item_id=first.item_id)
    return first.item_id, edit.proposal_id


def test_an_edit_written_before_a_newer_correction_is_refused_and_changes_nothing(
    scoped: Any, knowledge: ClientKnowledgeRepository
) -> None:
    """F-K1: approving the older edit used to replace the correction at revision 3."""
    item_id, proposal_id = _fact_corrected_after_a_study_proposed(scoped, knowledge)
    reviewer = client_scope(scoped, "reviewer")
    with pytest.raises(StaleKnowledgeProposal) as refused:
        knowledge.decide(reviewer, proposal_id=proposal_id, approve=True)
    assert (refused.value.item_id, refused.value.base_revision) == (item_id, 1)
    assert refused.value.current_revision == 2
    [item] = knowledge.items(reviewer)
    assert (item.title, item.revision) == ("Dealers: 134", 2)
    [pending] = knowledge.proposals(reviewer, status=ProposalStatus.PROPOSED)
    assert pending.proposal_id == proposal_id
    # Naming a revision that is not the current one is still stale.
    with pytest.raises(StaleKnowledgeProposal):
        knowledge.decide(reviewer, proposal_id=proposal_id, approve=True, reviewed_revision=1)
    assert knowledge.summary(reviewer).context_revision == 2


def test_a_reviewer_who_names_the_current_revision_accepts_the_edit_over_it(
    scoped: Any, knowledge: ClientKnowledgeRepository
) -> None:
    item_id, proposal_id = _fact_corrected_after_a_study_proposed(scoped, knowledge)
    reviewer = client_scope(scoped, "reviewer")
    decided = knowledge.decide(reviewer, proposal_id=proposal_id, approve=True, reviewed_revision=2)
    assert decided.status is ProposalStatus.APPROVED and decided.revision == 3
    history = knowledge.revisions(reviewer, item_id=item_id)
    assert [r.title for r in history] == ["Dealers: 120", "Dealers: 134", "Dealers: 125"]
    assert history[-1].provenance["base_revision"] == 1
    assert history[-1].provenance["accepted_over_revision"] == 2


def test_a_stale_edit_can_still_be_rejected(
    scoped: Any, knowledge: ClientKnowledgeRepository
) -> None:
    _, proposal_id = _fact_corrected_after_a_study_proposed(scoped, knowledge)
    reviewer = client_scope(scoped, "reviewer")
    rejected = knowledge.decide(reviewer, proposal_id=proposal_id, approve=False, note="older")
    assert rejected.status is ProposalStatus.REJECTED
    [item] = knowledge.items(reviewer)
    assert item.title == "Dealers: 134"


def test_a_persons_edit_from_an_older_revision_is_refused_before_it_is_filed(
    scoped: Any, knowledge: ClientKnowledgeRepository
) -> None:
    researcher = client_scope(scoped, "researcher")
    first = knowledge.add(researcher, kind=KnowledgeKind.FACT, title="Dealers: 120")
    assert first.item_id is not None
    knowledge.add(
        researcher,
        kind=KnowledgeKind.FACT,
        title="Dealers: 134",
        item_id=first.item_id,
        base_revision=1,
    )
    with pytest.raises(StaleKnowledgeProposal):
        knowledge.add(
            researcher,
            kind=KnowledgeKind.FACT,
            title="Dealers: 99",
            item_id=first.item_id,
            base_revision=1,
        )
    [item] = knowledge.items(researcher)
    assert (item.title, item.revision) == ("Dealers: 134", 2)
    assert knowledge.proposals(researcher, status=ProposalStatus.PROPOSED) == []
    with pytest.raises(ValueError):
        knowledge.add(researcher, kind=KnowledgeKind.FACT, title="New", base_revision=1)


def test_an_edit_filed_before_its_base_was_recorded_is_treated_as_stale(
    scoped: Any, knowledge: ClientKnowledgeRepository, session: Any
) -> None:
    """Unknown is never current: a pending edit from before the column waits for a reviewer."""
    from aia_core.infrastructure.tables import ClientKnowledgeProposalRow

    researcher = client_scope(scoped, "researcher")
    first = knowledge.add(researcher, kind=KnowledgeKind.FACT, title="Dealers: 120")
    edit = knowledge.propose(
        researcher, kind=KnowledgeKind.FACT, title="Dealers: 125", item_id=first.item_id
    )
    row = session.get(ClientKnowledgeProposalRow, edit.proposal_id)
    row.base_revision = None
    session.flush()
    reviewer = client_scope(scoped, "reviewer")
    with pytest.raises(StaleKnowledgeProposal) as refused:
        knowledge.decide(reviewer, proposal_id=edit.proposal_id, approve=True)
    assert refused.value.base_revision is None
    decided = knowledge.decide(
        reviewer, proposal_id=edit.proposal_id, approve=True, reviewed_revision=1
    )
    assert decided.revision == 2


# ---- a file by reference (client-workspace C7a) -----------------------------------------


def test_only_a_source_document_or_dataset_names_a_source_and_only_by_its_id() -> None:
    ref = {"source_id": "SRC-0123456789abcdef"}
    for kind in (KnowledgeKind.SOURCE, KnowledgeKind.DOCUMENT, KnowledgeKind.DATASET):
        assert source_ref(kind, ref) == "SRC-0123456789abcdef"
        assert source_ref(kind, {}) is None
    with pytest.raises(ValueError, match="does not carry a source"):
        source_ref(KnowledgeKind.FACT, ref)
    for bad in ("SRC-XYZ", "src-0123456789abcdef", " SRC-0123456789abcdef", None, 7):
        with pytest.raises(ValueError, match="not a source's id"):
            source_ref(KnowledgeKind.DOCUMENT, {"source_id": bad})


def test_a_malformed_reference_is_refused_on_every_way_in_and_a_study_names_none(
    scoped: Any, knowledge: ClientKnowledgeRepository
) -> None:
    lead = client_scope(scoped, "lead")
    with pytest.raises(ValueError):
        knowledge.add(
            lead, kind=KnowledgeKind.FACT, title="F", content={"source_id": "SRC-0123456789abcdef"}
        )
    with pytest.raises(ValueError):
        knowledge.propose(lead, kind=KnowledgeKind.DOCUMENT, title="D", content={"source_id": "x"})
    with pytest.raises(ValueError, match="does not attach"):
        knowledge.propose_from_study(
            scoped.scope(user="researcher"),
            kind=KnowledgeKind.DOCUMENT,
            title="D",
            content={"source_id": "SRC-0123456789abcdef"},
        )
    assert knowledge.proposals(lead) == []


def test_a_checked_source_is_added_once_per_client_and_url(
    scoped: Any, knowledge: ClientKnowledgeRepository
) -> None:
    """Plan inline-decisions 1: the same URL again answers ``exists`` and writes nothing; another
    client, or another URL, is its own source."""
    researcher = client_scope(scoped, "researcher")
    url = "https://stat.example/fiktivni"
    first = knowledge.add_source_once(
        researcher, url=url, title="Fiktivní statistika", content={"quote": "q"}, provenance={}
    )
    assert first.status == "added" and first.item_id is not None
    again = knowledge.add_source_once(
        researcher, url=url, title="Jiný název", content={}, provenance={}
    )
    assert (again.status, again.item_id, again.proposal_id) == ("exists", first.item_id, None)
    [item] = knowledge.items(researcher)
    assert item.content == {"quote": "q", "url": url} and item.kind is KnowledgeKind.SOURCE
    other = knowledge.add_source_once(
        researcher, url=f"{url}/2", title="Druhý", content={}, provenance={}
    )
    assert other.status == "added"
    theirs = knowledge.add_source_once(
        client_scope(scoped, "other_lead", "other"), url=url, title="B", content={}, provenance={}
    )
    assert theirs.status == "added" and theirs.item_id != first.item_id


def test_a_checked_source_is_the_same_source_by_its_final_url_either_way(
    scoped: Any, knowledge: ClientKnowledgeRepository
) -> None:
    """A source is one source whether a run reached it by its address or through a redirect:
    a URL that is another source's final URL, or a final URL that is another's URL, answers
    ``exists`` and writes nothing."""
    researcher = client_scope(scoped, "researcher")
    short, final = "https://stat.example/s/1", "https://stat.example/fiktivni-statistika"
    first = knowledge.add_source_once(
        researcher, url=short, title="T", content={"final_url": final}, provenance={}
    )
    assert first.status == "added"
    reached_directly = knowledge.add_source_once(
        researcher, url=final, title="T", content={"final_url": final}, provenance={}
    )
    assert (reached_directly.status, reached_directly.item_id) == ("exists", first.item_id)
    other = knowledge.add_source_once(
        researcher, url="https://stat.example/s/2", title="T", content={}, provenance={}
    )
    via_redirect = knowledge.add_source_once(
        researcher,
        url="https://stat.example/s/3",
        title="T",
        content={"final_url": "https://stat.example/s/2"},
        provenance={},
    )
    assert (via_redirect.status, via_redirect.item_id) == ("exists", other.item_id)
    assert len(knowledge.items(researcher)) == 2


def test_where_self_approval_is_off_a_checked_source_waits_and_is_not_proposed_twice(
    scoped: Any, knowledge: ClientKnowledgeRepository
) -> None:
    scoped.scope_repo.set_self_approval(
        scoped.admin_context, allowed=False, client_id=scoped.clients["primary"].client_id
    )
    researcher = client_scope(scoped, "researcher")
    url = "https://trh.example/fiktivni"
    first = knowledge.add_source_once(researcher, url=url, title="T", content={}, provenance={})
    assert first.status == "proposed" and first.item_id is None and first.proposal_id
    again = knowledge.add_source_once(researcher, url=url, title="T", content={}, provenance={})
    assert (again.status, again.proposal_id) == ("exists", first.proposal_id)
    assert len(knowledge.proposals(researcher, status=ProposalStatus.PROPOSED)) == 1


def test_a_checked_source_is_refused_under_a_deleted_clients_tombstone(
    scoped: Any, session: Any, knowledge: ClientKnowledgeRepository
) -> None:
    """Settings-backends SB5: a writer that resolved its scope before a deletion and takes the
    client's lock after it reads the tombstone and writes nothing."""
    from datetime import UTC, datetime

    from aia_core.infrastructure.tables import ClientRow

    researcher = client_scope(scoped, "researcher")  # resolved before the deletion
    session.get(ClientRow, researcher.client_id).deleted_at = datetime.now(UTC)
    session.flush()
    with pytest.raises(ScopeDenied) as denied:
        knowledge.add_source_once(
            researcher, url="https://stat.example/x", title="X", content={}, provenance={}
        )
    assert denied.value.reason == "client_deleted"
    assert knowledge.items(researcher) == []
