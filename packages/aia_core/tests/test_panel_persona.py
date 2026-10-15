"""Panel personas from a run's sample, through the canonical loader (chunk 3e).

The population here is ``tests/fixtures/persona_profile/signals.csv`` (fictional rows carrying
every column the profile reads and the fictional catalog's signals), imported with the catalog and
the unit's own value labels as companions and loaded as the ANALYSIS view a run binds. Its
profiles must be exactly what 18.6.6 showed for the same row and topics, captured in
``tests/fixtures/persona_profile/expected.json`` (``tools/persona_capture.py``).
"""

from __future__ import annotations

import csv
import io
import json
import math
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy.orm import Session

from aia_core.domain.ai_respondent import build_request, plan_items
from aia_core.domain.licence import DataLineage
from aia_core.domain.licence_determinations import PANEL_DERIVED_DATASETS
from aia_core.domain.panel_persona import PersonaRefused, panel_personas
from aia_core.domain.persona_profile import PERSONA_MODE
from aia_core.domain.persona_topics import block_topics
from aia_core.domain.population.sampling import (
    PanelSample,
    SampleAudit,
    SampledRespondent,
)
from aia_core.domain.residency import DataClass
from aia_core.domain.respondent_behavior import assign_styles

FIXTURES = Path(__file__).parent / "fixtures" / "persona_profile"
UNIT = Path(__file__).resolve().parents[3] / "legacy" / "npc-panel-18.6.6" / "app"
EXPECTED: dict[str, Any] = json.loads((FIXTURES / "expected.json").read_text("utf-8"))
INPUTS: dict[str, Any] = json.loads((FIXTURES / "cases.json").read_text("utf-8"))
CATALOG_BYTES = (FIXTURES / "catalog.csv").read_bytes()
LABELS_BYTES = (UNIT / "PERSONA_VALUE_LABELS_v17.json").read_bytes()
WEIGHT = "w"


def _read() -> tuple[list[str], list[dict[str, str]]]:
    reader = csv.reader(io.StringIO((FIXTURES / "signals.csv").read_text("utf-8")))
    header, *raw = list(reader)
    rows = [dict(zip(header, r, strict=True)) for r in raw]
    for i, row in enumerate(rows):
        row["core_donor_id"] = f"FIC-DONOR-{i % 7 + 1:03d}"
        row[WEIGHT] = f"{1 + (i % 5) / 10:.1f}"
    return [*header, "core_donor_id", WEIGHT], rows


HEADER, ALL_ROWS = _read()
#: The rows 18.6.6's Panel kept (an age, 18 or more): the population built here. The others
#: exist in the fixture for the profile's "ve věku neuvedeno" and are refused as a population.
AGED = [i for i, r in enumerate(ALL_ROWS) if r["vek"] and int(r["vek"]) >= 18]
ROWS = [ALL_ROWS[i] for i in AGED]


