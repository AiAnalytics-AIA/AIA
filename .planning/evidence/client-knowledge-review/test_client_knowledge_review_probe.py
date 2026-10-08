"""Read-only audit reproductions; these assert observed gaps, not target behavior."""

from aia_core.domain.knowledge import KnowledgeKind


def test_a_pending_edit_can_replace_a_newer_accepted_correction(scoped, session):
    from aia_core.infrastructure.client_knowledge_repository import ClientKnowledgeRepository

    repo = ClientKnowledgeRepository(session)
    client = scoped.resolver.client_context(
        scoped.principal(scoped.users["researcher"]),
        client_id=scoped.clients["primary"].client_id,
    )
    original = repo.add(client, kind=KnowledgeKind.FACT, title="Initial claim")
    pending = repo.propose_from_study(
        scoped.scope(user="researcher"),
        kind=KnowledgeKind.FACT,
        title="Earlier pending proposal",
        item_id=original.item_id,
    )
    correction = repo.add(
        client, kind=KnowledgeKind.FACT, title="Newer accepted correction", item_id=original.item_id
    )
    assert correction.revision == 2
    decision = repo.decide(client, proposal_id=pending.proposal_id, approve=True)
    assert decision.revision == 3
    [current] = repo.items(client)
    assert current.title == "Earlier pending proposal"
    assert [r.title for r in repo.revisions(client, item_id=original.item_id)] == [
        "Initial claim", "Newer accepted correction", "Earlier pending proposal"
    ]


def test_a_dimension_can_be_accepted_with_no_definition_or_values(scoped, session):
    from aia_core.infrastructure.client_knowledge_repository import ClientKnowledgeRepository

    repo = ClientKnowledgeRepository(session)
    client = scoped.resolver.client_context(
        scoped.principal(scoped.users["researcher"]),
        client_id=scoped.clients["primary"].client_id,
    )
    repo.add(client, kind=KnowledgeKind.DIMENSION, title="Price sensitivity")
    [dimension] = repo.for_study(scoped.scope(user="researcher"), kinds=[KnowledgeKind.DIMENSION])
    assert dimension.title == "Price sensitivity"
    assert dimension.content == {}
