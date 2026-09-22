"""``PopulationRuntime`` end to end: import, establish, promote, resolve, load.

Runs over the synthetic population in ``conftest.py`` -- real gzip CSV bytes, a
real dictionary, a contract pinning both -- through the same code the Czech
population will use. Nothing here needs the withheld archive.
"""

from __future__ import annotations

import gzip
from collections.abc import Mapping, Sequence
from typing import Any

import pytest
from sqlalchemy.orm import Session

from aia_core.application.population import Enricher, PopulationRuntime
from aia_core.domain.population import (
    EnrichmentFailed,
    FieldOrigin,
    ImportRejected,
    LineageError,
    ParsedPanel,
    PopulationError,
    PopulationKind,
    PopulationNotEstablished,
    PopulationSelector,
    PopulationView,
    PromotionConflict,
    ResolutionMode,
    StaticReferenceImmutable,
    UnknownDatasetVersion,
    VersionIntegrityError,
    VersionNotRuntimeEligible,
    VersionStatus,
    WeightResolutionError,
    content_sha256,
)
from aia_core.domain.workflow import StepDefinition
from aia_core.infrastructure.population_source import PopulationAssetMissing
from aia_core.infrastructure.repositories import ProjectRepository
from aia_core.infrastructure.workflow_repository import WorkflowRepository


class LifeStageEnricher:
    """A test enricher: deterministic text derived from source fields."""

    enricher_id = "test-enricher/v1"

    def derive(self, panel: ParsedPanel) -> Mapping[str, Sequence[str | None]]:
        ages = panel.column("vek")
        return {
            "life_stage_derived": tuple(
                None if a is None else ("senior" if int(a) >= 65 else "adult") for a in ages
            ),
            "dominant_media_derived": tuple("tv" for _ in ages),
        }


class BrokenEnricher:
    enricher_id = "broken"

    def __init__(self, result: Any = None, *, raises: bool = False) -> None:
        self._result = result
        self._raises = raises

    def derive(self, panel: ParsedPanel) -> Mapping[str, Sequence[str | None]]:
        if self._raises:
            raise RuntimeError("derivation exploded")
        return dict(self._result)


def runtime(session: Session, pop: Any, enricher: Enricher | None = None) -> PopulationRuntime:
    return PopulationRuntime(session, contract=pop.contract, source=pop.source, enricher=enricher)


def import_label(rt: PopulationRuntime, pop: Any, label: str, **kwargs: Any) -> Any:
    return rt.import_version(
        label=label,
        panel_location=kwargs.pop("panel_location", pop.location(label)),
        dictionary_location=pop.dictionary_location,
        provenance="synthetic test bundle",
        imported_by="importer",
        **kwargs,
    )


@pytest.fixture
def established(session: Session, synthetic_population: Any) -> dict[str, Any]:
    """All three versions imported; STATIC -> v1_1 and LIVE -> v1_4 established."""
    rt = runtime(session, synthetic_population, LifeStageEnricher())
    versions = {
        label: import_label(rt, synthetic_population, label)
        for label in ("v1_BASE", "v1_1", "v1_4")
    }
    rt.establish(
        population_id="SYN_STATIC",
        kind=PopulationKind.STATIC,
        version_id=versions["v1_1"].version_id,
        actor_id="owner",
        reason="establish the reproducibility anchor",
    )
    rt.establish(
        population_id="SYN_LIVE",
        kind=PopulationKind.LIVE,
        version_id=versions["v1_4"].version_id,
        actor_id="owner",
        reason="establish the default runtime",
    )
    return {"rt": rt, "versions": versions, "pop": synthetic_population}


# --------------------------------------------------------------------------- #
# Import
# --------------------------------------------------------------------------- #


