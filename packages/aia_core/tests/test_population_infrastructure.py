"""Population infrastructure: the parser, the asset sources, the registry, run bindings.

Adapters are tested against real bytes -- gzip CSV built in the test -- asserting
every field of what comes back (``ARCHITECTURE.md`` §7). Repositories are tested
round-trip against the session fixture, which is PostgreSQL when ``DATABASE_URL``
is set and SQLite otherwise.
"""

from __future__ import annotations

import gzip
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from aia_core.domain.population import (
    DatasetVersion,
    ImportRejected,
    PopulationBinding,
    PopulationBindingConflict,
    PopulationBindingMissing,
    PopulationBindingRequired,
    PopulationKind,
    PopulationView,
    PromotionConflict,
    ResolutionMode,
    content_sha256,
    dataset_version_id,
    plan_establish,
    plan_promotion,
)
from aia_core.domain.workflow import StepDefinition
from aia_core.infrastructure.population_parser import parse_dictionary, parse_panel
from aia_core.infrastructure.population_repository import PopulationRegistryRepository
from aia_core.infrastructure.population_source import (
    FilesystemPopulationSource,
    InMemoryPopulationSource,
    PopulationAssetMissing,
    PopulationAssetSource,
)
from aia_core.infrastructure.repositories import ProjectRepository
from aia_core.infrastructure.tables import (
    PopulationRow,
    RunPopulationBindingRow,
    WorkflowRunRow,
)
from aia_core.infrastructure.workflow_repository import WorkflowNotFound, WorkflowRepository

AT = datetime(2026, 9, 22, 12, 0, tzinfo=UTC)

# --------------------------------------------------------------------------- #
# Parser -- three real fixtures, every field asserted
# --------------------------------------------------------------------------- #


def gz(text: str) -> bytes:
    return gzip.compress(text.encode("utf-8"), mtime=0)


def test_parser_fixture_1_preserves_text_exactly() -> None:
    panel = parse_panel(gz("id,isco,weight,note\n1,0110,1.5,NA\n2,0310,0.5,\n"))
    assert panel.header == ("id", "isco", "weight", "note")
    assert panel.row_count == 2
    assert panel.column("id") == ("1", "2")
    # Leading zeros are kept: nothing is ever numerically inferred.
    assert panel.column("isco") == ("0110", "0310")
    assert panel.column("weight") == ("1.5", "0.5")
    # "NA" is text, not null. Only an empty cell is null.
    assert panel.column("note") == ("NA", None)


def test_parser_fixture_2_quoting_utf8_bom_and_crlf() -> None:
    text = '﻿id,city,quote\r\n1,"Praha, střed","he said ""ano"""\r\n2,Brno,  spaced  \r\n'
    panel = parse_panel(gz(text))
    # The BOM does not glue itself onto the first header name.
    assert panel.header == ("id", "city", "quote")
    assert panel.row_count == 2
    assert panel.column("id") == ("1", "2")
    assert panel.column("city") == ("Praha, střed", "Brno")
    # Whitespace is data; nothing is stripped.
    assert panel.column("quote") == ('he said "ano"', "  spaced  ")


def test_parser_fixture_3_header_only_and_duplicates_survive() -> None:
    panel = parse_panel(gz("a,b,a\n"))
    assert panel.header == ("a", "b", "a")
    assert panel.row_count == 0
    assert panel.columns == ((), (), ())

    duplicated = parse_panel(gz("a,b,a\n1,2,3\n"))
    # Both copies survive, by position, so validation can report the duplicate.
    assert duplicated.columns == (("1",), ("2",), ("3",))


def test_parser_interns_equal_values() -> None:
    panel = parse_panel(gz("code\n" + "0110\n" * 3))
    first, second, third = panel.column("code")
    assert first is second is third


