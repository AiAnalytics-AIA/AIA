"""The population double (plan run-qc-and-checkpoint RQC10): fictional, local and test only.

Both processes build it independently, so its bytes must be deterministic; it is established
through the canonical loader, idempotently; and it refuses every environment but local and test
before reading anything.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from aia_core.application.population import live_binding
from aia_core.application.population_double import (
    DOUBLE_NAMES,
    PopulationDoubleRefused,
    population_double,
    population_double_problem,
)
from aia_core.domain.deployment import DeploymentEnvironment
from aia_core.domain.population.audience_catalogue import AUDIENCE_CATALOGUE_VERSION
from aia_core.infrastructure.population_repository import PopulationRegistryRepository
from aia_core.infrastructure.tables import Base


@pytest.fixture
def session() -> Iterator[Session]:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with sessionmaker(bind=engine)() as s:
        yield s
    engine.dispose()


@pytest.mark.parametrize(
    "environment",
    [
        DeploymentEnvironment.DEVELOP,
        DeploymentEnvironment.STAGING,
        DeploymentEnvironment.PRODUCTION,
        None,  # unset or unknown AIA_ENV
    ],
)
def test_the_double_refuses_every_environment_but_local_and_test(
    environment: DeploymentEnvironment | None,
) -> None:
    assert population_double_problem(environment) is not None
    with pytest.raises(PopulationDoubleRefused, match="local and test"):
        population_double(environment)


@pytest.mark.parametrize("environment", [DeploymentEnvironment.LOCAL, DeploymentEnvironment.TEST])
def test_local_and_test_compose_it(environment: DeploymentEnvironment) -> None:
    assert population_double_problem(environment) is None
    assert population_double(environment).population_id == DOUBLE_NAMES.live


def test_two_processes_build_the_same_contract_and_bytes() -> None:
    """The API and the worker each build it; a run the API records must load in the worker."""
    first = population_double(DeploymentEnvironment.TEST)
    second = population_double(DeploymentEnvironment.TEST)
    assert first.contract == second.contract
    assert first.rows == second.rows == 3000
    for label in ("v1_BASE", "v1_1", "v1_4"):
        location = f"panels/{label}.csv.gz"
        assert first.source.read(location) == second.source.read(location)
    assert set(first.companions) == {
        "CORE_JOINT_STATUS.json",
        "PERSONA_SIGNAL_CATALOG_v17.csv",
        "PERSONA_VALUE_LABELS_v17.json",
    }


def test_it_is_established_once_and_loads_through_the_canonical_loader(session: Session) -> None:
    double = population_double(DeploymentEnvironment.TEST)
    live = double.establish(session)
    session.commit()
    # Idempotent: a restarted API finds what it established and imports nothing again.
    assert double.establish(session) == live
    registry = PopulationRegistryRepository(session)
    assert registry.population(DOUBLE_NAMES.live).current_version_id == live  # type: ignore[union-attr]
    assert registry.population(DOUBLE_NAMES.static) is not None
    assert len(registry.versions(DOUBLE_NAMES.dataset_id)) == 3
    # LIVE's audience catalogue is kept, so the audience step can read it.
    assert registry.audience_catalogue(live, AUDIENCE_CATALOGUE_VERSION) is not None

    binding = live_binding(session, contract=double.contract, population_id=double.population_id)
    assert binding is not None and binding.version_id == live
    # Another process's double loads what this one recorded: the bytes are the same.
    loaded = population_double(DeploymentEnvironment.TEST).runtime(session).load(binding)
    assert loaded.binding.version_id == live


def test_a_test_may_leave_a_companion_out() -> None:
    double = population_double(DeploymentEnvironment.TEST, omit=("PERSONA_VALUE_LABELS_v17.json",))
    assert "PERSONA_VALUE_LABELS_v17.json" not in double.companions
    assert all(c.asset_id != "PERSONA_VALUE_LABELS_v17.json" for c in double.contract.companions)