def test_import_registers_a_content_addressed_version(
    session: Session, synthetic_population: Any
) -> None:
    rt = runtime(session, synthetic_population)
    base = import_label(rt, synthetic_population, "v1_BASE")
    sha = content_sha256(synthetic_population.panel_bytes("v1_BASE"))
    assert base.content_sha256 == sha
    assert base.version_id == f"synthetic_population@sha256:{sha[:16]}"
    assert base.parent_version_id is None
    assert (base.row_count, base.column_count) == (6, 6)
    assert base.contract_id == "synthetic_population/v1"


def test_import_records_its_full_validation_report(
    session: Session, synthetic_population: Any
) -> None:
    from aia_core.infrastructure.population_repository import PopulationRegistryRepository

    rt = runtime(session, synthetic_population)
    base = import_label(rt, synthetic_population, "v1_BASE")
    record = PopulationRegistryRepository(session).validation_record(base.version_id)
    assert record is not None
    assert record["passed"] is True
    assert record["companions_validated"] is False
    assert {c["check"] for c in record["checks"]} >= {
        "dictionary.checksum",
        "schema.columns_in_order",
        "rows.primary_key",
        "weights.main.total",
    }


def test_import_never_promotes(session: Session, synthetic_population: Any) -> None:
    rt = runtime(session, synthetic_population)
    for label in ("v1_BASE", "v1_1", "v1_4"):
        version = import_label(rt, synthetic_population, label)
        assert rt.version_status(version.version_id) is VersionStatus.REGISTERED
    with pytest.raises(PopulationNotEstablished):
        rt.resolve(PopulationSelector.population("SYN_LIVE"))


def test_import_is_idempotent_for_the_same_bytes_and_label(
    session: Session, synthetic_population: Any
) -> None:
    rt = runtime(session, synthetic_population)
    first = import_label(rt, synthetic_population, "v1_BASE")
    assert import_label(rt, synthetic_population, "v1_BASE") == first


def test_known_bytes_cannot_be_imported_under_another_label(
    session: Session, synthetic_population: Any
) -> None:
    rt = runtime(session, synthetic_population)
    import_label(rt, synthetic_population, "v1_BASE")
    with pytest.raises(ImportRejected) as caught:
        import_label(
            rt,
            synthetic_population,
            "v1_BASE_copy",
            panel_location=synthetic_population.location("v1_BASE"),
        )
    assert caught.value.failures == ("identity.distinct_labels",)


def test_a_preserved_label_is_bound_to_its_preserved_bytes(
    session: Session, synthetic_population: Any
) -> None:
    rt = runtime(session, synthetic_population)
    import_label(rt, synthetic_population, "v1_BASE")
    # v1_1's label with v1_4's bytes: the versions stay distinct.
    with pytest.raises(ImportRejected) as caught:
        import_label(
            rt,
            synthetic_population,
            "v1_1",
            panel_location=synthetic_population.location("v1_4"),
        )
    assert any("identity" in f for f in caught.value.failures)


def test_a_preserved_version_needs_its_contract_parent_first(
    session: Session, synthetic_population: Any
) -> None:
    rt = runtime(session, synthetic_population)
    with pytest.raises(LineageError, match="import that first"):
        import_label(rt, synthetic_population, "v1_1")


def test_a_preserved_versions_parent_comes_from_the_contract(
    session: Session, synthetic_population: Any
) -> None:
    rt = runtime(session, synthetic_population)
    base = import_label(rt, synthetic_population, "v1_BASE")
    static = import_label(rt, synthetic_population, "v1_1")
    assert static.parent_version_id == base.version_id
    # Naming a different parent for a preserved version is refused.
    with pytest.raises(LineageError, match="parent is v1_1"):
        import_label(rt, synthetic_population, "v1_4", parent_version_id=base.version_id)


def test_a_lineage_root_takes_no_parent(session: Session, synthetic_population: Any) -> None:
    rt = runtime(session, synthetic_population)
    with pytest.raises(LineageError, match="lineage root"):
        import_label(
            rt,
            synthetic_population,
            "v1_BASE",
            parent_version_id="synthetic_population@sha256:0000000000000000",
        )


