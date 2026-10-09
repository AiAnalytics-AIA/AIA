"""AIA-88: stale proposals cannot replace corrections, even under contention."""

from __future__ import annotations

import os
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import pytest
from sqlalchemy import func, select, text

from aia_core.application.scope import ScopeResolver
from aia_core.domain.knowledge import KnowledgeConflict, KnowledgeKind, ProposalStatus
from aia_core.infrastructure.client_knowledge_repository import ClientKnowledgeRepository
from aia_core.infrastructure.db import create_session_factory
from aia_core.infrastructure.tables import (
    AccessAuditRow,
    ClientKnowledgeItemRow,
    ClientKnowledgeProposalRow,
)


def _scope(scoped: Any, session: Any = None) -> Any:
    resolver = ScopeResolver(session) if session is not None else scoped.resolver
    return resolver.client_context(
        scoped.principal(scoped.users["researcher"]),
        client_id=scoped.clients["primary"].client_id,
    )


@pytest.mark.parametrize("from_study", [False, True], ids=["client", "study"])
def test_stale_acceptance_leaves_the_correction_and_pending_proposal_unchanged(
    session: Any, scoped: Any, from_study: bool
) -> None:
    repo = ClientKnowledgeRepository(session)
    scope = _scope(scoped)
    first = repo.add(scope, kind=KnowledgeKind.FACT, title="Original", content={"value": 1})
    assert first.base_revision is None
    propose = repo.propose_from_study if from_study else repo.propose
    pending = propose(
        scoped.scope() if from_study else scope,
        kind=KnowledgeKind.FACT,
        title="Earlier proposal",
        content={"value": 2},
        item_id=first.item_id,
    )
    assert pending.base_revision == 1
    repo.add(scope, kind=KnowledgeKind.FACT, title="New correction", item_id=first.item_id)
    before = session.scalar(select(func.count()).select_from(AccessAuditRow))
    with pytest.raises(KnowledgeConflict) as caught:
        repo.decide(scope, proposal_id=pending.proposal_id, approve=True)
    assert (caught.value.reason, caught.value.expected_revision, caught.value.current_revision) == (
        "stale_revision",
        1,
        2,
    )
    # Committing a caught refusal must not commit an accidentally dirtied approval.
    session.commit()
    with create_session_factory(session.bind)() as fresh:
        read = ClientKnowledgeRepository(fresh)
        fresh_scope = _scope(scoped, fresh)
        [item] = read.items(fresh_scope)
        assert (item.title, item.revision) == ("New correction", 2)
        kept = next(p for p in read.proposals(fresh_scope) if p.proposal_id == pending.proposal_id)
        assert kept.status is ProposalStatus.PROPOSED
        assert kept.decided_by is None and kept.decided_at is None and kept.revision is None
        assert [r.revision for r in read.revisions(fresh_scope, item_id=item.item_id)] == [1, 2]
        assert read.summary(fresh_scope).context_revision == 2
        assert fresh.scalar(select(func.count()).select_from(AccessAuditRow)) == before

    # Explicit re-proposal against the corrected revision, not automatic merge.
    replacement = repo.propose(
        scope,
        kind=KnowledgeKind.FACT,
        title="Reviewed again",
        item_id=first.item_id,
        base_revision=2,
    )
    assert replacement.proposal_id != pending.proposal_id and replacement.base_revision == 2
    assert repo.decide(scope, proposal_id=replacement.proposal_id, approve=True).revision == 3
    assert (
        repo.decide(scope, proposal_id=pending.proposal_id, approve=False).status
        is ProposalStatus.REJECTED
    )


@pytest.mark.parametrize("write", ["add", "propose", "propose_from_study"])
def test_a_known_stale_base_is_refused_before_a_proposal_is_created(
    session: Any, scoped: Any, write: str
) -> None:
    repo = ClientKnowledgeRepository(session)
    scope = _scope(scoped)
    first = repo.add(scope, kind=KnowledgeKind.FACT, title="Original")
    repo.add(scope, kind=KnowledgeKind.FACT, title="Correction", item_id=first.item_id)
    before = len(repo.proposals(scope))
    with pytest.raises(KnowledgeConflict):
        getattr(repo, write)(
            scoped.scope() if write == "propose_from_study" else scope,
            kind=KnowledgeKind.FACT,
            title="Stale",
            item_id=first.item_id,
            base_revision=1,
        )
    assert len(repo.proposals(scope)) == before
    assert repo.items(scope)[0].title == "Correction"


