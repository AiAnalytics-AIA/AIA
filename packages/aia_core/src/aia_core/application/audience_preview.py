"""The audience step's preview, counted in the API process (panel-grounded-respondents 6c).

The owner chose to count in the API (2026-10-12): the API loads LIVE itself, through the one
loader (:class:`~.population.PopulationRuntime`, every hash re-verified, the ANALYSIS view),
and answers with :func:`~..domain.population.audience_preview.audience_preview` -- counts and
the sampler's verdict, never a row.

A population is loaded once per process and version and kept while that version is LIVE's;
when LIVE moves, the next preview loads the new version and the old one is let go. Loading
is serialised by a lock, so concurrent previews never load twice.
"""

from __future__ import annotations

import threading
from collections.abc import Mapping
from typing import Any

from sqlalchemy.orm import Session

from ..domain.population import (
    PopulationImportContract,
    PopulationSelector,
    PopulationView,
    RuntimePopulation,
)
from ..domain.population.audience_preview import audience_preview
from ..infrastructure.population_repository import PopulationRegistryRepository
from ..infrastructure.population_source import PopulationAssetSource
from .population import Enricher, PopulationRuntime

__all__ = ["AudiencePreviewer"]


class AudiencePreviewer:
    """Counts an audience in the population ``population_id`` stands on now."""

    def __init__(
        self,
        *,
        contract: PopulationImportContract,
        source: PopulationAssetSource,
        enricher: Enricher,
        population_id: str,
    ) -> None:
        self._contract = contract
        self._source = source
        self._enricher = enricher
        self._population_id = population_id
        self._lock = threading.Lock()
        self._loaded: RuntimePopulation | None = None

    def _population(self, session: Session) -> RuntimePopulation | None:
        registry = PopulationRegistryRepository(session)
        population = registry.population(self._population_id)
        if population is None:
            return None
        with self._lock:
            loaded = self._loaded
            if loaded is None or loaded.binding.version_id != population.current_version_id:
                self._loaded = None  # let the old version go before the new one loads
                runtime = PopulationRuntime(
                    session, contract=self._contract, source=self._source, enricher=self._enricher
                )
                loaded = runtime.load(
                    runtime.resolve(
                        PopulationSelector.population(self._population_id),
                        view=PopulationView.ANALYSIS,
                    )
                )
                self._loaded = loaded
            return loaded

    def preview(
        self, session: Session, filters: Mapping[str, Any] | None, n: int | None
    ) -> dict[str, Any] | None:
        """The preview's answer, with the version it was counted on; ``None`` without LIVE."""
        population = self._population(session)
        if population is None:
            return None
        answer = audience_preview(population, filters, n)
        return {
            "version_id": population.binding.version_id,
            "version_label": population.binding.version_label,
            **answer,
        }
