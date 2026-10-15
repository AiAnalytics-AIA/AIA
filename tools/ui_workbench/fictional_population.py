"""WORKBENCH ONLY. A fictional LIVE population for the audience step (panel-grounded 6f).

The audience step reads AIA's population: its factor catalogue
(``GET /api/v1/population/audience-catalogue``) and the feasibility preview
(``POST /api/v1/population/audience-preview``). The develop seed establishes none, and
the v17 contract pins 18,766 licence-bound rows that never come to this machine, so the
workbench imports the sampler's fictional fixture instead
(``packages/aia_core/tests/fixtures/representative_draw/rows.csv``: 3,000 invented rows
on 400 invented donors, every quota field), under a contract of its own, through
``PopulationRuntime`` exactly as an operator would, and keeps its catalogue.

:func:`install` then points the running API's audience routes at it, through the one
seam the composition root offers (``app.state.audience_population`` and
``app.state.audience_previewer``). Research runs are untouched: they keep recording the
Czech LIVE, which the workbench has not established.
"""

from __future__ import annotations

import csv
import gzip
import io
import json
import math
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[2]
ROWS = REPO / "packages" / "aia_core" / "tests" / "fixtures" / "representative_draw" / "rows.csv"
WEIGHT = "vaha_strukturalni_2025"
LIVE = "WORKBENCH_FICTIONAL_LIVE"
STATIC = "WORKBENCH_FICTIONAL_STATIC"
_HEADER = (
    "field",
    "block",
    "source",
    "evidence_status",
    "production_grade",
    "recommended_use",
    "description",
    "persona_eligible",
)
_DEFAULT = ("core", "POPULATION_ANCHOR", "A", "PERSONA_OR_ANALYSIS_WITH_SCOPE", "yes")
_AUDIT = {
    "panel_row_id": ("provenance", "PROVENANCE_OR_CORE", "T", "AUDIT_ONLY", "no"),
    "core_donor_id": ("provenance", "PROVENANCE_OR_CORE", "T", "AUDIT_ONLY", "no"),
    WEIGHT: ("weight", "NEW_WEIGHT", "T", "AUDIT_ONLY", "no"),
}


def _csv(header: tuple[str, ...], rows: list[list[str]]) -> bytes:
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(header)
    writer.writerows(rows)
    return buffer.getvalue().encode("utf-8")


class _NoEnrichment:
    enricher_id = "workbench-no-enrichment/v1"

    def derive(self, panel: Any) -> dict[str, tuple[str | None, ...]]:
        return {}