@pytest.mark.parametrize("invalid", [0, -1, 1])
def test_invalid_or_itemless_base_is_refused(session: Any, scoped: Any, invalid: int) -> None:
    with pytest.raises(ValueError):
        ClientKnowledgeRepository(session).propose(
            _scope(scoped), kind=KnowledgeKind.FACT, title="New", base_revision=invalid
        )


def test_a_legacy_pending_edit_has_no_guessed_base_and_can_be_rejected(
    session: Any, scoped: Any
) -> None:
    repo = ClientKnowledgeRepository(session)
    scope = _scope(scoped)
    first = repo.add(scope, kind=KnowledgeKind.FACT, title="Original")
    pending = repo.propose(
        scope, kind=KnowledgeKind.FACT, title="Legacy edit", item_id=first.item_id
    )
    row = session.get(ClientKnowledgeProposalRow, pending.proposal_id)
    assert row is not None
    row.base_revision = None  # A row persisted before the migration.
    session.commit()
    with pytest.raises(KnowledgeConflict) as caught:
        repo.decide(scope, proposal_id=pending.proposal_id, approve=True)
    assert caught.value.reason == "missing_base_revision"
    assert repo.items(scope)[0].revision == 1
    assert (
        repo.decide(scope, proposal_id=pending.proposal_id, approve=False).status
        is ProposalStatus.REJECTED
    )


@pytest.mark.postgres
@pytest.mark.parametrize("race", ["same-item", "same-proposal", "different-items"])
def test_competing_acceptances_use_fresh_locked_rows_and_unique_context_revisions(
    engine: Any, session: Any, scoped: Any, race: str
) -> None:
    if engine.dialect.name != "postgresql":
        if os.environ.get("AIA_REQUIRE_POSTGRES") == "1":
            pytest.fail("AIA-88 contention requires real PostgreSQL")
        pytest.skip("AIA-88 contention requires real PostgreSQL")
    repo = ClientKnowledgeRepository(session)
    scope = _scope(scoped)
    first = repo.add(scope, kind=KnowledgeKind.FACT, title="Original")
    other = (
        repo.add(scope, kind=KnowledgeKind.FACT, title="Other")
        if race == "different-items"
        else first
    )
    a = repo.propose(scope, kind=KnowledgeKind.FACT, title="Proposal A", item_id=first.item_id)
    b = (
        repo.propose(scope, kind=KnowledgeKind.FACT, title="Proposal B", item_id=other.item_id)
        if race != "same-proposal"
        else a
    )
    session.commit()
    factory = create_session_factory(engine)
    barrier = threading.Barrier(2)

    def accept(proposal_id: str) -> str:
        with factory() as worker:
            worker_scope = _scope(scoped, worker)
            # Deliberately preload the pending row before either transaction decides.
            assert worker.get(ClientKnowledgeProposalRow, proposal_id).status == "PROPOSED"
            proposal = worker.get(ClientKnowledgeProposalRow, proposal_id)
            assert worker.get(ClientKnowledgeItemRow, proposal.item_id).current_revision == 1
            worker.execute(text("SET LOCAL lock_timeout = '5s'"))
            barrier.wait(timeout=5)
            try:
                ClientKnowledgeRepository(worker).decide(
                    worker_scope, proposal_id=proposal_id, approve=True
                )
                worker.commit()
                return "approved"
            except KnowledgeConflict:
                worker.rollback()
                return "stale"
            except ValueError:
                worker.rollback()
                return "decided"

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(accept, p.proposal_id) for p in (a, b)]
        outcomes = sorted(f.result(timeout=15) for f in futures)
    assert (
        outcomes
        == {
            "same-item": ["approved", "stale"],
            "same-proposal": ["approved", "decided"],
            "different-items": ["approved", "approved"],
        }[race]
    )
    session.expire_all()
    history = [r for item in repo.items(scope) for r in repo.revisions(scope, item_id=item.item_id)]
    assert sorted(r.context_revision for r in history) == list(range(1, len(history) + 1))
    assert all(item.revision == 2 for item in repo.items(scope))
    if race == "same-item":
        assert len(repo.proposals(scope, status=ProposalStatus.PROPOSED)) == 1