def test_a_new_version_must_name_a_registered_parent(
    established: dict[str, Any],
) -> None:
    rt, pop = established["rt"], established["pop"]
    pop.source.put(
        "panels/v1_5.csv.gz", pop.rebuild("v1_4", lambda rows: rows[0].update(segment="calibrated"))
    )
    with pytest.raises(LineageError, match="must name the version"):
        import_label(rt, pop, "v1_5")
    with pytest.raises(LineageError, match="not a registered"):
        import_label(rt, pop, "v1_5", parent_version_id="synthetic_population@sha256:00")
    newer = import_label(
        rt, pop, "v1_5", parent_version_id=established["versions"]["v1_4"].version_id
    )
    assert newer.parent_version_id == established["versions"]["v1_4"].version_id


def test_a_label_is_never_re_pointed(established: dict[str, Any]) -> None:
    rt, pop = established["rt"], established["pop"]
    pop.source.put("other.csv.gz", pop.rebuild("v1_4", lambda rows: rows[1].update(segment="z")))
    with pytest.raises(ImportRejected) as caught:
        import_label(rt, pop, "v1_4", panel_location="other.csv.gz")
    assert caught.value.failures == ("identity.label_taken",)


def test_an_invalid_bundle_is_rejected_with_every_failure(
    session: Session, synthetic_population: Any
) -> None:
    pop = synthetic_population
    rt = runtime(session, pop)
    import_label(rt, pop, "v1_BASE")
    import_label(rt, pop, "v1_1")

    def damage(rows: list[dict[str, str]]) -> None:
        rows[0]["row_id"] = rows[1]["row_id"]  # duplicate key
        rows[2]["w_main"] = "lots"  # malformed weight

    pop.source.put("bad.csv.gz", pop.rebuild("v1_4", damage))
    parent = import_label(rt, pop, "v1_1")
    with pytest.raises(ImportRejected) as caught:
        import_label(
            rt, pop, "v1_9", panel_location="bad.csv.gz", parent_version_id=parent.version_id
        )
    failures = " ".join(caught.value.failures)
    assert "rows.primary_key" in failures
    assert "weights.main.parseable" in failures
    assert "weights.main.total" in failures


def test_a_malformed_file_is_rejected_before_anything_is_written(
    session: Session, synthetic_population: Any
) -> None:
    pop = synthetic_population
    rt = runtime(session, pop)
    pop.source.put(pop.location("v1_BASE"), b"not gzip at all")
    with pytest.raises(ImportRejected):
        import_label(rt, pop, "v1_BASE")


def test_a_missing_asset_is_refused_not_substituted(
    session: Session, synthetic_population: Any
) -> None:
    rt = runtime(session, synthetic_population)
    with pytest.raises(PopulationAssetMissing):
        import_label(rt, synthetic_population, "v1_BASE", panel_location="absent.csv.gz")


# --------------------------------------------------------------------------- #
# Establish and promote
# --------------------------------------------------------------------------- #


def test_the_three_preserved_versions_keep_distinct_roles(established: dict[str, Any]) -> None:
    rt, v = established["rt"], established["versions"]
    assert rt.version_status(v["v1_BASE"].version_id) is VersionStatus.REGISTERED
    assert rt.version_status(v["v1_1"].version_id) is VersionStatus.STATIC_REFERENCE
    assert rt.version_status(v["v1_4"].version_id) is VersionStatus.LIVE_CURRENT
    assert len({x.content_sha256 for x in v.values()}) == 3


def test_static_is_immutable_even_by_explicit_call(established: dict[str, Any]) -> None:
    rt, v = established["rt"], established["versions"]
    with pytest.raises(StaticReferenceImmutable):
        rt.promote_live(
            population_id="SYN_STATIC",
            target_version_id=v["v1_4"].version_id,
            expected_current_version_id=v["v1_1"].version_id,
            actor_id="owner",
            reason="try to move the anchor",
        )
    assert rt.version_status(v["v1_1"].version_id) is VersionStatus.STATIC_REFERENCE


