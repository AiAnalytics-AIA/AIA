"""A population version keeps its field dictionary (population-operations P7a).

Its characteristics -- each field's block, evidence status and permitted uses -- are read
from its dictionary, which until P7a lived only beside the panel. An import now keeps the
bytes it verified; a version imported before gets them through ``record_dictionary``, which
stores them only when they hash to the version's own pin, and never reads the panel.
"""

from __future__ import annotations

from typing import Any

import pytest
from sqlalchemy import delete

from aia_core.application.population import PopulationRuntime
from aia_core.domain.population import (
    UnknownDatasetVersion,
    VersionIntegrityError,
    content_sha256,
)
from aia_core.infrastructure.population_repository import PopulationRegistryRepository
from aia_core.infrastructure.population_source import PopulationAssetMissing
from aia_core.infrastructure.tables import PopulationVersionDictionaryRow


class _CountingSource:
    """The fictional source, counting which locations were read."""

    def __init__(self, inner: Any) -> None:
        self.inner = inner
        self.reads: list[str] = []

    def read(self, location: str) -> bytes:
        self.reads.append(location)
        return bytes(self.inner.read(location))


def _import(session: Any, pop: Any, label: str = "v1_BASE") -> str:
    runtime = PopulationRuntime(session, contract=pop.contract, source=pop.source)
    return runtime.import_version(
        label=label,
        panel_location=pop.location(label),
        dictionary_location=pop.dictionary_location,
        provenance="fictional test bundle",
        imported_by="importer",
    ).version_id


def _forget(session: Any, version_id: str) -> None:
    """Make ``version_id`` look imported before dictionaries were kept."""
    session.execute(
        delete(PopulationVersionDictionaryRow).where(
            PopulationVersionDictionaryRow.version_id == version_id
        )
    )
    session.flush()


def test_an_import_keeps_the_dictionary_it_verified(
    session: Any, synthetic_population: Any
) -> None:
    pop = synthetic_population
    version_id = _import(session, pop)
    kept = PopulationRegistryRepository(session).dictionary(version_id)
    dictionary = bytes(pop.source.read(pop.dictionary_location))
    assert kept == (content_sha256(dictionary), dictionary)


def test_a_version_imported_before_keeps_its_own_dictionary_and_no_panel_is_read(
    session: Any, synthetic_population: Any
) -> None:
    pop = synthetic_population
    version_id = _import(session, pop)
    _forget(session, version_id)
    source = _CountingSource(pop.source)
    runtime = PopulationRuntime(session, contract=pop.contract, source=source)

    assert runtime.record_dictionary(version_id, recorded_by="test") is True
    assert source.reads == [pop.dictionary_location]
    sha, content = PopulationRegistryRepository(session).dictionary(version_id) or ("", b"")
    assert (
        sha == content_sha256(content) == content_sha256(pop.source.read(pop.dictionary_location))
    )

    assert runtime.record_dictionary(version_id, recorded_by="test") is False
    assert source.reads == [pop.dictionary_location]  # kept: nothing read again


def test_other_bytes_at_the_location_are_refused_and_nothing_is_kept(
    session: Any, synthetic_population: Any
) -> None:
    pop = synthetic_population
    version_id = _import(session, pop)
    _forget(session, version_id)
    pop.source.put(pop.dictionary_location, b"field,block\nvek,core\n")
    runtime = PopulationRuntime(session, contract=pop.contract, source=pop.source)

    with pytest.raises(VersionIntegrityError):
        runtime.record_dictionary(version_id, recorded_by="test")
    assert PopulationRegistryRepository(session).dictionary(version_id) is None


def test_a_missing_file_or_an_unknown_version_keeps_nothing(
    session: Any, synthetic_population: Any
) -> None:
    pop = synthetic_population
    version_id = _import(session, pop)
    _forget(session, version_id)
    runtime = PopulationRuntime(session, contract=pop.contract, source=_Empty())
    with pytest.raises(PopulationAssetMissing):
        runtime.record_dictionary(version_id, recorded_by="test")
    with pytest.raises(UnknownDatasetVersion):
        runtime.record_dictionary("cz_synthetic_population@sha256:0000", recorded_by="test")
    assert PopulationRegistryRepository(session).dictionary(version_id) is None


class _Empty:
    def read(self, location: str) -> bytes:
        raise PopulationAssetMissing(f"no population asset at {location!r}")
