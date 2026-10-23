"""Deep Research compositions (deep-research-web-search 52, settings-backends SB6): the ONLY
reader and writer of ``deep_research_compositions``.

Written once per worker start by ``aia_executors.deep_research_reach.record_reach``, acting as
no one: a worker's composition is the deployment's, no organization's. Read by any member of an
organization for Settings → Deep Research → Dosah: the newest record.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..domain.deep_research_reach import RouteReach, reach_from_record, reach_record
from ..domain.scope import OrganizationContext
from .tables import DeepResearchCompositionRow, as_utc

__all__ = ["Composition", "DeepResearchCompositions", "record_composition"]


@dataclass(frozen=True, slots=True)
class Composition:
    worker: str
    build_sha: str | None
    composed_at: datetime
    agent_directed: bool
    #: ``enforce`` or ``advisory`` (AIA_DATA_CLASS_GATES); ``None``: Deep Research not composed.
    class_gates: str | None
    routes: list[RouteReach]


def record_composition(
    session: Session,
    *,
    worker: str,
    build_sha: str | None,
    composed_at: datetime,
    agent_directed: bool,
    class_gates: str | None,
    routes: Sequence[RouteReach],
) -> None:
    """Keep one worker start's composition; the caller commits."""
    session.add(
        DeepResearchCompositionRow(
            worker=worker,
            build_sha=build_sha,
            composed_at=composed_at,
            agent_directed=agent_directed,
            class_gates=class_gates,
            routes=reach_record(routes),
        )
    )
    session.flush()


class DeepResearchCompositions:
    """Read-only, for any member of an organization."""

    def __init__(self, session: Session, reader: OrganizationContext) -> None:
        if not isinstance(reader, OrganizationContext):
            raise TypeError("DeepResearchCompositions requires an issued OrganizationContext")
        self._session = session

    def latest(self) -> Composition | None:
        """The newest worker start's composition, or ``None`` when no worker recorded one."""
        row = self._session.scalar(
            select(DeepResearchCompositionRow)
            .order_by(
                DeepResearchCompositionRow.composed_at.desc(),
                DeepResearchCompositionRow.composition_id.desc(),
            )
            .limit(1)
        )
        if row is None:
            return None
        return Composition(
            worker=row.worker,
            build_sha=row.build_sha,
            composed_at=as_utc(row.composed_at),
            agent_directed=row.agent_directed,
            class_gates=row.class_gates,
            routes=reach_from_record(row.routes),
        )