def test_explicit_promotion_supersedes_the_previous_live(established: dict[str, Any]) -> None:
    rt, pop, v = established["rt"], established["pop"], established["versions"]
    pop.source.put("panels/v1_5.csv.gz", pop.rebuild("v1_4", lambda r: r[0].update(segment="c")))
    newer = import_label(rt, pop, "v1_5", parent_version_id=v["v1_4"].version_id)
    assert rt.version_status(newer.version_id) is VersionStatus.REGISTERED

    rt.promote_live(
        population_id="SYN_LIVE",
        target_version_id=newer.version_id,
        expected_current_version_id=v["v1_4"].version_id,
        actor_id="owner",
        reason="approved calibration overlay",
    )
    assert rt.version_status(newer.version_id) is VersionStatus.LIVE_CURRENT
    assert rt.version_status(v["v1_4"].version_id) is VersionStatus.SUPERSEDED
    assert rt.resolve(PopulationSelector.population("SYN_LIVE")).version_id == newer.version_id


def test_promotion_with_a_stale_expectation_is_refused(established: dict[str, Any]) -> None:
    rt, pop, v = established["rt"], established["pop"], established["versions"]
    pop.source.put("panels/v1_5.csv.gz", pop.rebuild("v1_4", lambda r: r[0].update(segment="c")))
    newer = import_label(rt, pop, "v1_5", parent_version_id=v["v1_4"].version_id)
    with pytest.raises(PromotionConflict):
        rt.promote_live(
            population_id="SYN_LIVE",
            target_version_id=newer.version_id,
            expected_current_version_id=v["v1_1"].version_id,
            actor_id="owner",
            reason="stale",
        )


def test_promoting_an_unknown_population_is_refused(established: dict[str, Any]) -> None:
    with pytest.raises(PopulationNotEstablished):
        established["rt"].promote_live(
            population_id="NOPE",
            target_version_id="x",
            expected_current_version_id="y",
            actor_id="owner",
            reason="r",
        )


def test_establishing_an_unknown_version_is_refused(
    session: Session, synthetic_population: Any
) -> None:
    with pytest.raises(UnknownDatasetVersion):
        runtime(session, synthetic_population).establish(
            population_id="SYN_STATIC",
            kind=PopulationKind.STATIC,
            version_id="synthetic_population@sha256:0000000000000000",
            actor_id="owner",
            reason="r",
        )


def test_version_status_of_an_unknown_version_is_refused(established: dict[str, Any]) -> None:
    with pytest.raises(UnknownDatasetVersion):
        established["rt"].version_status("synthetic_population@sha256:0000000000000000")


# --------------------------------------------------------------------------- #
# Resolve
# --------------------------------------------------------------------------- #


def test_resolution_records_version_weight_and_view(established: dict[str, Any]) -> None:
    rt, v = established["rt"], established["versions"]
    binding = rt.resolve(PopulationSelector.population("SYN_LIVE"))
    assert binding.version_id == v["v1_4"].version_id
    assert binding.content_sha256 == v["v1_4"].content_sha256
    assert binding.resolution is ResolutionMode.LIVE_CURRENT
    assert (binding.weight_role, binding.weight_column) == ("main", "w_main")
    assert binding.view is PopulationView.ANALYSIS


def test_the_lineage_root_cannot_back_a_run(established: dict[str, Any]) -> None:
    rt, v = established["rt"], established["versions"]
    with pytest.raises(VersionNotRuntimeEligible):
        rt.resolve(PopulationSelector.pinned(v["v1_BASE"].version_id))


# --------------------------------------------------------------------------- #
# Load -- one canonical loader, named views
# --------------------------------------------------------------------------- #


