"""A study's selected client knowledge, frozen (client-knowledge-lifecycle K4a).

The rules these tests pin: a person chooses an item for a study at the revision they were
shown, and a stale choice selects nothing; the frozen context holds each chosen revision's
words, never a newer one, and says when the item has moved on; an item no longer active is
named as omitted, never dropped silently; nothing crosses to another client or study; the
context's hash names exactly what it holds.
"""

from __future__ import annotations

from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from aia_core.domain.knowledge import KnowledgeAuthor, KnowledgeKind, revision_sha256
from aia_core.domain.knowledge_context import (
    CONTEXT_VERSION,
    ContextEntryState,
    FrozenKnowledgeContext,
    FrozenKnowledgeEntry,
    OmittedKnowledge,
    OmittedReason,
    StaleKnowledgeSelection,
    context_sha256,
)
from aia_core.domain.scope import ClientContext, Permission, ScopeDenied
from aia_core.infrastructure.client_knowledge_repository import ClientKnowledgeRepository
from aia_core.infrastructure.tables import (
    AccessAuditRow,
    ClientKnowledgeItemRow,
    ClientKnowledgeSelectionRow,
    StudyRow,
)


@pytest.fixture
def knowledge(session: Session) -> ClientKnowledgeRepository:
    return ClientKnowledgeRepository(session)


def client_scope(scoped: Any, user: str = "researcher", client: str = "primary") -> ClientContext:
    return scoped.resolver.client_context(
        scoped.principal(scoped.users[user]), client_id=scoped.clients[client].client_id
    )


def _fact(knowledge: ClientKnowledgeRepository, scope: ClientContext, title: str) -> str:
    added = knowledge.add(scope, kind=KnowledgeKind.FACT, title=title, summary="Shrnutí.")
    assert added.item_id is not None
    return added.item_id


def test_a_study_without_choices_freezes_an_empty_context_whatever_the_client_holds(
    scoped: Any, knowledge: ClientKnowledgeRepository
) -> None:
    """Knowledge accepted for the client does not enter a study on its own."""
    _fact(knowledge, client_scope(scoped), "Dealeři: 120")
    frozen = knowledge.freeze_for_study(scoped.scope(user="researcher"))
    assert (frozen.entries, frozen.omitted) == ((), ())
    assert frozen.study_id == scoped.studies["primary"].study_id
    assert frozen.verify()


def test_a_chosen_revision_is_frozen_with_its_words_and_hash(
    scoped: Any, knowledge: ClientKnowledgeRepository
) -> None:
    item_id = _fact(knowledge, client_scope(scoped), "Dealeři: 120")
    study = scoped.scope(user="researcher")
    chosen = knowledge.select_for_study(study, item_id=item_id, revision=1)
    assert (chosen.item_id, chosen.revision, chosen.selected_by) == (
        item_id,
        1,
        scoped.users["researcher"],
    )
    frozen = knowledge.freeze_for_study(study)
    [entry] = frozen.entries
    assert (entry.title, entry.summary, entry.revision) == ("Dealeři: 120", "Shrnutí.", 1)
    assert (entry.kind, entry.author, entry.state) == (
        KnowledgeKind.FACT,
        KnowledgeAuthor.PERSON,
        ContextEntryState.CURRENT,
    )
    assert entry.sha256 == revision_sha256("Dealeři: 120", "Shrnutí.", {})
    # Frozen twice, unchanged: the same context, hash for hash.
    assert knowledge.freeze_for_study(study).sha256 == frozen.sha256
    assert frozen.verify()


def test_a_choice_from_an_older_screen_selects_nothing(
    scoped: Any, knowledge: ClientKnowledgeRepository
) -> None:
    person = client_scope(scoped)
    item_id = _fact(knowledge, person, "Dealeři: 120")
    knowledge.add(person, kind=KnowledgeKind.FACT, title="Dealeři: 134", item_id=item_id)
    study = scoped.scope(user="researcher")
    with pytest.raises(StaleKnowledgeSelection) as refused:
        knowledge.select_for_study(study, item_id=item_id, revision=1)
    assert (refused.value.revision, refused.value.current_revision) == (1, 2)
    assert knowledge.selections(study) == []


def test_an_item_that_moved_on_stays_frozen_at_the_revision_chosen_and_says_so(
    scoped: Any, knowledge: ClientKnowledgeRepository
) -> None:
    person = client_scope(scoped)
    item_id = _fact(knowledge, person, "Dealeři: 120")
    study = scoped.scope(user="researcher")
    knowledge.select_for_study(study, item_id=item_id, revision=1)
    before = knowledge.freeze_for_study(study)
    knowledge.add(person, kind=KnowledgeKind.FACT, title="Dealeři: 134", item_id=item_id)

    after = knowledge.freeze_for_study(study)
    [entry] = after.entries
    assert (entry.title, entry.revision, entry.current_revision) == ("Dealeři: 120", 1, 2)
    assert entry.state is ContextEntryState.SUPERSEDED
    # What is read did not change, so neither did the identity; the state is said beside it.
    assert after.sha256 == before.sha256

    # Chosen again at the new revision: the newer words, current, a new identity.
    knowledge.select_for_study(study, item_id=item_id, revision=2)
    again = knowledge.freeze_for_study(study)
    [entry] = again.entries
    assert (entry.title, entry.state) == ("Dealeři: 134", ContextEntryState.CURRENT)
    assert again.sha256 != after.sha256
    [selection] = knowledge.selections(study)
    assert selection.revision == 2