@pytest.mark.parametrize(
    ("data", "failure"),
    [
        (b"id,x\n1,2\n", "panel.format"),  # not gzip
        (b"\x1f\x8bnot really gzip", "panel.format"),
        (gz(""), "panel.header"),
        (gz("id,x\n1,2,3\n"), "panel.ragged_row"),
        (gz("id,x\n1\n"), "panel.ragged_row"),
        (gzip.compress(b"id,x\n1,\xff\n", mtime=0), "panel.encoding"),
        (gz('id,x\n1,"unterminated\n'), "panel.csv"),
    ],
)
def test_parser_refuses_malformed_panels(data: bytes, failure: str) -> None:
    with pytest.raises(ImportRejected) as caught:
        parse_panel(data)
    assert caught.value.failures == (failure,)


def test_dictionary_parser_returns_ordered_fields() -> None:
    parsed = parse_dictionary(b'field,block,description\nid,core,x\nvek,core,"age, years"\n')
    assert parsed.fields == ("id", "vek")


def test_dictionary_parser_honours_the_field_column() -> None:
    parsed = parse_dictionary(b"name,field\nx,id\ny,vek\n", field_column="field")
    assert parsed.fields == ("id", "vek")


@pytest.mark.parametrize(
    ("data", "failure"),
    [
        (b"name,block\nid,core\n", "dictionary.header"),
        (b"", "dictionary.header"),
        (b"field,block\nid,core\n,core\n", "dictionary.empty_field"),
        (b"field\n\xff\n", "dictionary.encoding"),
    ],
)
def test_dictionary_parser_refuses_malformed_input(data: bytes, failure: str) -> None:
    with pytest.raises(ImportRejected) as caught:
        parse_dictionary(data)
    assert caught.value.failures == (failure,)


# --------------------------------------------------------------------------- #
# Asset sources
# --------------------------------------------------------------------------- #


def test_in_memory_source_round_trip_and_missing() -> None:
    source = InMemoryPopulationSource({"a": b"1"})
    assert isinstance(source, PopulationAssetSource)
    assert source.read("a") == b"1"
    source.put("a", b"2")
    assert source.read("a") == b"2"
    with pytest.raises(PopulationAssetMissing):
        source.read("b")


def test_filesystem_source_reads_under_its_root_only(tmp_path: Path) -> None:
    (tmp_path / "panels").mkdir()
    (tmp_path / "panels" / "v.csv.gz").write_bytes(b"bytes")
    (tmp_path.parent / "outside.txt").write_bytes(b"secret")
    source = FilesystemPopulationSource(tmp_path)
    assert isinstance(source, PopulationAssetSource)
    assert source.read("panels/v.csv.gz") == b"bytes"
    with pytest.raises(PopulationAssetMissing, match="outside"):
        source.read("../outside.txt")
    with pytest.raises(PopulationAssetMissing):
        source.read("panels/absent.csv.gz")
    with pytest.raises(PopulationAssetMissing):
        source.read("panels")


# --------------------------------------------------------------------------- #
# Registry repository
# --------------------------------------------------------------------------- #


def make_version(label: str, parent: DatasetVersion | None = None) -> DatasetVersion:
    sha = content_sha256(label.encode())
    return DatasetVersion(
        version_id=dataset_version_id("synthetic_population", sha),
        dataset_id="synthetic_population",
        label=label,
        content_sha256=sha,
        byte_size=10,
        row_count=6,
        column_count=6,
        contract_id="synthetic_population/v1",
        dictionary_sha256=content_sha256(b"d"),
        field_names_sha256=content_sha256(b"n"),
        parent_version_id=parent.version_id if parent else None,
        storage_location=f"panels/{label}.csv.gz",
        dictionary_location="dictionary.csv",
        provenance="synthetic",
        imported_at=AT,
        imported_by="importer",
    )


@pytest.fixture
def registry(session: Session) -> PopulationRegistryRepository:
    return PopulationRegistryRepository(session)


@pytest.fixture
def lineage(registry: PopulationRegistryRepository) -> dict[str, DatasetVersion]:
    base = make_version("v1_BASE")
    static = make_version("v1_1", base)
    live = make_version("v1_4", static)
    for v in (base, static, live):
        registry.insert_version(v, validation={"passed": True, "label": v.label})
    return {"base": base, "static": static, "live": live}