def test_the_base_view_is_exactly_the_source_fields(established: dict[str, Any]) -> None:
    rt, pop = established["rt"], established["pop"]
    binding = rt.resolve(PopulationSelector.population("SYN_LIVE"), view=PopulationView.BASE)
    population = rt.load(binding)
    assert population.fields == pop.fields
    assert population.derived_fields == ()
    assert population.row_count == 6
    assert population.binding == binding
    with pytest.raises(PopulationError, match="no analysis weight"):
        _ = population.analysis_weight


def test_the_analysis_view_adds_exactly_the_declared_derived_fields(
    established: dict[str, Any],
) -> None:
    rt, pop = established["rt"], established["pop"]
    population = rt.load(rt.resolve(PopulationSelector.population("SYN_LIVE")))
    extra = [f for f in population.fields if f not in pop.fields]
    assert extra == ["life_stage_derived", "dominant_media_derived", "_analysis_weight"]
    assert population.origin("vek") is FieldOrigin.SOURCE
    assert population.origin("life_stage_derived") is FieldOrigin.ENRICHMENT
    assert population.origin("_analysis_weight") is FieldOrigin.ANALYSIS_WEIGHT
    assert all(not d.client_claims_allowed for d in population.derived_fields)
    assert population.column("life_stage_derived") == (
        "adult",
        "senior",
        None,
        "adult",
        "adult",
        "senior",
    )


def test_the_analysis_weight_is_the_resolved_column_exactly(established: dict[str, Any]) -> None:
    rt = established["rt"]
    population = rt.load(rt.resolve(PopulationSelector.population("SYN_LIVE")))
    assert population.analysis_weight == (1.5, 0.5, 2.0, 1.0, 3.25, 0.75)
    alt = rt.load(rt.resolve(PopulationSelector.population("SYN_LIVE"), weight_role="alt"))
    assert alt.analysis_weight == (2.0, 1.0, 1.0, 3.0, 1.0, 2.0)
    assert alt.binding.weight_column == "w_alt"


def test_loaded_text_is_lossless(established: dict[str, Any]) -> None:
    rt = established["rt"]
    population = rt.load(rt.resolve(PopulationSelector.population("SYN_LIVE")))
    assert population.column("occupation_code") == ("0110", "0310", "2512", "0010", "9629", "0000")
    assert population.column("segment") == ("a4", "b4", "Praha, střed", "NA", None, "x")
    assert population.column("vek")[2] is None


def test_a_loaded_population_cannot_be_mutated_through_its_columns(
    established: dict[str, Any],
) -> None:
    rt = established["rt"]
    population = rt.load(rt.resolve(PopulationSelector.population("SYN_LIVE")))
    with pytest.raises(TypeError):
        population._columns["vek"] = ("0",) * 6  # type: ignore[index]
    with pytest.raises(AttributeError):
        population.row_count = 1  # type: ignore[misc]
    again = rt.load(rt.resolve(PopulationSelector.population("SYN_LIVE")))
    assert again.column("vek") == population.column("vek")


def test_unknown_fields_are_refused(established: dict[str, Any]) -> None:
    rt = established["rt"]
    population = rt.load(rt.resolve(PopulationSelector.population("SYN_LIVE")))
    with pytest.raises(PopulationError):
        population.column("not_a_field")
    with pytest.raises(PopulationError):
        population.origin("not_a_field")


def test_the_analysis_view_does_not_load_without_an_enricher(
    session: Session, established: dict[str, Any]
) -> None:
    pop = established["pop"]
    bare = runtime(session, pop, enricher=None)
    binding = bare.resolve(PopulationSelector.population("SYN_LIVE"))
    with pytest.raises(EnrichmentFailed, match="not loadable unenriched"):
        bare.load(binding)
    # The BASE view is explicit, not a silent fallback, and still loads.
    base = bare.resolve(PopulationSelector.population("SYN_LIVE"), view=PopulationView.BASE)
    assert bare.load(base).view is PopulationView.BASE


