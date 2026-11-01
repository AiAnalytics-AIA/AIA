"""A deactivation and a role change of the same OWNER at once never deadlock (SB2 review).

``deactivate_member`` locked the member row, then the organization row in ``_guard_owner``;
``add_member`` takes the organization row, then writes the member row. Run together on one
OWNER, each held the lock the other waited for, and PostgreSQL broke the deadlock by failing
one with an error that is not a refusal. Both now lock the organization row first.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

import pytest
from sqlalchemy.orm import Session

from aia_core.application.membership import deactivate_member
from aia_core.application.scope import AuthenticatedPrincipal, ScopeResolver
from aia_core.domain.scope import OrganizationContext, OrganizationRole, ScopeDenied
from aia_core.infrastructure.scope_repository import ScopeRepository


@pytest.fixture
def postgres(engine: Any) -> Any:
    if engine.dialect.name != "postgresql":
        pytest.skip("row locks are PostgreSQL's; SQLite serialises writers")
    return engine


def test_deactivating_and_demoting_one_owner_at_once_only_ever_refuse(
    postgres: Any, session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    from aia_core.infrastructure.db import create_session_factory

    # The deactivation pauses between finding its member and the OWNER rule, so the role
    # change reaches its locks in between: the interleaving that deadlocked, every time.
    slow = threading.local()
    guard = ScopeRepository._guard_owner

    def paused(self: ScopeRepository, *args: Any, **kwargs: Any) -> None:
        if getattr(slow, "on", False):
            time.sleep(0.5)
        guard(self, *args, **kwargs)

    monkeypatch.setattr(ScopeRepository, "_guard_owner", paused)

    repo = ScopeRepository(session)
    org, first = repo.create_organization(
        slug="race-deactivate", name="Race", owner_email="a@art-chain.io", owner_name="A"
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

    def act(
        name: str, change: Callable[[Session, OrganizationContext], object], pause: bool
    ) -> None:
        slow.on = pause
        try:
            with factory() as own:
                context = ScopeResolver(own).organization_context(
                    AuthenticatedPrincipal(
                        user_id=first.user_id, organization_id=org.organization_id
                    )
                )
                barrier.wait(30)
                try:
                    change(own, context)
                    time.sleep(0.2)  # hold the decision open: a racer must wait, not pass
                    own.commit()
                    result = name
                except ScopeDenied as exc:
                    own.rollback()
                    result = exc.reason
            with lock:
                outcomes.append(result)
        except BaseException as exc:  # a deadlock lands here, reported below
            errors.append(exc)

    threads = [
        threading.Thread(
            target=act,
            args=(
                "deactivated",
                lambda s, c: deactivate_member(s, c, user_id=second.user_id, now=datetime.now(UTC)),
                True,
            ),
        ),
        threading.Thread(
            target=act,
            args=(
                "demoted",
                lambda s, c: ScopeRepository(s).add_member(
                    c, email="b@art-chain.io", role=OrganizationRole.ADMIN
                ),
                False,
            ),
        ),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(60)
    assert not errors, errors
    # Either order is sound: demoted first, then the ADMIN deactivated; or deactivated first,
    # then the demotion refused, B no longer counting as an active OWNER.
    assert sorted(outcomes) in (["deactivated", "demoted"], ["deactivated", "last_owner"])
