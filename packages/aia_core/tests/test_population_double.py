"""The population double (plan run-qc-and-checkpoint RQC10): fictional, local and test only.

Both processes build it independently, so its bytes must be deterministic; it is established
through the canonical loader, idempotently; and it refuses every environment but local and test
before reading anything.
"""

from __future__ import annotations

import threading
from collections.abc import Iterator
from pathlib import Path
from typing import Any
from unittest import mock

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
def memory() -> Iterator[Session]:
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


def test_it_is_established_once_and_loads_through_the_canonical_loader(
    memory: Session,
) -> None:
    session = memory
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


def _file_sessions(tmp_path: Path) -> sessionmaker[Session]:
    engine = create_engine(f"sqlite+pysqlite:///{tmp_path / 'double.db'}")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)


def test_two_concurrent_first_establishes_both_get_the_one_live(
    engine: Any, session: Session
) -> None:
    """The audience step reads its catalogue and its preview at once: on a fresh database two
    transactions both find nothing and both import. Neither fails; one LIVE results.

    PostgreSQL only (CI runs this suite against it, and locally with ``DATABASE_URL``): SQLite
    admits one writer, so two transactions that both read before writing deadlock there."""
    if engine.dialect.name == "sqlite":
        pytest.skip("SQLite admits one writer; the race is PostgreSQL's (DATABASE_URL)")
    sessions = sessionmaker(bind=engine)
    double = population_double(DeploymentEnvironment.TEST)
    barrier = threading.Barrier(2)
    real = PopulationRegistryRepository.population
    results: list[str] = []
    errors: list[BaseException] = []

    def first_read_waits(self: PopulationRegistryRepository, pid: str, **k: Any) -> Any:
        found = real(self, pid, **k)
        if pid == DOUBLE_NAMES.live and found is None:
            barrier.wait(timeout=10)  # both have read "nothing" before either writes
        return found

    def establish() -> None:
        try:
            with sessions() as own:
                results.append(double.establish(own))
                own.commit()
        except BaseException as exc:  # the test reports it
            errors.append(exc)

    with mock.patch.object(PopulationRegistryRepository, "population", first_read_waits):
        threads = [threading.Thread(target=establish) for _ in range(2)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=60)
    assert errors == []
    assert len(results) == 2 and results[0] == results[1]
    live = PopulationRegistryRepository(session).population(DOUBLE_NAMES.live)
    assert live is not None and live.current_version_id == results[0]


def test_an_establish_that_read_before_another_committed_reads_back_what_it_wrote(
    tmp_path: Path,
) -> None:
    sessions = _file_sessions(tmp_path)
    double = population_double(DeploymentEnvironment.TEST)
    with sessions() as first:
        live = double.establish(first)
        first.commit()
    real = PopulationRegistryRepository.population
    calls = {"n": 0}

    def stale_once(self: PopulationRegistryRepository, pid: str, **k: object) -> object:
        calls["n"] += 1
        return None if calls["n"] == 1 else real(self, pid, **k)  # type: ignore[arg-type]

    with (
        sessions() as late,
        mock.patch.object(PopulationRegistryRepository, "population", stale_once),
    ):
        assert double.establish(late) == live
        late.commit()