def _population(
    session: Session,
    kit: Any,
    *,
    header: Sequence[str] = tuple(HEADER),
    rows: Sequence[Mapping[str, str]] = ROWS,
    omit: Sequence[str] = (),
    policy: Mapping[str, tuple[str, str, str, str, str]] | None = None,
    matched: Sequence[str] = ("issp",),
    population_id: str = "PERSONA_LIVE",
) -> Any:
    """``rows`` as a population version with the persona companions, loaded as a run would."""
    gzip_csv, joint_certificate_json = kit.gzip_csv, kit.joint_certificate_json
    policy_dictionary_csv = kit.policy_dictionary_csv

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

    fields = tuple(header)
    versions = {
        label: [{**r, "panel_row_id": f"{r['panel_row_id']}{suffix}"} for r in rows]
        for label, suffix in (("v1_BASE", "-B"), ("v1_1", "-S"), ("v1_4", ""))
    }
    panels = {label: gzip_csv(fields, r) for label, r in versions.items()}
    base_policy = {
        "panel_row_id": ("provenance", "PROVENANCE_OR_CORE", "T", "AUDIT_ONLY", "no"),
        "core_donor_id": ("provenance", "PROVENANCE_OR_CORE", "T", "AUDIT_ONLY", "no"),
        WEIGHT: ("weight", "NEW_WEIGHT", "T", "AUDIT_ONLY", "no"),
        **{
            c: ("issp", "MATCHED_WHOLE_BLOCK", "B", "PERSONA_OR_ANALYSIS_WITH_SCOPE", "yes")
            for c in fields
            if c.startswith(("SIG_trust", "SIG_vote", "SIG_news")) or c == "_donor_issp_quality"
        },
        **(policy or {}),
    }
    dictionary = policy_dictionary_csv(fields, base_policy)
    certificate = joint_certificate_json(
        content_sha256(panels["v1_4"]), matched_blocks=list(matched)
    )
    assets = {
        asset: data
        for asset, data in (
            ("CORE_JOINT_STATUS.json", certificate),
            ("PERSONA_SIGNAL_CATALOG_v17.csv", CATALOG_BYTES),
            ("PERSONA_VALUE_LABELS_v17.json", LABELS_BYTES),
        )
        if asset not in omit
    }
    kinds = {"CORE_JOINT_STATUS.json": CompanionKind.CORE_JOINT_STATUS}
    specs = tuple(
        CompanionSpec(
            asset_id=asset,
            kind=kinds.get(asset, CompanionKind.INTEGRITY_ONLY),
            sha256=content_sha256(data),
            byte_size=len(data),
            fmt="json" if asset.endswith(".json") else "csv",
        )
        for asset, data in assets.items()
    )
    total = math.fsum(float(r[WEIGHT]) for r in rows)
    contract = PopulationImportContract(
        contract_id="persona_population/v1",
        dataset_id="persona_population",
        field_count=len(fields),
        field_names_sha256=field_names_fingerprint(fields),
        dictionary_sha256=content_sha256(dictionary),
        primary_key="panel_row_id",
        expected_rows=len(rows),
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
        for asset, data_ in assets.items():
            source.put(f"companions/{label}/{asset}", data_)

    class _NoEnrichment:
        enricher_id = "test-no-enrichment/v1"

        def derive(self, panel: Any) -> dict[str, tuple[str | None, ...]]:
            return {}

    rt = PopulationRuntime(session, contract=contract, source=source, enricher=_NoEnrichment())

    def load(label: str) -> Any:
        return rt.import_version(
            label=label,
            panel_location=f"panels/{label}.csv.gz",
            dictionary_location="dictionary.csv",
            provenance="fictional persona rows",
            imported_by="importer",
            companion_locations={a: f"companions/{label}/{a}" for a in assets},
        )

    load("v1_BASE")
    anchor = load("v1_1")
    rt.establish(
        population_id="PERSONA_STATIC",
        kind=PopulationKind.STATIC,
        version_id=anchor.version_id,
        operator=kit.operator,
        reason="the anchor",
    )
    version = load("v1_4")
    rt.establish(
        population_id=population_id,
        kind=PopulationKind.LIVE,
        version_id=version.version_id,
        operator=kit.operator,
        reason="the persona test population",
    )
    return {
        "live": rt.load(
            rt.resolve(PopulationSelector.population(population_id), view=PopulationView.ANALYSIS)
        ),
        "static": rt.load(
            rt.resolve(
                PopulationSelector.population("PERSONA_STATIC"), view=PopulationView.ANALYSIS
            )
        ),
    }


def _sample(population: Any, rows: Sequence[int]) -> PanelSample:
    """A sample naming ``rows``; the sampler itself is chunk 2e's, tested there."""
    donors = population.column("core_donor_id")
    audit = SampleAudit(
        status="PASS",
        population_n=population.row_count,
        sample_n=len(rows),
        fields=(),
        quota_fields=(),
        selection_method="largest_remainder",
        raw=None,
        weighted=None,
        raw_tolerance_pp=0.5,
        weighted_tolerance_pp=0.25,
        raw_selection_warning=False,
        effective_n=float(len(rows)),
        effective_n_ratio=1.0,
        weight_min=1.0,
        weight_max=1.0,
        audience_donors=None,
        sample_donors=None,
    )
    return PanelSample(
        respondents=tuple(
            SampledRespondent(
                row=r, donor=donors[r], base_weight=1.0, analysis_weight=0.5 + k, order=k
            )
            for k, r in enumerate(rows)
        ),
        audit=audit,
        filters={},
        seed=1,
        version_id=population.binding.version_id,
        content_sha256=population.binding.content_sha256,
    )


@pytest.fixture
def population(session: Session, population_kit: Any) -> Any:
    return _population(session, population_kit)["live"]


def test_every_sampled_row_becomes_a_panel_persona(population: Any) -> None:
    built = panel_personas(population, _sample(population, [0, 5, 9]))
    ids = population.column("panel_row_id")
    assert [p.persona_id for p in built.personas] == [ids[0], ids[5], ids[9]]
    assert [p.donor_id for p in built.personas] == [ROWS[i]["core_donor_id"] for i in (0, 5, 9)]
    assert [p.weight for p in built.personas] == [0.5, 1.5, 2.5]  # the sample's raked weight
    assert all(not p.fictional for p in built.personas)
    assert all(p.lineage == PANEL_DERIVED_DATASETS for p in built.personas)
    assert built.personas[0].facts["pohlavi"] == ROWS[0]["pohlavi"]
    assert built.personas[0].facts["vek"] == int(ROWS[0]["vek"])
    assert built.provenance()["persona_mode"] == PERSONA_MODE


def test_styles_are_assigned_over_the_whole_population_as_18_6_6_did(population: Any) -> None:
    built = panel_personas(population, _sample(population, [3, 7]))
    everyone = assign_styles(
        [
            {
                "respondent_id": population.column("panel_row_id")[i],
                "vek": int(ROWS[i]["vek"]) if ROWS[i]["vek"] else None,
                "pohlavi": ROWS[i]["pohlavi"],
                "vzdelani": ROWS[i]["vzdelani"] or None,
            }
            for i in range(len(ROWS))
        ]
    )
    for persona, i in zip(built.personas, (3, 7), strict=True):
        assert persona.style == {k: round(v, 6) for k, v in everyone[i].items()}
    # Styled over the sample alone they would differ: the z-scores are the population's.
    alone = assign_styles(
        [
            {
                "respondent_id": p.persona_id,
                **{k: p.facts.get(k) for k in ("vek", "pohlavi", "vzdelani")},
            }
            for p in built.personas
        ]
    )
    assert built.personas[0].style != {k: round(v, 6) for k, v in alone[0].items()}


@pytest.mark.parametrize(
    "index", [i for i, c in enumerate(INPUTS["signal_cases"]) if c["row"] in AGED][::2]
)
def test_a_personas_profile_is_what_18_6_6_showed_for_its_row(population: Any, index: int) -> None:
    case = INPUTS["signal_cases"][index]
    built = panel_personas(population, _sample(population, [AGED.index(case["row"])]))
    persona = built.personas[0]
    assert (
        built.profile(persona.persona_id, case["topics"]) == (EXPECTED["signals"][index]["persona"])
    )


def test_each_block_is_shown_the_profile_of_its_own_topics(population: Any) -> None:
    from test_ai_respondent import _spec

    spec = _spec()
    built = panel_personas(population, _sample(population, [4]))
    persona = built.personas[0]
    plan = built.plan(spec, persona)
    assert "q_sex" in plan.facts  # answered from the row by code, never asked
    assert len(plan.profiles) == len(plan.blocks) > 1
    for block in plan.blocks:
        topics = block_topics([(item.text, item.labels) for item in block.items])
        assert plan.profiles[block.index] == built.profile(persona.persona_id, topics)
    request = build_request(
        plan,
        plan.blocks[0],
        {},
        items_by_id={i.item_id: i for i in plan_items(spec)},
        policy_version="test",
        data_class=DataClass.CLASS_A_CLIENT_CONFIDENTIAL,
        lineage=DataLineage(datasets=frozenset(PANEL_DERIVED_DATASETS)),
        max_output_tokens=1000,
    )
    assert plan.profiles[0] in request.messages[0].content
    assert "FIKTIVNÍ" not in request.messages[0].content


def test_a_field_the_policy_refuses_is_left_out_and_recorded(
    session: Session, population_kit: Any
) -> None:
    refused = {"kraj": ("core", "POPULATION_ANCHOR", "A", "PERSONA_OR_ANALYSIS_WITH_SCOPE", "no")}
    population = _population(session, population_kit, policy=refused)["live"]
    built = panel_personas(population, _sample(population, [1]))
    assert ("kraj", "not_persona_eligible") in built.refused_fields
    persona = built.personas[0]
    assert "kraj" not in built.rows[persona.persona_id]
    assert "Žiju v kraji" not in built.profile(persona.persona_id, [])


def test_a_population_whose_joint_use_is_refused_gets_no_personas(
    session: Session, population_kit: Any
) -> None:
    static = _population(session, population_kit)["static"]  # the certificate certifies v1_4 only
    with pytest.raises(PersonaRefused) as refused:
        panel_personas(static, _sample(static, [0]))
    assert refused.value.reason == "persona_joint_refused"


def test_matched_block_fields_are_gated_within_their_block_not_across(
    session: Session, population_kit: Any
) -> None:
    """Core and the issp block each pass; across them the persona shows a labelled match."""
    population = _population(session, population_kit)["live"]
    assert not population.decide_joint(["SIG_trust_gov", "pohlavi"], client_facing=False).allowed
    built = panel_personas(population, _sample(population, [2]))
    assert built.personas  # built, with the issp signals carrying their provenance


@pytest.mark.parametrize(
    ("change", "reason"),
    [
        ("no_catalog", "persona_catalog_missing"),
        ("no_labels", "persona_value_labels_missing"),
        ("compatibility", "persona_compatibility_block_unported"),
        ("minor", "persona_age_out_of_scope"),
        ("no_age", "persona_age_out_of_scope"),
    ],
)
def test_a_persona_that_cannot_be_built_as_18_6_6_built_it_is_refused(
    session: Session, population_kit: Any, change: str, reason: str
) -> None:
    from aia_core.domain.population import PopulationError

    header, rows = list(HEADER), [dict(r) for r in ROWS]
    omit = {
        "no_catalog": ("PERSONA_SIGNAL_CATALOG_v17.csv",),
        "no_labels": ("PERSONA_VALUE_LABELS_v17.json",),
    }.get(change, ())
    if change == "compatibility":
        header.append("P_media_tv_10")
        for r in rows:
            r["P_media_tv_10"] = "5"
    if change == "minor":
        rows[6]["vek"] = "16"
    if change == "no_age":
        rows[6]["vek"] = ""
    population = _population(session, population_kit, header=header, rows=rows, omit=omit)["live"]
    with pytest.raises(PopulationError) as refused:
        panel_personas(population, _sample(population, [0]))
    assert refused.value.reason == reason
