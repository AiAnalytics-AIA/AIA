"""LIVE's audience factor catalogue, as the audience step reads it (panel-grounded 6b).

The catalogue a new run's sample would be filtered by: the LIVE population's current
version, its kept catalogue (``population_ops record-catalogue``; never computed here, so
nothing here reads a respondent row), and the 18 built-in subpanels with their filters in
the filter's own language and whether this version's policy lets each be applied.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from ..domain.population import PopulationImportContract
from ..domain.population.audience import subpanel_filters
from ..domain.population.audience_catalogue import for_the_screen
from ..infrastructure.population_repository import PopulationRegistryRepository
from .population import kept_audience_catalogue
from .population_characteristics import SubpanelCharacteristics, version_characteristics

__all__ = ["LiveAudienceCatalogue", "live_audience_catalogue"]


@dataclass(frozen=True, slots=True)
class LiveAudienceCatalogue:
    """LIVE's version, its catalogue (``None`` while none is kept) and its subpanels."""

    version_id: str
    version_label: str
    catalogue: dict[str, Any] | None
    subpanels: tuple[SubpanelCharacteristics, ...]
    #: Each subpanel's filter as :func:`~..domain.population.audience.select_audience` takes it.
    subpanel_filters: dict[str, dict[str, Any]]


def live_audience_catalogue(
    session: Session,
    *,
    contract: PopulationImportContract,
    population_id: str,
    organization_id: str,
) -> LiveAudienceCatalogue | None:
    """``population_id``'s catalogue as it stands now, or ``None`` when it is not established.

    Reads the registry and what is kept; the version is the population's current one, as a
    run started now would record it.
    """
    registry = PopulationRegistryRepository(session)
    population = registry.population(population_id)
    if population is None:
        return None
    version_id = population.current_version_id
    kept = kept_audience_catalogue(registry, version_id)
    characteristics = version_characteristics(
        session,
        contract=contract,
        version_id=version_id,
        organization_id=organization_id,
    )
    return LiveAudienceCatalogue(
        version_id=version_id,
        version_label=characteristics.label,
        catalogue=for_the_screen(kept) if kept is not None else None,
        subpanels=characteristics.subpanels,
        subpanel_filters={
            sp.subpanel.key: subpanel_filters(sp.subpanel) for sp in characteristics.subpanels
        },
    )
