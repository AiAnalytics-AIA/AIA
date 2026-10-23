"""An approval and a withdrawal of the same proposal at once: exactly one wins (#841 review).

Each checked the other with a plain SELECT. Under READ COMMITTED both passed and both
committed, leaving a withdrawn version in force, which every later run would then pin
(``_in_force`` reads no decline). Both now lock the version row before their checks.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from typing import Any

import pytest
from sqlalchemy.orm import Session

from aia_core.application.scope import AuthenticatedPrincipal, ScopeResolver
from aia_core.domain.scope import OrganizationContext, OrganizationRole
from aia_core.infrastructure.deep_research_settings_repository import (
    DeepResearchSettingsReader,
    DeepResearchSettingsRepository,
    SettingRefused,
)
from aia_core.infrastructure.scope_repository import ScopeRepository

RETENTION = "retention.snapshots"


@pytest.fixture
def postgres(engine: Any) -> Any:
    if engine.dialect.name != "postgresql":
        pytest.skip("row locks are PostgreSQL's; SQLite serialises writers")
    return engine


def test_an_approval_and_a_withdrawal_of_one_proposal_never_both_commit(
    postgres: Any, session: Session
) -> None:
    from aia_core.infrastructure.db import create_session_factory

    repo = ScopeRepository(session)
    org, first = repo.create_organization(
        slug="race-decline", name="Race", owner_email="a@art-chain.io", owner_name="A"
    )
    resolver = ScopeResolver(session)

    def context(user_id: str, s: Session) -> OrganizationContext:
        return ScopeResolver(s).organization_context(
            AuthenticatedPrincipal(user_id=user_id, organization_id=org.organization_id)
        )

    owner = resolver.organization_context(
        AuthenticatedPrincipal(user_id=first.user_id, organization_id=org.organization_id)
    )
    second = repo.add_member(owner, email="b@art-chain.io", role=OrganizationRole.ADMIN)
    DeepResearchSettingsRepository(session, owner).propose(RETENTION, 90)
    session.commit()

    factory = create_session_factory(postgres)
    barrier = threading.Barrier(2)
    outcomes: list[str] = []
    errors: list[BaseException] = []
    lock = threading.Lock()

    def act(
        name: str, user_id: str, change: Callable[[DeepResearchSettingsRepository], object]
    ) -> None:
        try:
            with factory() as own:
                settings = DeepResearchSettingsRepository(own, context(user_id, own))
                barrier.wait(30)
                try:
                    change(settings)
                    time.sleep(0.3)  # hold the decision open: the other must wait, not pass
                    own.commit()
                    result = name
                except SettingRefused as exc:
                    own.rollback()
                    result = exc.reason
            with lock:
                outcomes.append(result)
        except BaseException as exc:  # reported below, never swallowed
            errors.append(exc)

    threads = [
        threading.Thread(
            target=act, args=("approved", second.user_id, lambda r: r.approve(RETENTION, 1))
        ),
        threading.Thread(
            target=act,
            args=("withdrawn", first.user_id, lambda r: r.decline(RETENTION, 1, reason="zpět")),
        ),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(60)
    assert not errors, errors
    assert sorted(outcomes) in (
        ["approved", "version_not_pending"],
        ["version_declined", "withdrawn"],
    )
    session.expire_all()
    [version] = DeepResearchSettingsReader(session, owner).versions(RETENTION)
    assert version.state in ("IN_FORCE", "WITHDRAWN")
