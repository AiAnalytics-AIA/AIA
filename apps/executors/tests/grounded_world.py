"""A fictional population in the worker's test database, for runs whose respondents come from it.

The rows are the sampler's fictional fixture (``packages/aia_core/tests/fixtures/
representative_draw/rows.csv``: 3,000 rows aged 18 or more on 400 donors, every quota field and the
profile's basic columns), with the persona companions (the fictional signal catalog and the unit's
value labels), imported and established LIVE through ``PopulationRuntime`` exactly as an operator
would. :func:`grounded_population` returns the loader the worker's panel path takes, over that
population -- the production loader reads the v17 contract, which fictional rows cannot meet.
"""

from __future__ import annotations

import csv
import gzip
import io
import json
import math
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

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
from aia_core.infrastructure.population_source import (
    InMemoryPopulationSource,
    PopulationAssetSource,
)
from aia_core.infrastructure.workflow_repository import WorkflowRepository
from sqlalchemy.orm import Session

ROOT = Path(__file__).resolve().parents[3]
CORE_FIXTURES = ROOT / "packages" / "aia_core" / "tests" / "fixtures"
LABELS = ROOT / "legacy" / "npc-panel-18.6.6" / "app" / "PERSONA_VALUE_LABELS_v17.json"
WEIGHT = "vaha_strukturalni_2025"
LIVE = "GROUNDED_LIVE"
_POLICY_HEADER = (
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


def _rows() -> tuple[tuple[str, ...], list[dict[str, str]]]:
    text = (CORE_FIXTURES / "representative_draw" / "rows.csv").read_text("utf-8")
    header, *raw = list(csv.reader(io.StringIO(text)))
    return tuple(header), [dict(zip(header, r, strict=True)) for r in raw]


class _NoEnrichment:
    enricher_id = "test-no-enrichment/v1"

    def derive(self, panel: Any) -> dict[str, tuple[str | None, ...]]:
        return {}


def _operator() -> Any:
    config = PopulationOperatorConfig.from_names(
        {"operator": ("POPULATION_ESTABLISH", "POPULATION_PROMOTE")}
    )
    return PopulationAuthority(config).operator_context(
        AuthenticatedPrincipal(user_id="operator", organization_id="platform")
    )


@dataclass(frozen=True, slots=True)
class GroundedPopulation:
    """The population as established, and how a run reaches it."""

    contract: PopulationImportContract
    source: InMemoryPopulationSource
    rows: int

    def runtime(
        self, session: Session, source: PopulationAssetSource | None = None
    ) -> PopulationRuntime:
        return PopulationRuntime(
            session,
            contract=self.contract,
            source=source if source is not None else self.source,
            enricher=_NoEnrichment(),
        )

    def loader(
        self, source: PopulationAssetSource | None = None
    ) -> Callable[[Session, WorkflowRepository, str], Any]:
        """What the worker's panel path takes: the run's recorded binding, loaded.

        ``source`` replaces where it reads (the worker's composed source over the store).
        """

        def load(session: Session, workflow: WorkflowRepository, run_id: str) -> Any:
            return self.runtime(session, source).load_for_run(workflow, run_id)

        return load


def grounded_population(session: Session, *, omit: tuple[str, ...] = ()) -> GroundedPopulation:
    """Import the fictional rows as v1_BASE, v1_1 (STATIC) and v1_4 (LIVE), and commit."""
    header, base = _rows()
    versions = {
        label: [[r[h] if h != "panel_row_id" else f"{r[h]}-{label}" for h in header] for r in base]
        for label in ("v1_BASE", "v1_1", "v1_4")
    }
    panels = {label: gzip.compress(_csv(header, rows), mtime=0) for label, rows in versions.items()}
    # The dictionary's column order: field, block, source, evidence_status, grade, use, text,
    # persona.
    dictionary = _csv(
        _POLICY_HEADER,
        [
            [
                name,
                (row := _AUDIT.get(name, _DEFAULT))[0],
                "synthetic",
                row[1],
                row[2],
                row[3],
                f"{name} (synthetic)",
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
            "panel_sha256": content_sha256(panels["v1_4"]),
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
    assets = {
        asset: data
        for asset, data in (
            ("CORE_JOINT_STATUS.json", certificate),
            (
                "PERSONA_SIGNAL_CATALOG_v17.csv",
                (CORE_FIXTURES / "persona_profile" / "catalog.csv").read_bytes(),
            ),
            ("PERSONA_VALUE_LABELS_v17.json", LABELS.read_bytes()),
        )
        if asset not in omit
    }
    total = math.fsum(float(r[WEIGHT] or 0) for r in base)
    contract = PopulationImportContract(
        contract_id="grounded_population/v1",
        dataset_id="grounded_population",
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
            KnownVersion("v1_BASE", content_sha256(panels["v1_BASE"]), len(panels["v1_BASE"])),
            KnownVersion("v1_1", content_sha256(panels["v1_1"]), len(panels["v1_1"]), "v1_BASE"),
            KnownVersion("v1_4", content_sha256(panels["v1_4"]), len(panels["v1_4"]), "v1_1"),
        ),
        static_reference_label="v1_1",
        enrichment_fields=(),
        companions=tuple(
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
        ),
        joint_certified_labels=frozenset({"v1_4"}),
    )
    source = InMemoryPopulationSource({"dictionary.csv": dictionary})
    for label, data in panels.items():
        source.put(f"panels/{label}.csv.gz", data)
        for asset, blob in assets.items():
            source.put(f"companions/{label}/{asset}", blob)
    world = GroundedPopulation(contract=contract, source=source, rows=len(base))
    runtime = world.runtime(session)

    def load(label: str) -> Any:
        return runtime.import_version(
            label=label,
            panel_location=f"panels/{label}.csv.gz",
            dictionary_location="dictionary.csv",
            provenance="fictional sampling rows",
            imported_by="importer",
            companion_locations={a: f"companions/{label}/{a}" for a in assets},
        )

    load("v1_BASE")
    anchor = load("v1_1")
    operator = _operator()
    runtime.establish(
        population_id="GROUNDED_STATIC",
        kind=PopulationKind.STATIC,
        version_id=anchor.version_id,
        operator=operator,
        reason="the anchor",
    )
    live = load("v1_4")
    runtime.establish(
        population_id=LIVE,
        kind=PopulationKind.LIVE,
        version_id=live.version_id,
        operator=operator,
        reason="the grounded fieldwork test population",
    )
    session.commit()
    return world
