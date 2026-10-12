"""The panel persona source (chunk 5b): sample, personas and plans from a run's population.

The population is the sampler's fictional fixture (``fixtures/representative_draw/rows.csv``:
3,000 rows aged 18 or more on 400 donors, every quota field and the profile's basic columns),
imported with the persona companions (the fictional signal catalog and the unit's value labels)
and loaded as the ANALYSIS view a run binds. What the sampler and the personas compute is tested
in their own suites against the unit; here, that they compose in the contract's order and that
each refusal surfaces by name before anything else is built.
"""

from __future__ import annotations

import csv
import io
import math
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy.orm import Session

from aia_core.domain.ai_respondent import PROMPT_SHA256, dataset_origin
from aia_core.domain.evidence import respondent_system_fingerprint
from aia_core.domain.fieldwork import DataOrigin
from aia_core.domain.panel_persona import PersonaRefused
from aia_core.domain.panel_source import PANEL_SOURCE, panel_plans, respondent_system
from aia_core.domain.population.sampling import SAMPLER_VERSION, SamplingRefused
from aia_core.domain.research_design import ResearchSpecification, compile_design

TESTS = Path(__file__).parent
ROWS_CSV = TESTS / "fixtures" / "representative_draw" / "rows.csv"
CATALOG = (TESTS / "fixtures" / "persona_profile" / "catalog.csv").read_bytes()
LABELS = (
    TESTS.parents[2] / "legacy" / "npc-panel-18.6.6" / "app" / "PERSONA_VALUE_LABELS_v17.json"
).read_bytes()
WEIGHT = "vaha_strukturalni_2025"


def _rows() -> tuple[tuple[str, ...], list[dict[str, str]]]:
    header, *raw = list(csv.reader(io.StringIO(ROWS_CSV.read_text("utf-8"))))
    return tuple(header), [dict(zip(header, r, strict=True)) for r in raw]


HEADER, ROWS = _rows()


class _NoEnrichment:
    enricher_id = "test-no-enrichment/v1"

    def derive(self, panel: Any) -> dict[str, tuple[str | None, ...]]:
        return {}


def _population(session: Session, kit: Any, *, omit: tuple[str, ...] = ()) -> Any:
    """The fixture rows as a LIVE population with the persona companions, as a run loads it."""
    from aia_core.application.population import PopulationRuntime
    from aia_core.domain.population import (
        CompanionKind,
        CompanionSpec,
        KnownVersion,
        PopulationImportContract,
        PopulationKind,
        PopulationSelector,
        PopulationView,
        WeightScheme,
        content_sha256,
        field_names_fingerprint,
    )
    from aia_core.infrastructure.population_source import InMemoryPopulationSource

    versions = {
        label: [{**r, "panel_row_id": f"{r['panel_row_id']}-{label}"} for r in ROWS]
        for label in ("v1_BASE", "v1_1", "v1_4")
    }
    panels = {label: kit.gzip_csv(HEADER, rows) for label, rows in versions.items()}
    dictionary = kit.policy_dictionary_csv(
        HEADER,
        {
            "panel_row_id": ("provenance", "PROVENANCE_OR_CORE", "T", "AUDIT_ONLY", "no"),
            "core_donor_id": ("provenance", "PROVENANCE_OR_CORE", "T", "AUDIT_ONLY", "no"),
            WEIGHT: ("weight", "NEW_WEIGHT", "T", "AUDIT_ONLY", "no"),
        },
    )
    certificate = kit.joint_certificate_json(content_sha256(panels["v1_4"]))
    assets = {
        asset: data
        for asset, data in (
            ("CORE_JOINT_STATUS.json", certificate),
            ("PERSONA_SIGNAL_CATALOG_v17.csv", CATALOG),
            ("PERSONA_VALUE_LABELS_v17.json", LABELS),
        )
        if asset not in omit
    }
    specs = tuple(
        CompanionSpec(
            asset_id=asset,
            kind=CompanionKind.CORE_JOINT_STATUS
            if asset == "CORE_JOINT_STATUS.json"
            else CompanionKind.INTEGRITY_ONLY,
            sha256=content_sha256(data),
            byte_size=len(data),
            fmt="json" if asset.endswith(".json") else "csv",
        )
        for asset, data in assets.items()
    )
    total = math.fsum(float(r[WEIGHT] or 0) for r in ROWS)
    contract = PopulationImportContract(
        contract_id="panel_source_population/v1",
        dataset_id="panel_source_population",
        field_count=len(HEADER),
        field_names_sha256=field_names_fingerprint(HEADER),
        dictionary_sha256=content_sha256(dictionary),
        primary_key="panel_row_id",
        expected_rows=len(ROWS),
        weight_schemes=(
            WeightScheme("default_current", WEIGHT, expected_total=total, tolerance=1e-6),
        ),
        default_weight_role="default_current",
        known_versions=(
            KnownVersion("v1_BASE", content_sha256(panels["v1_BASE"]), len(panels["v1_BASE"])),
            KnownVersion("v1_1", content_sha256(panels["v1_1"]), len(panels["v1_1"]), "v1_BASE"),
            KnownVersion("v1_4", content_sha256(panels["v1_4"]), len(panels["v1_4"]), "v1_1"),
        ),
        static_reference_label="v1_1",
        enrichment_fields=(),
        companions=specs,
        joint_certified_labels=frozenset({"v1_4"}),
    )
    source = InMemoryPopulationSource({"dictionary.csv": dictionary})
    for label, data in panels.items():
        source.put(f"panels/{label}.csv.gz", data)
        for asset, blob in assets.items():
            source.put(f"companions/{label}/{asset}", blob)
    rt = PopulationRuntime(session, contract=contract, source=source, enricher=_NoEnrichment())

    def load(label: str) -> Any:
        return rt.import_version(
            label=label,
            panel_location=f"panels/{label}.csv.gz",
            dictionary_location="dictionary.csv",
            provenance="fictional sampling rows",
            imported_by="importer",
            companion_locations={a: f"companions/{label}/{a}" for a in assets},
        )

    load("v1_BASE")
    anchor = load("v1_1")
    rt.establish(
        population_id="PANEL_SOURCE_STATIC",
        kind=PopulationKind.STATIC,
        version_id=anchor.version_id,
        operator=kit.operator,
        reason="the anchor",
    )
    version = load("v1_4")
    rt.establish(
        population_id="PANEL_SOURCE_LIVE",
        kind=PopulationKind.LIVE,
        version_id=version.version_id,
        operator=kit.operator,
        reason="the panel source's test population",
    )
    return rt.load(
        rt.resolve(PopulationSelector.population("PANEL_SOURCE_LIVE"), view=PopulationView.ANALYSIS)
    )