@pytest.mark.parametrize(
    "enricher",
    [
        BrokenEnricher(raises=True),
        BrokenEnricher({"life_stage_derived": ("a",) * 6}),  # one missing
        BrokenEnricher(
            {
                "life_stage_derived": ("a",) * 6,
                "dominant_media_derived": ("b",) * 6,
                "sneaky_extra": ("c",) * 6,
            }
        ),
        BrokenEnricher({"life_stage_derived": ("a",) * 5, "dominant_media_derived": ("b",) * 6}),
        BrokenEnricher({"life_stage_derived": (1,) * 6, "dominant_media_derived": ("b",) * 6}),
    ],
    ids=["raises", "missing-field", "extra-field", "short-column", "non-text"],
)
def test_a_failing_enricher_is_a_refusal_never_a_silent_skip(
    session: Session, established: dict[str, Any], enricher: Any
) -> None:
    rt = runtime(session, established["pop"], enricher)
    with pytest.raises(EnrichmentFailed):
        rt.load(rt.resolve(PopulationSelector.population("SYN_LIVE")))


def test_a_swapped_file_is_refused_by_hash(established: dict[str, Any]) -> None:
    rt, pop = established["rt"], established["pop"]
    binding = rt.resolve(PopulationSelector.population("SYN_LIVE"), view=PopulationView.BASE)
    pop.source.put(pop.location("v1_4"), pop.panel_bytes("v1_1"))
    with pytest.raises(VersionIntegrityError, match="swapped"):
        rt.load(binding)


def test_a_swapped_dictionary_is_refused_by_hash(established: dict[str, Any]) -> None:
    rt, pop = established["rt"], established["pop"]
    binding = rt.resolve(PopulationSelector.population("SYN_LIVE"), view=PopulationView.BASE)
    pop.source.put(pop.dictionary_location, b"field\nrow_id\n")
    with pytest.raises(VersionIntegrityError, match="dictionary"):
        rt.load(binding)


def test_a_binding_that_disagrees_with_the_registry_is_refused(
    established: dict[str, Any],
) -> None:
    from dataclasses import replace

    rt, v = established["rt"], established["versions"]
    binding = rt.resolve(PopulationSelector.population("SYN_LIVE"))
    with pytest.raises(VersionIntegrityError):
        rt.load(replace(binding, content_sha256=v["v1_1"].content_sha256))
    with pytest.raises(WeightResolutionError):
        rt.load(replace(binding, weight_column="w_alt"))  # role main, wrong column
    with pytest.raises(UnknownDatasetVersion):
        rt.load(replace(binding, version_id="synthetic_population@sha256:0000000000000000"))


def test_a_null_in_the_selected_weight_refuses_the_load(
    session: Session, synthetic_population: Any
) -> None:
    pop = synthetic_population
    rt = runtime(session, pop, LifeStageEnricher())
    base = import_label(rt, pop, "v1_BASE")
    static = import_label(rt, pop, "v1_1")

    # w_alt with a null that keeps its declared total: import passes, load refuses.
    def null_alt(rows: list[dict[str, str]]) -> None:
        rows[0]["w_alt"] = ""
        rows[3]["w_alt"] = "5"

    pop.source.put("panels/v1_6.csv.gz", pop.rebuild("v1_4", null_alt))
    candidate = rt.import_version(
        label="v1_6",
        panel_location="panels/v1_6.csv.gz",
        dictionary_location=pop.dictionary_location,
        provenance="x",
        imported_by="importer",
        parent_version_id=static.version_id,
    )
    assert base.version_id != candidate.version_id
    rt.establish(
        population_id="SYN_STATIC",
        kind=PopulationKind.STATIC,
        version_id=static.version_id,
        actor_id="owner",
        reason="r",
    )
    rt.establish(
        population_id="SYN_LIVE",
        kind=PopulationKind.LIVE,
        version_id=candidate.version_id,
        actor_id="owner",
        reason="r",
    )
    ok = rt.load(rt.resolve(PopulationSelector.population("SYN_LIVE")))
    assert len(ok.analysis_weight) == 6
    with pytest.raises(WeightResolutionError, match="1 null"):
        rt.load(rt.resolve(PopulationSelector.population("SYN_LIVE"), weight_role="alt"))