def establish_both(
    registry: PopulationRegistryRepository, lineage: dict[str, DatasetVersion]
) -> None:
    versions = registry.versions("synthetic_population")
    for pid, kind, version in (
        ("SYN_STATIC", PopulationKind.STATIC, lineage["static"]),
        ("SYN_LIVE", PopulationKind.LIVE, lineage["live"]),
    ):
        population, record = plan_establish(
            population_id=pid,
            kind=kind,
            version=version,
            versions=versions,
            populations=registry.populations("synthetic_population"),
            static_label="v1_1",
            actor_id="owner",
            reason="establish",
            at=AT,
        )
        registry.insert_population(population, record)


def test_version_round_trip(
    registry: PopulationRegistryRepository, lineage: dict[str, DatasetVersion]
) -> None:
    live = lineage["live"]
    assert registry.get_version(live.version_id) == live
    assert registry.version_by_sha(live.content_sha256) == live
    assert registry.version_by_label("synthetic_population", "v1_4") == live
    assert set(registry.versions("synthetic_population")) == {
        v.version_id for v in lineage.values()
    }
    assert registry.validation_record(live.version_id) == {"passed": True, "label": "v1_4"}
    assert registry.get_version("synthetic_population@sha256:0000000000000000") is None
    assert registry.versions("other_dataset") == {}


def test_the_same_bytes_cannot_be_registered_twice(
    session: Session, registry: PopulationRegistryRepository, lineage: dict[str, DatasetVersion]
) -> None:
    # Same content hash under another label: the unique key refuses it.
    duplicate = replace(lineage["live"], label="v1_4_copy")
    with pytest.raises(IntegrityError):
        registry.insert_version(duplicate, validation={})
    session.rollback()


def test_a_label_cannot_name_two_byte_sequences(
    session: Session, registry: PopulationRegistryRepository, lineage: dict[str, DatasetVersion]
) -> None:
    other = make_version("different bytes")
    relabelled = replace(other, label="v1_4")
    with pytest.raises(IntegrityError):
        registry.insert_version(relabelled, validation={})
    session.rollback()


def test_the_registry_has_no_update_path_for_versions() -> None:
    public = {n for n in dir(PopulationRegistryRepository) if not n.startswith("_")}
    assert not {n for n in public if "update" in n or "delete" in n or "set_" in n}


def test_populations_and_history_round_trip(
    registry: PopulationRegistryRepository, lineage: dict[str, DatasetVersion]
) -> None:
    establish_both(registry, lineage)
    populations = {p.population_id: p for p in registry.populations("synthetic_population")}
    assert populations["SYN_STATIC"].kind is PopulationKind.STATIC
    assert populations["SYN_STATIC"].current_version_id == lineage["static"].version_id
    assert populations["SYN_LIVE"].current_version_id == lineage["live"].version_id
    history = registry.promotions("synthetic_population")
    # Both entries share the fixed test clock, so compare without order.
    assert {(r.population_id, r.from_version_id) for r in history} == {
        ("SYN_STATIC", None),
        ("SYN_LIVE", None),
    }
    assert registry.population("SYN_LIVE", for_update=True) == populations["SYN_LIVE"]
    assert registry.population("absent") is None


def test_promotion_is_compare_and_set_in_the_database(
    session: Session, registry: PopulationRegistryRepository, lineage: dict[str, DatasetVersion]
) -> None:
    establish_both(registry, lineage)
    newer = make_version("v1_5", lineage["live"])
    registry.insert_version(newer, validation={})
    live = registry.population("SYN_LIVE")
    assert live is not None
    promoted, record = plan_promotion(
        population=live,
        target_version_id=newer.version_id,
        expected_current_version_id=live.current_version_id,
        versions=registry.versions("synthetic_population"),
        populations=registry.populations("synthetic_population"),
        actor_id="owner",
        reason="approved",
        at=AT,
    )
    registry.apply_promotion(promoted, record)
    current = registry.population("SYN_LIVE")
    assert current is not None
    assert current.current_version_id == newer.version_id

    # Replaying the same plan -- as a second, concurrent promoter would -- finds the
    # pointer already moved and changes nothing.
    with pytest.raises(PromotionConflict):
        registry.apply_promotion(promoted, replace(record, promotion_id="PRM-replay"))
    assert len(registry.promotions("synthetic_population")) == 3


