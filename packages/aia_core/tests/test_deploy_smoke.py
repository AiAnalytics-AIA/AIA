"""A deploy's smoke results, read and kept (settings-backends SB4).

Only a check's label and result are kept: a detail line, an ``info`` line and the closing
verdict are no check. Settings lists what is not ready first; a NOT_RUNNABLE check is never
a pass.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from aia_core.domain.deploy_smoke import (
    MAX_LABEL,
    SmokeCheck,
    SmokeStatus,
    parse_smoke_lines,
)
from aia_core.domain.scope import ScopeDenied
from aia_core.infrastructure.deploy_smoke_repository import DeploySmokeRepository, record_smoke_run

LINES = """Smoke: https://aia-develop.example expecting build abc1234

ok    web: / opens AIA (302 /app/clients), not the 18.6.6 document
FAIL  api: /health is ok
      {"status": "down", "detail": "Authorization: Bearer secret"}
info  host: no 18.6.6 working volume on this host (aia_legacy_state)
NOT_RUNNABLE  ai: a paid model call
      the smoke makes no paid model call
ok    worker: container is running
warn  smoke: results not kept; Settings shows the previous run

smoke: FAILED
"""


def test_only_check_lines_are_read_and_no_detail_is_kept() -> None:
    checks = parse_smoke_lines(LINES.splitlines(keepends=True))
    assert checks == [
        SmokeCheck("web: / opens AIA (302 /app/clients), not the 18.6.6 document", SmokeStatus.OK),
        SmokeCheck("api: /health is ok", SmokeStatus.FAIL),
        SmokeCheck("ai: a paid model call", SmokeStatus.NOT_RUNNABLE),
        SmokeCheck("worker: container is running", SmokeStatus.OK),
    ]
    assert "Bearer" not in repr(checks)


def test_a_long_label_is_cut_not_dropped() -> None:
    [check] = parse_smoke_lines(["ok    " + "x" * 400])
    assert len(check.label) == MAX_LABEL


def test_the_latest_run_is_read_not_ready_first(scoped: Any, session: Any) -> None:
    then = datetime(2026, 10, 22, 21, 0, tzinfo=UTC)
    record_smoke_run(
        session,
        run_id="SMK-old",
        build_sha="aaaaaaa",
        checks=[SmokeCheck("old", SmokeStatus.FAIL)],
        ran_at=then,
    )
    record_smoke_run(
        session,
        run_id="SMK-new",
        build_sha="bbbbbbb",
        checks=parse_smoke_lines(LINES.splitlines()),
        ran_at=then + timedelta(hours=1),
    )
    latest = DeploySmokeRepository(session, scoped.admin_context).latest()
    assert latest is not None
    assert (latest.run_id, latest.build_sha) == ("SMK-new", "bbbbbbb")
    assert [c.status for c in latest.checks] == [
        SmokeStatus.FAIL,
        SmokeStatus.NOT_RUNNABLE,
        SmokeStatus.OK,
        SmokeStatus.OK,
    ]
    assert latest.checks[2].label.startswith("web: /")  # passes keep the smoke's order


def test_nothing_kept_reads_none_and_only_an_administrator_reads(scoped: Any, session: Any) -> None:
    assert DeploySmokeRepository(session, scoped.admin_context).latest() is None
    member = scoped.resolver.organization_context(scoped.principal(scoped.users["researcher"]))
    with pytest.raises(ScopeDenied):
        DeploySmokeRepository(session, member)


def test_the_seeds_smoke_organization_is_no_tenant_on_develop_only(
    scoped: Any, session: Any
) -> None:
    """Deployment state is read by an organization's admin only while it is the one tenant; on
    develop the seed's synthetic smoke organization is the deployment's own and not counted."""
    from aia_core.application.develop_seed import SMOKE_ORGANIZATION_SLUG
    from aia_core.application.system_status import latest_smoke_run
    from aia_core.domain.deployment import DeploymentEnvironment

    admin = scoped.admin_context
    assert latest_smoke_run(session, admin, environment=DeploymentEnvironment.TEST) is None
    scoped.scope_repo.create_organization(
        slug=SMOKE_ORGANIZATION_SLUG, name="Smoke", owner_email="s@example.invalid"
    )
    assert latest_smoke_run(session, admin, environment=DeploymentEnvironment.DEVELOP) is None
    with pytest.raises(ScopeDenied) as shared:
        latest_smoke_run(session, admin, environment=DeploymentEnvironment.TEST)
    assert shared.value.reason == "deployment_shared"