def test_repeat_loads_are_served_from_the_cache_under_the_new_binding(
    established: dict[str, Any],
) -> None:
    rt, pop = established["rt"], established["pop"]
    first = rt.load(rt.resolve(PopulationSelector.population("SYN_LIVE")))
    # Remove the bytes: a cache hit must not need them.
    pop.source.put(pop.location("v1_4"), b"")
    second_binding = rt.resolve(PopulationSelector.population("SYN_LIVE"))
    second = rt.load(second_binding)
    assert second.binding is second_binding
    assert second.column("row_id") is first.column("row_id")


def test_the_reference_gzip_mtime_does_not_change_identity(
    session: Session, synthetic_population: Any
) -> None:
    # Two gzip encodings of the same CSV are two byte sequences, hence two
    # versions. Identity is the bytes as delivered, as the reference's hashes are.
    pop = synthetic_population
    raw = gzip.decompress(pop.panel_bytes("v1_BASE"))
    assert content_sha256(gzip.compress(raw, mtime=1)) != content_sha256(pop.panel_bytes("v1_BASE"))


# --------------------------------------------------------------------------- #
# Runs load only the population they recorded
# --------------------------------------------------------------------------- #


def test_a_run_loads_exactly_its_recorded_population_after_a_promotion(
    session: Session, scoped: Any, established: dict[str, Any]
) -> None:
    rt, pop, v = established["rt"], established["pop"], established["versions"]
    project, _ = ProjectRepository(session, scoped.scope(user="lead", study="primary")).create(
        title="Run host", content={"goal": "g"}
    )
    workflow = WorkflowRepository(session, scoped.scope(user="lead", study="primary"))
    run_id = workflow.create_run(
        project_id=project.project_id,
        project_revision=1,
        workflow_type="persistent_research_project",
        steps=[StepDefinition(node_key="sample", kind="sampling", consumes_population=True)],
        idempotency_key="population-run",
        population=rt.resolve(PopulationSelector.population("SYN_LIVE")),
    )

    # LIVE moves on while the run is in flight.
    pop.source.put("panels/v1_5.csv.gz", pop.rebuild("v1_4", lambda r: r[0].update(segment="c")))
    newer = import_label(rt, pop, "v1_5", parent_version_id=v["v1_4"].version_id)
    rt.promote_live(
        population_id="SYN_LIVE",
        target_version_id=newer.version_id,
        expected_current_version_id=v["v1_4"].version_id,
        actor_id="owner",
        reason="approved",
    )

    loaded = rt.load_for_run(workflow, run_id)
    assert loaded.binding.version_id == v["v1_4"].version_id
    assert loaded.column("segment")[0] == "a4"


def test_a_run_with_no_binding_reads_no_population(
    session: Session, scoped: Any, established: dict[str, Any]
) -> None:
    from aia_core.domain.population import PopulationBindingMissing

    project, _ = ProjectRepository(session, scoped.scope(user="lead", study="primary")).create(
        title="Run host", content={"goal": "g"}
    )
    workflow = WorkflowRepository(session, scoped.scope(user="lead", study="primary"))
    run_id = workflow.create_run(
        project_id=project.project_id,
        project_revision=1,
        workflow_type="single",
        steps=[StepDefinition(node_key="compile", kind="project_compile")],
        idempotency_key="no-population-run",
    )
    with pytest.raises(PopulationBindingMissing):
        established["rt"].load_for_run(workflow, run_id)