def test_the_database_never_moves_a_static_pointer(
    session: Session, registry: PopulationRegistryRepository, lineage: dict[str, DatasetVersion]
) -> None:
    establish_both(registry, lineage)
    static = registry.population("SYN_STATIC")
    assert static is not None
    # Bypass the domain rule entirely and ask the repository to move STATIC.
    forged = replace(static, current_version_id=lineage["live"].version_id)
    record = plan_establish(
        population_id="unused",
        kind=PopulationKind.STATIC,
        version=lineage["static"],
        versions=registry.versions("synthetic_population"),
        populations=[],
        static_label="v1_1",
        actor_id="owner",
        reason="x",
        at=AT,
    )[1]
    record = replace(
        record,
        population_id="SYN_STATIC",
        from_version_id=static.current_version_id,
        to_version_id=lineage["live"].version_id,
    )
    with pytest.raises(PromotionConflict):
        registry.apply_promotion(forged, record)
    row = session.scalar(select(PopulationRow).where(PopulationRow.population_id == "SYN_STATIC"))
    assert row is not None
    assert row.current_version_id == lineage["static"].version_id


def test_one_population_per_kind_per_dataset_in_the_database(
    session: Session, registry: PopulationRegistryRepository, lineage: dict[str, DatasetVersion]
) -> None:
    establish_both(registry, lineage)
    second, record = plan_establish(
        population_id="SYN_STATIC_2",
        kind=PopulationKind.STATIC,
        version=lineage["static"],
        versions=registry.versions("synthetic_population"),
        populations=[],  # lie to the domain rule; the database still refuses
        static_label="v1_1",
        actor_id="owner",
        reason="x",
        at=AT,
    )
    with pytest.raises(IntegrityError):
        registry.insert_population(second, record)
    session.rollback()


# --------------------------------------------------------------------------- #
# Run bindings
# --------------------------------------------------------------------------- #

CONSUMING = [
    StepDefinition(node_key="sample", kind="respondent_sampling", consumes_population=True),
    StepDefinition(node_key="report", kind="final_report", depends_on=("sample",)),
]
NON_CONSUMING = [StepDefinition(node_key="compile", kind="project_compile")]


@pytest.fixture
def project(session: Session, scoped: Any) -> Any:
    repo = ProjectRepository(session, scoped.scope(user="lead", study="primary"))
    created, _ = repo.create(title="Population host", content={"goal": "g"})
    return created


@pytest.fixture
def workflow(session: Session, scoped: Any) -> WorkflowRepository:
    return WorkflowRepository(session, scoped.scope(user="lead", study="primary"))


def binding_for(version: DatasetVersion, **changes: Any) -> PopulationBinding:
    binding = PopulationBinding(
        dataset_id=version.dataset_id,
        version_id=version.version_id,
        version_label=version.label,
        content_sha256=version.content_sha256,
        contract_id=version.contract_id,
        population_id="SYN_LIVE",
        resolution=ResolutionMode.LIVE_CURRENT,
        weight_role="main",
        weight_column="w_main",
        view=PopulationView.ANALYSIS,
        resolved_at=AT,
    )
    return replace(binding, **changes)


def create(workflow: WorkflowRepository, project: Any, steps: Any, **kwargs: Any) -> str:
    return workflow.create_run(
        project_id=project.project_id,
        project_revision=1,
        workflow_type="persistent_research_project",
        steps=steps,
        idempotency_key=kwargs.pop("key", "k1"),
        **kwargs,
    )