def build(session: Any) -> tuple[Any, Any]:
    """Import and establish the fictional population, keep LIVE's catalogue, and commit.

    Returns the contract and the asset source the API's previewer reads.
    """
    from aia_core.application.population import PopulationRuntime
    from aia_core.application.population_authority import (
        PopulationAuthority,
        PopulationOperatorConfig,
    )
    from aia_core.application.scope import AuthenticatedPrincipal
    from aia_core.domain.population import (
        CompanionKind,
        CompanionSpec,
        KnownVersion,
        PopulationImportContract,
        PopulationKind,
        WeightScheme,
        content_sha256,
        field_names_fingerprint,
    )
    from aia_core.infrastructure.population_repository import PopulationRegistryRepository
    from aia_core.infrastructure.population_source import InMemoryPopulationSource

    header_row, *body = list(csv.reader(io.StringIO(ROWS.read_text("utf-8"))))
    header = tuple(header_row)
    base = [dict(zip(header, r, strict=True)) for r in body]
    panels = {
        label: gzip.compress(
            _csv(header, [[r[h] if h != "panel_row_id" else f"{r[h]}-{label}" for h in header]
                          for r in base]),
            mtime=0,
        )
        for label in ("wb1_BASE", "wb1_1", "wb1_4")
    }  # fmt: skip
    dictionary = _csv(
        _HEADER,
        [
            [
                name,
                (row := _AUDIT.get(name, _DEFAULT))[0],
                "fictional",
                row[1],
                row[2],
                row[3],
                f"{name} (fictional)",
                row[4],
            ]
            for name in header
        ],
    )
    certificate = json.dumps(
        {
            "status": "COHERENT_CORE_MATCHED_BLOCKS",
            "structure_status": "QC_PASSED",
            "prediction_validation_status": "EXTERNAL_HOLDOUT_PENDING",
            "panel_sha256": content_sha256(panels["wb1_4"]),
            "matched_blocks": [],
            "core_same_person_joint": True,
            "cross_block_same_person_joint": False,
            "client_joint_outputs_allowed": False,
            "descriptive_core_outputs_allowed": True,
            "matched_block_outputs_allowed": True,
            "cross_block_joint_claims_allowed": False,
        },
        indent=2,
    ).encode("utf-8")
    total = math.fsum(float(r[WEIGHT] or 0) for r in base)
    contract = PopulationImportContract(
        contract_id="workbench_fictional_population/v1",
        dataset_id="workbench_fictional_population",
        field_count=len(header),
        field_names_sha256=field_names_fingerprint(header),
        dictionary_sha256=content_sha256(dictionary),
        primary_key="panel_row_id",
        expected_rows=len(base),
        weight_schemes=(
            WeightScheme("default_current", WEIGHT, expected_total=total, tolerance=1e-6),
        ),
        default_weight_role="default_current",
        known_versions=(
            KnownVersion("wb1_BASE", content_sha256(panels["wb1_BASE"]), len(panels["wb1_BASE"])),
            KnownVersion(
                "wb1_1", content_sha256(panels["wb1_1"]), len(panels["wb1_1"]), "wb1_BASE"
            ),
            KnownVersion("wb1_4", content_sha256(panels["wb1_4"]), len(panels["wb1_4"]), "wb1_1"),
        ),
        static_reference_label="wb1_1",
        enrichment_fields=(),
        companions=(
            CompanionSpec(
                asset_id="CORE_JOINT_STATUS.json",
                kind=CompanionKind.CORE_JOINT_STATUS,
                sha256=content_sha256(certificate),
                byte_size=len(certificate),
                fmt="json",
            ),
        ),
        joint_certified_labels=frozenset({"wb1_4"}),
    )
    source = InMemoryPopulationSource({"dictionary.csv": dictionary})
    for label, data in panels.items():
        source.put(f"panels/{label}.csv.gz", data)
        source.put(f"companions/{label}/CORE_JOINT_STATUS.json", certificate)
    runtime = PopulationRuntime(session, contract=contract, source=source, enricher=_NoEnrichment())
    operator = PopulationAuthority(
        PopulationOperatorConfig.from_names(
            {"workbench": ("POPULATION_ESTABLISH", "POPULATION_PROMOTE")}
        )
    ).operator_context(AuthenticatedPrincipal(user_id="workbench", organization_id="platform"))

    def load(label: str) -> Any:
        return runtime.import_version(
            label=label,
            panel_location=f"panels/{label}.csv.gz",
            dictionary_location="dictionary.csv",
            provenance="the workbench's fictional sampling rows",
            imported_by="workbench",
            companion_locations={
                "CORE_JOINT_STATUS.json": f"companions/{label}/CORE_JOINT_STATUS.json"
            },
        )

    registry = PopulationRegistryRepository(session)
    established = registry.population(LIVE)
    if established is None:  # a fresh workbench database; a restart finds it there
        load("wb1_BASE")
        anchor = load("wb1_1")
        runtime.establish(
            population_id=STATIC,
            kind=PopulationKind.STATIC,
            version_id=anchor.version_id,
            operator=operator,
            reason="the workbench's fictional anchor",
        )
        live_version = load("wb1_4").version_id
        runtime.establish(
            population_id=LIVE,
            kind=PopulationKind.LIVE,
            version_id=live_version,
            operator=operator,
            reason="the workbench's fictional audience population",
        )
    else:
        live_version = established.current_version_id
    runtime.record_audience_catalogue(live_version, recorded_by="workbench")  # once per version
    session.commit()
    return contract, source


def install(app: Any, contract: Any, source: Any) -> None:
    """Point the running API's audience routes at the fictional population."""
    from aia_api.dependencies import AudiencePopulation
    from aia_core.application.audience_preview import AudiencePreviewer

    app.state.audience_population = AudiencePopulation(contract=contract, population_id=LIVE)
    app.state.audience_previewer = AudiencePreviewer(
        contract=contract, source=source, enricher=_NoEnrichment(), population_id=LIVE
    )
