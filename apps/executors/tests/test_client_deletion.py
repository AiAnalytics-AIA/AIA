"""Deleting a client end to end (settings-backends SB5; the owner, 2026-10-22: content gone,
ledgers kept).

A client with knowledge, a kept source, a study's working copy and a Lead turn the real worker
answered (a run, its artifacts and their objects, usage rows) is deleted: every content row and
stored object is gone; the usage ledger, the approval ledger and the audit stay, the client's
and study's names replaced by their ids; the client resolves no scope again.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from aia_core.application.client_deletion import delete_client, delete_objects, deletion_preview
from aia_core.application.scope import AuthenticatedPrincipal, ScopeResolver
from aia_core.domain.knowledge import KnowledgeKind
from aia_core.domain.scope import ScopeDenied
from aia_core.infrastructure.client_knowledge_repository import (
    ClientKnowledgeRepository,
    count_client_knowledge,
)
from aia_core.infrastructure.client_source_repository import (
    ClientSourceRepository,
    count_client_sources,
)
from aia_core.infrastructure.repositories import client_projects
from aia_core.infrastructure.storage import ObjectNotFound
from aia_core.infrastructure.tables import (
    AccessAuditRow,
    AIUsageEventRow,
    ClientRow,
    ProjectArtifactRow,
    StudyRow,
)
from sqlalchemy import select
from test_research_lead_executor import (  # type: ignore[import-not-found]
    REPLY,
    RecordedBedrock,
    hatch,
    post,
    worker,
)


def _client_scope(world: Any, session: Any) -> Any:
    return ScopeResolver(session).client_context(
        AuthenticatedPrincipal(user_id=world.lead_id, organization_id=world.organization_id),
        client_id=world.client_id,
    )


def test_a_deleted_client_leaves_its_ledgers_and_nothing_else(
    world: Any, database_url: str, store: Any, build: Any
) -> None:
    hatch(world)
    post(world)
    assert worker(world, database_url, store, build, RecordedBedrock([REPLY])).run_once()
    with world.sessions() as session:
        scope = _client_scope(world, session)
        ClientKnowledgeRepository(session).add(
            scope, kind=KnowledgeKind.FACT, title="Fiktivní fakt", summary="Jen pro test."
        )
        ClientSourceRepository(session, store).add(
            scope, filename="poznamky.txt", data=b"Fiktivni poznamky klienta."
        )
        study = session.get(StudyRow, world.study_id)
        study.name = "Fiktivní studie Alfa"  # the world's "S" is in every id
        client = session.get(ClientRow, world.client_id)
        study_name, client_name = study.name, client.name
        keys = list(session.scalars(select(ProjectArtifactRow.storage_key)))
        usage_before = len(session.scalars(select(AIUsageEventRow)).all())
        session.commit()
    assert keys and usage_before
    for key in keys:
        store.get(key)  # stored

    now = datetime.now(UTC)
    with world.sessions() as session:
        admin = world.admin_context(session)
        preview = deletion_preview(session, admin, world.client_id, now=now)
        assert preview is not None
        assert preview.deleted["studies"] == 1 and preview.deleted["knowledge_items"] == 1
        assert preview.deleted["sources"] == 1 and preview.deleted["runs"] >= 1
        assert preview.kept["usage_rows"] >= usage_before
        session.commit()
        token = preview.confirm_token

    with world.sessions() as session:
        admin = world.admin_context(session)
        done = delete_client(session, admin, world.client_id, confirm_token=token, now=now)
        session.commit()
    assert not done.already_deleted and done.object_keys
    assert delete_objects(store, done.object_keys) == 0

    with world.sessions() as session:
        assert count_client_knowledge(session, client_id=world.client_id) == 0
        assert count_client_sources(session, client_id=world.client_id) == 0
        assert client_projects(session, client_id=world.client_id).projects == 0
        # The money ledger stays, and still names the client and study by id.
        assert len(session.scalars(select(AIUsageEventRow)).all()) == usage_before
        tomb = session.get(ClientRow, world.client_id)
        assert tomb.name == world.client_id and tomb.deleted_at is not None
        assert session.get(StudyRow, world.study_id).name == world.study_id
        audit = session.scalars(select(AccessAuditRow)).all()
        leaks = [
            (a.action, a.payload)
            for a in audit
            if client_name in str(a.payload) or study_name in str(a.payload)
        ]
        assert leaks == []
        added = next(a for a in audit if a.action == "CLIENT_SOURCE_ADDED")
        assert added.payload["filename"] == "erased"  # the client's text is gone, codes stay
        assert added.payload["outcome"] == "READ"
        assert next(a.payload for a in audit if a.action == "CLIENT_DELETED")["studies"] == 1
        with pytest.raises(ScopeDenied):
            _client_scope(world, session)
    for key in keys:
        with pytest.raises(ObjectNotFound):
            store.get(key)

    # Again: nothing to delete, said so; the spent confirmation is not asked for.
    with world.sessions() as session:
        again = delete_client(
            session, world.admin_context(session), world.client_id, confirm_token="x", now=now
        )
    assert again.already_deleted


def test_a_confirmation_is_the_askers_for_this_client_once_and_for_ten_minutes(
    world: Any,
) -> None:
    now = datetime.now(UTC)
    with world.sessions() as session:
        admin = world.admin_context(session)
        preview = deletion_preview(session, admin, world.client_id, now=now)
        assert preview is not None
        session.commit()
    with world.sessions() as session:
        admin = world.admin_context(session)
        with pytest.raises(ScopeDenied) as late:
            delete_client(
                session,
                admin,
                world.client_id,
                confirm_token=preview.confirm_token,
                now=now + timedelta(minutes=11),
            )
        assert late.value.reason == "confirmation_expired"
        session.rollback()
        with pytest.raises(ScopeDenied) as wrong:
            delete_client(session, admin, world.client_id, confirm_token="forged", now=now)
        assert wrong.value.reason == "confirmation_invalid"
        session.rollback()
    with world.sessions() as session:
        member = ScopeResolver(session).organization_context(
            AuthenticatedPrincipal(user_id=world.lead_id, organization_id=world.organization_id)
        )
        with pytest.raises(ScopeDenied) as role:
            deletion_preview(session, member, world.client_id, now=now)
        assert role.value.reason == "insufficient_role"