def test_a_population_consuming_run_requires_a_binding(
    workflow: WorkflowRepository, project: Any
) -> None:
    with pytest.raises(PopulationBindingRequired, match="sample"):
        create(workflow, project, CONSUMING)


def test_a_run_that_reads_no_population_needs_no_binding(
    workflow: WorkflowRepository, project: Any
) -> None:
    run_id = create(workflow, project, NON_CONSUMING)
    assert workflow.get_run(run_id)["population"] is None
    with pytest.raises(PopulationBindingMissing):
        workflow.population_binding(run_id)


def test_the_binding_is_recorded_with_the_run(
    workflow: WorkflowRepository, project: Any, lineage: dict[str, DatasetVersion]
) -> None:
    binding = binding_for(lineage["live"])
    run_id = create(workflow, project, CONSUMING, population=binding)
    assert workflow.population_binding(run_id) == binding
    recorded = workflow.get_run(run_id)["population"]
    assert recorded == binding.as_record()
    created_event = workflow.events(run_id)[0]
    assert created_event["payload"]["population"]["version_label"] == "v1_4"


def test_an_idempotent_resubmission_with_the_same_binding_returns_the_run(
    workflow: WorkflowRepository, project: Any, lineage: dict[str, DatasetVersion]
) -> None:
    first = create(workflow, project, CONSUMING, population=binding_for(lineage["live"]))
    # Re-resolved later: a different resolved_at is the same population.
    again = create(
        workflow,
        project,
        CONSUMING,
        population=binding_for(lineage["live"], resolved_at=datetime(2026, 9, 23, tzinfo=UTC)),
    )
    assert again == first


@pytest.mark.parametrize("change", ["version", "weight", "view", "none"])
def test_a_resubmission_that_resolves_differently_is_refused(
    workflow: WorkflowRepository,
    project: Any,
    lineage: dict[str, DatasetVersion],
    change: str,
) -> None:
    create(workflow, project, CONSUMING, population=binding_for(lineage["live"]))
    requested: PopulationBinding | None = {
        "version": binding_for(
            lineage["static"],
            population_id="SYN_STATIC",
            resolution=ResolutionMode.STATIC_REFERENCE,
        ),
        "weight": binding_for(lineage["live"], weight_role="alt", weight_column="w_alt"),
        "view": binding_for(lineage["live"], view=PopulationView.BASE),
        "none": None,
    }[change]
    with pytest.raises(PopulationBindingConflict):
        create(workflow, project, CONSUMING, population=requested)


def test_a_binding_must_name_a_registered_version(
    session: Session, workflow: WorkflowRepository, project: Any
) -> None:
    with pytest.raises(IntegrityError):
        create(workflow, project, CONSUMING, population=binding_for(make_version("ghost")))
    session.rollback()


def test_another_study_cannot_read_a_runs_binding(
    session: Session,
    scoped: Any,
    workflow: WorkflowRepository,
    project: Any,
    lineage: dict[str, DatasetVersion],
) -> None:
    run_id = create(workflow, project, CONSUMING, population=binding_for(lineage["live"]))
    other = WorkflowRepository(session, scoped.scope(user="lead", study="sibling"))
    with pytest.raises(WorkflowNotFound):
        other.population_binding(run_id)


def test_the_binding_row_cascades_with_its_run(
    session: Session,
    workflow: WorkflowRepository,
    project: Any,
    lineage: dict[str, DatasetVersion],
) -> None:
    run_id = create(workflow, project, CONSUMING, population=binding_for(lineage["live"]))
    assert session.get(RunPopulationBindingRow, run_id) is not None
    session.execute(delete(WorkflowRunRow).where(WorkflowRunRow.run_id == run_id))
    session.expire_all()
    assert session.get(RunPopulationBindingRow, run_id) is None
    # The version outlives the run; only the binding went with it.
    assert PopulationRegistryRepository(session).get_version(lineage["live"].version_id)
