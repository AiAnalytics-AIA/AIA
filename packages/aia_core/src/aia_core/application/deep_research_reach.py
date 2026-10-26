"""Settings → Deep Research → Dosah (deep-research-web-search 52, settings-backends SB6): what
the newest worker's composition reaches, as it stands for the organization asking.

The worker recorded each route it composed or did not; this adds what only the organization
holds: whether its approved settings let a priced route run (ADR 0022), and, for a data class
asked, which routes do not take it. Any member reads it. Read-only.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from ..domain.deep_research_reach import RouteReach, for_organization
from ..domain.residency import DataClass
from ..domain.scope import OrganizationContext
from ..infrastructure.deep_research_composition_repository import (
    Composition,
    DeepResearchCompositions,
)
from ..infrastructure.deep_research_settings_repository import DeepResearchSettingsReader

__all__ = ["Reach", "deep_research_reach"]


@dataclass(frozen=True, slots=True)
class Reach:
    #: ``None``: no worker has recorded a composition yet (nothing is presumed reachable).
    composition: Composition | None
    missing_for_live: tuple[str, ...]
    routes: list[RouteReach]


def deep_research_reach(
    session: Session, reader: OrganizationContext, *, data_class: DataClass | None = None
) -> Reach:
    missing = tuple(
        sorted(DeepResearchSettingsReader(session, reader).effective().missing_for_live())
    )
    composition = DeepResearchCompositions(session, reader).latest()
    if composition is None:
        return Reach(None, missing, [])
    return Reach(
        composition,
        missing,
        for_organization(
            composition.routes,
            missing_for_live=missing,
            data_class=data_class,
            class_gates_advisory=composition.class_gates == "advisory",
        ),
    )
