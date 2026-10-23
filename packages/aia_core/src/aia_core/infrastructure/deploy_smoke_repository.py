"""A deploy's smoke results (settings-backends SB4): the ONLY reader and writer of
``deploy_smoke_results``.

Written by the operator command ``aia_executors.smoke_record`` after ``bin/smoke.sh`` ran on
the host, acting as no one (as the seed does): the smoke proves the deployment, which is no
organization's. Read by an organization OWNER or ADMIN for Settings → Stav systému: the latest
run only.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..domain.deploy_smoke import SmokeCheck, SmokeStatus, order_checks
from ..domain.scope import OrganizationContext
from .tables import DeploySmokeResultRow, as_utc

__all__ = ["DeploySmokeRepository", "SmokeRun", "record_smoke_run"]


@dataclass(frozen=True, slots=True)
class SmokeRun:
    run_id: str
    build_sha: str
    ran_at: datetime
    #: Not ready first (FAIL, NOT_RUNNABLE), then the passes, each in the smoke's order.
    checks: list[SmokeCheck]


def record_smoke_run(
    session: Session,
    *,
    run_id: str,
    build_sha: str,
    checks: Sequence[SmokeCheck],
    ran_at: datetime,
) -> int:
    """Keep one smoke run's checks; the caller commits. Returns how many were kept."""
    for position, check in enumerate(checks):
        session.add(
            DeploySmokeResultRow(
                run_id=run_id,
                build_sha=build_sha,
                position=position,
                check_label=check.label,
                status=check.status.value,
                ran_at=ran_at,
            )
        )
    session.flush()
    return len(checks)


class DeploySmokeRepository:
    """Read-only, for an organization OWNER or ADMIN."""

    def __init__(self, session: Session, admin: OrganizationContext) -> None:
        if not isinstance(admin, OrganizationContext):
            raise TypeError("DeploySmokeRepository requires an issued OrganizationContext")
        admin.require_administer()
        self._session = session

    def latest(self) -> SmokeRun | None:
        """The newest smoke run, or ``None`` when none has been kept."""
        newest = self._session.execute(
            select(DeploySmokeResultRow.run_id)
            .order_by(DeploySmokeResultRow.ran_at.desc(), DeploySmokeResultRow.result_id.desc())
            .limit(1)
        ).scalar_one_or_none()
        if newest is None:
            return None
        rows = self._session.scalars(
            select(DeploySmokeResultRow).where(DeploySmokeResultRow.run_id == newest)
        ).all()
        ran_at = as_utc(rows[0].ran_at)
        return SmokeRun(
            run_id=newest,
            build_sha=rows[0].build_sha,
            ran_at=ran_at,
            checks=order_checks(
                (r.position, SmokeCheck(r.check_label, SmokeStatus(r.status))) for r in rows
            ),
        )