def test_an_item_no_longer_active_is_omitted_by_name(
    scoped: Any, knowledge: ClientKnowledgeRepository, session: Session
) -> None:
    person = client_scope(scoped)
    kept, retired = _fact(knowledge, person, "Zůstává"), _fact(knowledge, person, "Odchází")
    study = scoped.scope(user="researcher")
    for item_id in (kept, retired):
        knowledge.select_for_study(study, item_id=item_id, revision=1)
    # Retirement is K6's; the row's state is what the freeze reads.
    row = session.get(ClientKnowledgeItemRow, retired)
    assert row is not None
    row.status = "RETIRED"
    session.flush()
    frozen = knowledge.freeze_for_study(study)
    assert [e.item_id for e in frozen.entries] == [kept]
    [omitted] = frozen.omitted
    assert (omitted.item_id, omitted.revision, omitted.reason) == (
        retired,
        1,
        OmittedReason.RETIRED,
    )
    # A retired item cannot be chosen anew.
    with pytest.raises(ScopeDenied):
        knowledge.select_for_study(study, item_id=retired, revision=1)


def test_choices_never_cross_clients_or_studies(
    scoped: Any, knowledge: ClientKnowledgeRepository
) -> None:
    ours = _fact(knowledge, client_scope(scoped), "Acme: 120")
    theirs = _fact(knowledge, client_scope(scoped, "other_lead", "other"), "Globex: 9")
    study = scoped.scope(user="researcher")
    with pytest.raises(ScopeDenied):
        knowledge.select_for_study(study, item_id=theirs, revision=1)
    knowledge.select_for_study(study, item_id=ours, revision=1)
    # The sibling study of the same client chose nothing, and reads nothing.
    sibling = scoped.scope(user="researcher", study="sibling")
    assert knowledge.freeze_for_study(sibling).entries == ()
    other = scoped.scope(user="other_lead", study="other_client")
    assert knowledge.freeze_for_study(other).entries == ()
    assert knowledge.unselect_for_study(other, item_id=ours) is False
    assert [e.item_id for e in knowledge.freeze_for_study(study).entries] == [ours]


def test_choosing_needs_edit_rights_on_an_open_study_and_is_audited(
    scoped: Any, knowledge: ClientKnowledgeRepository, session: Session
) -> None:
    item_id = _fact(knowledge, client_scope(scoped), "Dealeři: 120")
    study = scoped.scope(user="researcher")
    knowledge.select_for_study(study, item_id=item_id, revision=1)
    assert knowledge.unselect_for_study(study, item_id=item_id) is True
    assert knowledge.selections(study) == []
    actions = session.scalars(
        select(AccessAuditRow.action).where(
            AccessAuditRow.study_id == study.study_id,
            AccessAuditRow.action.like("CLIENT_KNOWLEDGE_%SELECTED"),
        )
    ).all()
    assert sorted(actions) == ["CLIENT_KNOWLEDGE_SELECTED", "CLIENT_KNOWLEDGE_UNSELECTED"]

    read_only = study.__class__(
        **{
            **{f: getattr(study, f) for f in study.__dataclass_fields__},
            "permissions": frozenset({Permission.VIEW_STUDY}),
        }
    )
    with pytest.raises(ScopeDenied):
        knowledge.select_for_study(read_only, item_id=item_id, revision=1)

    row = session.get(StudyRow, study.study_id)
    assert row is not None
    row.status = "ARCHIVED"
    session.flush()
    with pytest.raises(ScopeDenied):
        knowledge.select_for_study(scoped.scope(user="researcher"), item_id=item_id, revision=1)


def test_a_selection_outside_the_studys_scope_is_omitted_by_name_never_skipped(
    scoped: Any, knowledge: ClientKnowledgeRepository, session: Session
) -> None:
    """Only a row written around the repository can do this; the freeze still names it."""
    theirs = _fact(knowledge, client_scope(scoped, "other_lead", "other"), "Globex: 9")
    study = scoped.scope(user="researcher")
    session.add(
        ClientKnowledgeSelectionRow(
            study_id=study.study_id,
            item_id=theirs,
            organization_id=study.organization_id,
            client_id=study.client_id,
            revision=1,
            selected_by=study.actor_id,
        )
    )
    session.flush()
    frozen = knowledge.freeze_for_study(study)
    assert frozen.entries == ()
    [omitted] = frozen.omitted
    assert (omitted.item_id, omitted.revision, omitted.reason) == (
        theirs,
        1,
        OmittedReason.UNAVAILABLE,
    )


