"""What a population version is made of, without a row (population-operations P7c).

Over the fictional population in ``conftest.py``: every field in dictionary order with its
dictionary facts and the policy's answer for each use, the runtime fields after them, the
blocks and weights; the subpanels checked against the version; nothing when the dictionary
is not kept, and a refusal when what is kept does not hash to the version's pin.
"""

from __future__ import annotations

from typing import Any

import pytest
from sqlalchemy import delete, update

from aia_core.application.population import PopulationRuntime
from aia_core.application.population_characteristics import version_characteristics
from aia_core.domain.population import UnknownDatasetVersion, VersionIntegrityError
from aia_core.domain.population.policy import FieldUse
from aia_core.domain.population.subpanels import BUILTIN_SUBPANELS
from aia_core.infrastructure.tables import PopulationVersionDictionaryRow


@pytest.fixture
def imported(session: Any, synthetic_population: Any) -> tuple[Any, str]:
    pop = synthetic_population
    runtime = PopulationRuntime(session, contract=pop.contract, source=pop.source)
    version = runtime.import_version(
        label="v1_BASE",
        panel_location=pop.location("v1_BASE"),
        dictionary_location=pop.dictionary_location,
        provenance="fictional test bundle",
        imported_by="importer",
    )
    return pop, version.version_id


def test_every_field_with_its_dictionary_facts_and_each_uses_answer(
    session: Any, imported: tuple[Any, str]
) -> None:
    pop, version_id = imported
    found = version_characteristics(session, contract=pop.contract, version_id=version_id)
    assert found.dictionary_kept and found.label == "v1_BASE"
    names = [f.field for f in found.fields]
    assert names[: len(pop.fields)] == list(pop.fields)  # dictionary order first
    assert set(names[len(pop.fields) :]) == {
        "life_stage_derived",
        "dominant_media_derived",
        pop.contract.analysis_weight_field,
    }
    by_name = {f.field: f for f in found.fields}
    vek = by_name["vek"]
    assert (vek.block, vek.evidence_status, vek.production_grade) == (
        "population_anchor",
        "POPULATION_ANCHOR",
        "A",
    )
    assert vek.description == "vek (synthetic)" and vek.persona_eligible and not vek.derived
    assert [u.use for u in vek.uses] == list(FieldUse)
    uses = {u.use: u for u in vek.uses}
    assert uses[FieldUse.AUDIENCE_FILTERING].allowed
    assert not uses[FieldUse.WEIGHTING].allowed
    row_id = {u.use: u for u in by_name["row_id"].uses}
    assert not row_id[FieldUse.AUDIENCE_FILTERING].allowed
    assert row_id[FieldUse.AUDIENCE_FILTERING].reason == "audit_only"
    assert by_name["w_main"].is_weight
    assert {u.use: u.allowed for u in by_name["w_main"].uses}[FieldUse.WEIGHTING]
    derived = by_name["life_stage_derived"]
    assert derived.derived and derived.description == ""
    assert not any(u.allowed for u in derived.uses)  # unclassified: refused for every use


def test_blocks_and_weights_come_with_it(session: Any, imported: tuple[Any, str]) -> None:
    pop, version_id = imported
    found = version_characteristics(session, contract=pop.contract, version_id=version_id)
    assert sum(n for _, n in found.blocks) == len(found.fields)
    assert dict(found.blocks)["weight"] == 2
    assert [(w.role, w.column, w.is_default) for w in found.weights] == [
        ("main", "w_main", True),
        ("alt", "w_alt", False),
    ]


def test_each_subpanel_is_checked_against_this_version(
    session: Any, imported: tuple[Any, str]
) -> None:
    pop, version_id = imported
    found = version_characteristics(session, contract=pop.contract, version_id=version_id)
    assert [s.subpanel.key for s in found.subpanels] == [s.key for s in BUILTIN_SUBPANELS]
    checks = {s.subpanel.key: (s.usable, s.reason) for s in found.subpanels}
    assert checks["young_18_29"] == (True, None)  # filters on vek, which this version lets filter
    assert checks["students"] == (False, "unknown_field")  # no is_student in this version


def test_without_a_kept_dictionary_nothing_is_said_usable(
    session: Any, imported: tuple[Any, str]
) -> None:
    pop, version_id = imported
    session.execute(delete(PopulationVersionDictionaryRow))
    session.flush()
    found = version_characteristics(session, contract=pop.contract, version_id=version_id)
    assert not found.dictionary_kept and found.fields == () and found.blocks == ()
    assert {(s.usable, s.reason) for s in found.subpanels} == {(None, None)}
    assert found.weights  # the contract's weights are known without the dictionary


def test_a_kept_dictionary_that_does_not_hash_to_the_pin_is_refused(
    session: Any, imported: tuple[Any, str]
) -> None:
    pop, version_id = imported
    session.execute(
        update(PopulationVersionDictionaryRow).values(content=b"field,block\nvek,core\n")
    )
    session.flush()
    with pytest.raises(VersionIntegrityError):
        version_characteristics(session, contract=pop.contract, version_id=version_id)


def test_an_unknown_version_is_refused(session: Any, synthetic_population: Any) -> None:
    with pytest.raises(UnknownDatasetVersion):
        version_characteristics(
            session, contract=synthetic_population.contract, version_id="nope@sha256:00"
        )
