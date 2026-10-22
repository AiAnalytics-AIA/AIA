"""The audience step's preview, counted in the API process (panel-grounded-respondents 6c).

The owner chose to count in the API (2026-10-12): the API loads LIVE itself, through the one
loader (:class:`~.population.PopulationRuntime`, every hash re-verified, the ANALYSIS view),
and answers with :func:`~..domain.population.audience_preview.audience_preview` -- counts and
the sampler's verdict, never a row.

A population is loaded once per process and version and kept while that version is LIVE's;
when LIVE moves, the next preview loads the new version and the old one is let go. Loading
is serialised by a lock, so concurrent previews never load twice.

:meth:`AudiencePreviewer.panel_sample` is the sample a panel run would draw (run-qc-and-checkpoint
RQC6b): ``draw_panel_sample`` over the same population, at the filters, ``n`` and seed the caller
names. Readiness is read often (Kontrola, Vzorek, the Lead), and a draw over LIVE's 18,766 rows
takes 41-127 ms at n 300-3,000, so the last :data:`SAMPLE_CACHE` draws are kept, keyed by the
version and everything the draw depends on; a new version is a new key.
"""

from __future__ import annotations

import json
import threading
from collections import OrderedDict
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any, Final

from sqlalchemy.orm import Session

from ..domain.population import (
    PopulationImportContract,
    PopulationSelector,
    PopulationView,
    RuntimePopulation,
)
from ..domain.population.audience_preview import audience_preview
from ..domain.population.errors import PopulationError
from ..domain.population.sampling import PanelSample, draw_panel_sample
from ..infrastructure.population_repository import PopulationRegistryRepository
from ..infrastructure.population_source import PopulationAssetSource
from .population import Enricher, PopulationRuntime

__all__ = [
    "POPULATION_UNAVAILABLE",
    "SAMPLE_CACHE",
    "AudiencePreviewer",
    "PanelDraw",
    "PanelSampler",
]

#: How many panel draws a previewer keeps.
SAMPLE_CACHE: Final = 32

#: A draw's ``refused`` when the population could not be loaded: unknown, not the design's.
POPULATION_UNAVAILABLE: Final = "population_unavailable"


@dataclass(frozen=True, slots=True)
class PanelDraw:
    """A panel run's sample as a start would draw it, or the sampler's refusal by name."""

    sample: PanelSample | None
    #: The refusal's reason (the sampler's, the audience filter's, or
    #: ``population_unavailable`` when the population could not be loaded); ``None`` with a sample.
    refused: str | None = None
    #: The version and seed the draw was asked on; ``None`` when no population was loaded.
    version_id: str | None = None
    seed: int | None = None
    #: What the refusal names (the audience filter's dropped or refused filters); empty when it
    #: names nothing.
    reasons: tuple[str, ...] = ()

    @property
    def sampler_refused(self) -> str | None:
        """The sampler's (or the audience filter's) refusal of this design; ``None`` when it
        drew, or when the population could not be loaded, which says nothing of the design."""
        return None if self.refused == POPULATION_UNAVAILABLE else self.refused


#: Draws a panel run's sample at (filters, n, seed) over the population a new run records; the
#: API binds :meth:`AudiencePreviewer.panel_sample` to its request's session.
PanelSampler = Callable[[Mapping[str, Any] | None, int, int], PanelDraw | None]


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
        self._draws: OrderedDict[tuple[str, str, int, int], PanelDraw] = OrderedDict()

    @property
    def population_id(self) -> str:
        """The population this previewer counts in."""
        return self._population_id

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

    def panel_sample(
        self, session: Session, filters: Mapping[str, Any] | None, n: int, seed: int
    ) -> PanelDraw | None:
        """The sample ``draw_panel_sample`` gives at ``filters``, ``n`` and ``seed`` over the
        population as it stands now; ``None`` when the population is not established."""
        try:
            population = self._population(session)
        except PopulationError:  # a missing or corrupt asset: unknown, never a failed readiness
            return PanelDraw(None, refused=POPULATION_UNAVAILABLE, seed=seed)
        if population is None:
            return None
        version_id = population.binding.version_id
        key = (
            version_id,
            json.dumps(filters or {}, sort_keys=True, default=str),
            n,
            seed,
        )
        with self._lock:
            kept = self._draws.get(key)
            if kept is not None:
                self._draws.move_to_end(key)
                return kept
        try:
            draw = PanelDraw(
                draw_panel_sample(population, filters, n, seed), None, version_id, seed
            )
        except PopulationError as exc:  # the sampler's or the audience filter's refusal
            draw = PanelDraw(None, exc.reason, version_id, seed, tuple(getattr(exc, "reasons", ())))
        with self._lock:
            self._draws[key] = draw
            while len(self._draws) > SAMPLE_CACHE:
                self._draws.popitem(last=False)
        return draw