def _entry(item_id: str, sha: str, state: ContextEntryState) -> FrozenKnowledgeEntry:
    return FrozenKnowledgeEntry(
        item_id=item_id,
        revision=1,
        kind=KnowledgeKind.FACT,
        title="t",
        author=KnowledgeAuthor.PERSON,
        sha256=sha,
        state=state,
        current_revision=1 if state is ContextEntryState.CURRENT else 2,
    )


def test_a_contexts_hash_covers_what_is_read_and_nothing_else() -> None:
    empty = FrozenKnowledgeContext.freeze(
        study_id="STD-1", client_id="CLI-1", entries=(), omitted=()
    )
    assert empty.version == CONTEXT_VERSION
    assert empty.sha256 == context_sha256(study_id="STD-1", client_id="CLI-1", entries=())
    assert empty.sha256 != context_sha256(study_id="STD-2", client_id="CLI-1", entries=())
    tampered = empty.model_copy(update={"client_id": "CLI-2"})
    assert not tampered.verify()

    current = _entry("KNW-1", "a" * 64, ContextEntryState.CURRENT)
    superseded = _entry("KNW-1", "a" * 64, ContextEntryState.SUPERSEDED)
    one = FrozenKnowledgeContext.freeze(
        study_id="STD-1", client_id="CLI-1", entries=(current,), omitted=()
    )
    # The item's state since, and what was left out, are said beside the hash, not in it.
    two = FrozenKnowledgeContext.freeze(
        study_id="STD-1",
        client_id="CLI-1",
        entries=(superseded,),
        omitted=(OmittedKnowledge(item_id="KNW-2", revision=1, reason=OmittedReason.RETIRED),),
    )
    assert one.sha256 == two.sha256
    other_words = _entry("KNW-1", "b" * 64, ContextEntryState.CURRENT)
    assert (
        FrozenKnowledgeContext.freeze(
            study_id="STD-1", client_id="CLI-1", entries=(other_words,), omitted=()
        ).sha256
        != one.sha256
    )


def test_verify_rehashes_each_entrys_words_and_the_context_keeps_its_own_copy() -> None:
    content: dict[str, Any] = {"quote": "Klient vede trh.", "locator": {"page": 1}}
    entry = FrozenKnowledgeEntry(
        item_id="KNW-1",
        revision=1,
        kind=KnowledgeKind.FACT,
        title="Vede trh",
        content=content,
        author=KnowledgeAuthor.AI,
        sha256=revision_sha256("Vede trh", "", content),
        state=ContextEntryState.CURRENT,
        current_revision=1,
    )
    frozen = FrozenKnowledgeContext.freeze(
        study_id="STD-1", client_id="CLI-1", entries=(entry,), omitted=()
    )
    assert frozen.verify()
    # The caller's dict changed after the freeze: the context holds its own copy.
    content["locator"]["page"] = 9
    assert frozen.entries[0].content["locator"] == {"page": 1}
    assert frozen.verify()
    # Words changed under an unchanged digest: verify re-hashes them and fails.
    changed = frozen.entries[0].model_copy(update={"content": {"quote": "Klient prohrává."}})
    tampered = frozen.model_copy(update={"entries": (changed,)})
    assert tampered.entries[0].sha256 == frozen.entries[0].sha256
    assert not tampered.verify()


def test_a_choice_changed_while_freezing_does_not_reach_the_freeze(
    scoped: Any, knowledge: ClientKnowledgeRepository, session: Session, engine: Any
) -> None:
    """The freeze reads the revisions it captured, never the live selection a second time."""
    from aia_core.infrastructure.db import create_session_factory

    if engine.dialect.name != "postgresql":
        pytest.skip("READ COMMITTED between two connections is PostgreSQL's")

    person = client_scope(scoped)
    item_id = _fact(knowledge, person, "Dealeři: 120")
    knowledge.add(person, kind=KnowledgeKind.FACT, title="Dealeři: 134", item_id=item_id)
    study = scoped.scope(user="researcher")
    knowledge.select_for_study(study, item_id=item_id, revision=2)
    session.commit()
    # A second connection moves the choice to revision 1 and commits after the freeze has read
    # the selection and before it reads the revisions. Before the fix the second read joined
    # the live selection and the item came back omitted, a choice nobody made.
    other_factory = create_session_factory(engine)
    real_rows = knowledge._selection_rows

    def rows_then_race(scope: Any) -> Any:
        captured = real_rows(scope)
        with other_factory() as other:
            row = other.get(ClientKnowledgeSelectionRow, (study.study_id, item_id))
            assert row is not None
            row.revision = 1
            other.commit()
        return captured

    knowledge._selection_rows = rows_then_race  # type: ignore[method-assign]
    frozen = knowledge.freeze_for_study(study)
    [entry] = frozen.entries
    assert (entry.revision, entry.title) == (2, "Dealeři: 134")
    assert frozen.omitted == ()
    assert frozen.verify()
