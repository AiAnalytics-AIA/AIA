"""The last OWNER survives two owners demoting each other at once (security-audit-2026-10 S14).

``ScopeRepository._guard_owner`` counts the organization's active OWNERs before it lets one be
demoted or deactivated. Under READ COMMITTED a plain count lets two such changes each see the
other OWNER and both commit, leaving none -- and with no OWNER, nobody may grant OWNER again.
The organization row is locked first, so the second change waits and then counts what the
first committed.
"""

from __future__ import annotations

import threading
import time
from typing import Any

import pytest
from sqlalchemy.orm import Session

from aia_core.application.scope import AuthenticatedPrincipal, ScopeResolver
from aia_core.domain.scope import OrganizationRole, ScopeDenied
from aia_core.infrastructure.scope_repository import ScopeRepository


@pytest.fixture
def postgres(engine: Any) -> Any:
    if engine.dialect.name != "postgresql":
        pytest.skip("row locks are PostgreSQL's; SQLite serialises writers")
    return engine


def test_two_owners_demoting_each_other_at_once_leave_one(postgres: Any, session: Session) -> None:
    from aia_core.infrastructure.db import create_session_factory

    repo = ScopeRepository(session)
    org, first = repo.create_organization(
        slug="race", name="Race", owner_email="a@art-chain.io", owner_name="A"
    )
    admin = ScopeResolver(session).organization_context(
        AuthenticatedPrincipal(user_id=first.user_id, organization_id=org.organization_id)
    )
    second = repo.add_member(admin, email="b@art-chain.io", role=OrganizationRole.OWNER)
    session.commit()

    factory = create_session_factory(postgres)
    barrier = threading.Barrier(2)
    outcomes: list[str] = []
    errors: list[BaseException] = []
    lock = threading.Lock()

    def demote(actor: str, target_email: str) -> None:
        try:
            with factory() as own:
                context = ScopeResolver(own).organization_context(
                    AuthenticatedPrincipal(user_id=actor, organization_id=org.organization_id)
                )
                barrier.wait(30)
                try:
                    ScopeRepository(own).add_member(
                        context, email=target_email, role=OrganizationRole.ADMIN
                    )
                    time.sleep(0.2)  # hold the decision open: a racer must wait, not pass
                    own.commit()
                    result = "demoted"
                except ScopeDenied as exc:
                    own.rollback()
                    result = exc.reason
            with lock:
                outcomes.append(result)
        except BaseException as exc:  # reported below, never swallowed
            errors.append(exc)

    threads = [
        threading.Thread(target=demote, args=(first.user_id, "b@art-chain.io")),
        threading.Thread(target=demote, args=(second.user_id, "a@art-chain.io")),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(60)
    assert not errors, errors
    assert sorted(outcomes) == ["demoted", "last_owner"]
    session.expire_all()
    owners = [
        m for m in repo.members(admin) if m["organization_role"] == OrganizationRole.OWNER.value
    ]
    assert len(owners) == 1
