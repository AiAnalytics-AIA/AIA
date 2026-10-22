"""A fictional population in the worker's test database, for runs whose respondents come from it.

The population is the population double (``aia_core.application.population_double``, plan
run-qc-and-checkpoint RQC10) under this suite's own names: the sampler's fictional fixture
(3,000 rows aged 18 or more on 400 donors, every quota field and the profile's basic columns)
with the persona companions (the fictional signal catalog and the unit's value labels),
imported and established LIVE through ``PopulationRuntime`` exactly as an operator would. One
builder serves these tests, the API's composition and the worker's, so the panel path the
tests prove is the one tier A drives over HTTP. :func:`grounded_population` returns it; its
``loader()`` is what the worker's panel path takes -- the production loader reads the v17
contract, which fictional rows cannot meet.
"""

from __future__ import annotations

from typing import Final

from aia_core.application.population_double import (
    WEIGHT,
    PopulationDouble,
    PopulationDoubleNames,
    population_double,
)
from aia_core.domain.deployment import DeploymentEnvironment
from sqlalchemy.orm import Session

__all__ = ["LIVE", "WEIGHT", "GroundedPopulation", "grounded_population"]

LIVE: Final = "GROUNDED_LIVE"
_NAMES: Final = PopulationDoubleNames(
    contract_id="grounded_population/v1",
    dataset_id="grounded_population",
    live=LIVE,
    static="GROUNDED_STATIC",
    imported_by="importer",
)

#: The population as established, and how a run reaches it.
GroundedPopulation = PopulationDouble


def grounded_population(session: Session, *, omit: tuple[str, ...] = ()) -> GroundedPopulation:
    """Import the fictional rows as v1_BASE, v1_1 (STATIC) and v1_4 (LIVE), and commit."""
    world = population_double(DeploymentEnvironment.TEST, names=_NAMES, omit=omit)
    world.establish(session)
    session.commit()
    return world