def _spec(n: int = 200, audience: dict[str, Any] | None = None) -> ResearchSpecification:
    design: dict[str, Any] = {
        "title": "Ranní nápoj",
        "n": n,
        "sections": [
            {
                "type": "questions",
                "questions": [
                    {"id": "q1", "text": "Jak často pijete kávu?", "typ": "skala", "skala": [1, 5]},
                    {
                        "id": "q2",
                        "text": "Co si ráno koupíte?",
                        "typ": "vyber",
                        "kategorie": ["Kávu", "Čaj", "Nic"],
                    },
                ],
            }
        ],
    }
    if audience is not None:
        design["audience"] = {"filters": audience}
    spec, problems = compile_design(design)
    assert spec is not None, problems
    return spec


@pytest.fixture
def population(session: Session, population_kit: Any) -> Any:
    return _population(session, population_kit)


def test_a_panel_run_is_sampled_built_and_planned_in_that_order(population: Any) -> None:
    spec = _spec(200)
    built = panel_plans(population, spec, seed=11)
    assert len(built.sample.respondents) == len(built.personas.personas) == len(built.plans) == 200
    ids = population.column("panel_row_id")
    assert [p.persona.persona_id for p in built.plans] == [
        str(ids[r.row]) for r in built.sample.respondents
    ]
    assert all(len(p.profiles) == len(p.blocks) for p in built.plans)
    # Panel-built personas make a modelled dataset, never a fictional one (4b).
    assert dataset_origin([p.persona for p in built.plans]) is DataOrigin.MODELLED_AI_PANEL
    # The run's seed decides it: the same rows, personas and profiles again. (The catalog holds
    # NaN priorities, which never compare equal, so the plans are compared, not the object.)
    again = panel_plans(population, spec, seed=11)
    assert again.sample == built.sample and again.plans == built.plans
    assert panel_plans(population, spec, seed=12).sample != built.sample


def test_the_designs_audience_filters_are_what_the_sample_draws_under(population: Any) -> None:
    """5a decision 4: applied, as 18.6.6 did; recorded in the sample's provenance."""
    spec = _spec(100, audience={"vek": {"min": 60, "max": 89}})
    assert spec.selection is not None and spec.selection.audience_filters
    built = panel_plans(population, spec, seed=3)
    ages = population.column("vek")
    assert all(60 <= int(ages[r.row]) <= 89 for r in built.sample.respondents)
    record = built.provenance(population)
    assert record["sample"]["filters"] == {"vek": {"min": 60, "max": 89}}
    assert record["source"] == PANEL_SOURCE and record["fictional"] is False
    assert record["binding"]["version_id"] == population.binding.version_id
    assert record["personas"]["persona_source"] == "aia-panel-persona-source-1"


def test_a_sampling_refusal_surfaces_by_name_before_any_persona_is_built(
    population: Any,
) -> None:
    with pytest.raises(SamplingRefused) as exceeded:
        panel_plans(population, _spec(len(ROWS) + 1), seed=1)
    assert exceeded.value.reason == "sampling_n_exceeds_support"
    with pytest.raises(SamplingRefused) as small:
        panel_plans(population, _spec(8), seed=1)
    assert small.value.reason == "sampling_unrepresentative"  # OI-99, the owner's decision
    with pytest.raises(ValueError, match="n"):
        panel_plans(population, _spec(10).model_copy(update={"n": None}), seed=1)


def test_a_persona_refusal_surfaces_by_name(session: Session, population_kit: Any) -> None:
    population = _population(session, population_kit, omit=("PERSONA_SIGNAL_CATALOG_v17.csv",))
    with pytest.raises(PersonaRefused) as missing:
        panel_plans(population, _spec(200), seed=1)
    assert missing.value.reason == "persona_catalog_missing"


def test_the_respondent_system_names_every_component_and_fingerprints(population: Any) -> None:
    system = respondent_system(population, model_binding="aws_bedrock/model-x/bedrock-eu-primary")
    assert system["respondent_prompt_sha256"] == PROMPT_SHA256
    assert system["sampler_version"] == SAMPLER_VERSION
    assert system["population_version"] == population.binding.version_id
    assert system["persona_mode"]
    assert len(respondent_system_fingerprint(system)) == 64
    other = respondent_system(population, model_binding="aws_bedrock/model-y/bedrock-eu-primary")
    assert respondent_system_fingerprint(other) != respondent_system_fingerprint(system)
