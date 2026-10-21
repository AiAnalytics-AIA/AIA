"""LOCAL AND TEST ONLY. A fictional population both processes compose: the API and the worker.

Tier A of the MVP acceptance harness drives AIA over HTTP with the real worker, and AC-05 needs a
run whose respondents come from its population. The Czech v17 contract pins 18,766 licence-bound
rows that never come to a test machine, and fictional rows cannot meet its pins, so until now
every panel test injected a loader into the worker in-process and the API recorded LIVE from a
contract of the test's own (plan ``run-qc-and-checkpoint`` RQC10; trace 2, "Tier A cannot run
AC-05 through HTTP"). This module is the population double instead: **one** fictional population
under a contract of its own, composed by configuration in both processes, so a run started over
HTTP records it and the worker's panel path reads the same bytes.

What it is: the sampler's fictional fixture (``packages/aia_core/tests/fixtures/representative_draw/
rows.csv``: 3,000 invented rows aged 18 or more on 400 invented donors, every quota field), its
persona companions (the fictional signal catalog and the unit's value labels) and a joint
certificate naming the panel, imported and established through :class:`PopulationRuntime`
exactly as an operator would. Nothing here bypasses the canonical loader, the field policy or the
certificate gate: a run reads it through ``load_for_run`` like any other population.

Where it may exist: :data:`ALLOWED_ENVIRONMENTS` only. :func:`population_double` refuses any other
``AIA_ENV`` (an unset or unknown one included) before it reads a byte, the API's settings refuse
the switch in every deployed environment, and ``make layer_check`` keeps every module but the two
compositions from importing this one and every deployment from naming it -- the rules the
workbench composition and recorded web retrieval are kept by.
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
from typing import Any, Final

from sqlalchemy.orm import Session

from ..domain.deployment import DeploymentEnvironment
from ..domain.population import (
    CompanionKind,
    CompanionSpec,
    KnownVersion,
    PopulationImportContract,
    PopulationKind,
    RuntimePopulation,
    WeightScheme,
    content_sha256,
    field_names_fingerprint,
)
from ..infrastructure.population_repository import PopulationRegistryRepository
from ..infrastructure.population_source import InMemoryPopulationSource, PopulationAssetSource
from ..infrastructure.workflow_repository import WorkflowRepository
from .audience_preview import AudiencePreviewer
from .population import PopulationRuntime
from .population_authority import PopulationAuthority, PopulationOperatorConfig
from .scope import AuthenticatedPrincipal

__all__ = [
    "ALLOWED_ENVIRONMENTS",
    "DOUBLE_NAMES",
    "POPULATION_DOUBLE_KEY",
    "WEIGHT",
    "PopulationDouble",
    "PopulationDoubleNames",
    "PopulationDoubleRefused",
    "population_double",
    "population_double_problem",
]

#: Where the double may be composed. Anything else -- develop, staging, production, unset or
#: unknown -- refuses before a byte is read.
ALLOWED_ENVIRONMENTS: Final = frozenset({DeploymentEnvironment.LOCAL, DeploymentEnvironment.TEST})

#: The switch both processes read: the API's ``Settings.population_double`` and the worker's
#: composition ``aia_executors.population_double:build_registry``, which needs no switch.
POPULATION_DOUBLE_KEY: Final = "AIA_POPULATION_DOUBLE"

#: The fixture's weight column, the contract's one weight scheme.
WEIGHT: Final = "vaha_strukturalni_2025"

#: The repository this module sits in: the fixtures are read from a checkout, never a wheel.
_REPO: Final = Path(__file__).resolve().parents[5]
_ROWS: Final = (
    _REPO / "packages" / "aia_core" / "tests" / "fixtures" / "representative_draw" / "rows.csv"
)
_CATALOG: Final = _REPO / "packages" / "aia_core" / "tests" / "fixtures" / "persona_profile"
_LABELS: Final = _REPO / "legacy" / "npc-panel-18.6.6" / "app" / "PERSONA_VALUE_LABELS_v17.json"

_POLICY_HEADER: Final = (
    "field",
    "block",
    "source",
    "evidence_status",
    "production_grade",
    "recommended_use",
    "description",
    "persona_eligible",
)
_DEFAULT: Final = ("core", "POPULATION_ANCHOR", "A", "PERSONA_OR_ANALYSIS_WITH_SCOPE", "yes")
_AUDIT: Final = {
    "panel_row_id": ("provenance", "PROVENANCE_OR_CORE", "T", "AUDIT_ONLY", "no"),
    "core_donor_id": ("provenance", "PROVENANCE_OR_CORE", "T", "AUDIT_ONLY", "no"),
    WEIGHT: ("weight", "NEW_WEIGHT", "T", "AUDIT_ONLY", "no"),
}
#: The three versions the contract knows, oldest first: a base, the STATIC anchor, LIVE.
_LABELS_IN_ORDER: Final = ("v1_BASE", "v1_1", "v1_4")
_CERTIFICATE: Final = "CORE_JOINT_STATUS.json"
_SIGNALS: Final = "PERSONA_SIGNAL_CATALOG_v17.csv"
_VALUE_LABELS: Final = "PERSONA_VALUE_LABELS_v17.json"


class PopulationDoubleRefused(RuntimeError):
    """The double was asked for where it may not exist, or its fixture is not on this machine."""


@dataclass(frozen=True, slots=True)
class PopulationDoubleNames:
    """What the double is called: its contract, its populations and who imported it."""

    contract_id: str
    dataset_id: str
    live: str
    static: str
    imported_by: str


#: The names tier A and the composition use.
DOUBLE_NAMES: Final = PopulationDoubleNames(
    contract_id="aia_population_double/v1",
    dataset_id="aia_population_double",
    live="DOUBLE_FICTIONAL_LIVE",
    static="DOUBLE_FICTIONAL_STATIC",
    imported_by="population-double",
)


class _NoEnrichment:
    """The double has no runtime dimensions to derive: its rows carry every field they use."""

    enricher_id = "population-double-no-enrichment/v1"

    def derive(self, panel: Any) -> dict[str, tuple[str | None, ...]]:
        return {}


def population_double_problem(environment: DeploymentEnvironment | None) -> str | None:
    """Why the double may not be composed here, or ``None`` when it may (local and test only)."""
    if environment in ALLOWED_ENVIRONMENTS:
        return None
    where = environment.value if environment is not None else "an unset or unknown AIA_ENV"
    return (
        f"the population double is fictional and refuses {where}: it is composed only in local "
        "and test, never in a deployment (plan run-qc-and-checkpoint RQC10)"
    )


def _csv(header: tuple[str, ...], rows: list[list[str]]) -> bytes:
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(header)
    writer.writerows(rows)
    return buffer.getvalue().encode("utf-8")


def _read(path: Path) -> bytes:
    try:
        return path.read_bytes()
    except FileNotFoundError as exc:
        raise PopulationDoubleRefused(
            f"the population double's fixture {path.name} is not on this machine; it is built "
            "only from a checkout of the repository"
        ) from exc


@dataclass(frozen=True, slots=True)
class PopulationDouble:
    """The fictional population: its contract, its bytes and how each process reaches it.

    Built only by :func:`population_double`. The bytes are deterministic (gzip ``mtime=0``), so
    the API's process and the worker's build the same contract and the same source independently.
    """

    names: PopulationDoubleNames
    contract: PopulationImportContract
    source: InMemoryPopulationSource
    rows: int
    companions: tuple[str, ...]

    @property
    def population_id(self) -> str:
        """The LIVE population a run records."""
        return self.names.live

    def runtime(
        self, session: Session, source: PopulationAssetSource | None = None
    ) -> PopulationRuntime:
        """The canonical loader over the double's contract and bytes (``source`` replaces them)."""
        return PopulationRuntime(
            session,
            contract=self.contract,
            source=source if source is not None else self.source,
            enricher=_NoEnrichment(),
        )

    def loader(
        self, source: PopulationAssetSource | None = None
    ) -> Callable[[Session, WorkflowRepository, str], RuntimePopulation]:
        """What the worker's panel path takes (``build_ai_fieldwork(population=)``): the run's
        recorded binding, loaded through the canonical loader."""

        def load(session: Session, workflow: WorkflowRepository, run_id: str) -> RuntimePopulation:
            return self.runtime(session, source).load_for_run(workflow, run_id)

        return load

    def previewer(self) -> AudiencePreviewer:
        """The audience preview over the double's LIVE, for the API's audience routes."""
        return AudiencePreviewer(
            contract=self.contract,
            source=self.source,
            enricher=_NoEnrichment(),
            population_id=self.names.live,
        )

    def establish(self, session: Session) -> str:
        """Import the three versions, establish STATIC and LIVE, keep LIVE's audience catalogue,
        and return LIVE's version id. The caller commits.

        Idempotent: a database that already holds the double's LIVE keeps it and is not imported
        again, so a restarted API finds what it established."""
        runtime = self.runtime(session)
        established = PopulationRegistryRepository(session).population(self.names.live)
        if established is not None:
            live_version = established.current_version_id
        else:
            operator = PopulationAuthority(
                PopulationOperatorConfig.from_names(
                    {self.names.imported_by: ("POPULATION_ESTABLISH", "POPULATION_PROMOTE")}
                )
            ).operator_context(
                AuthenticatedPrincipal(user_id=self.names.imported_by, organization_id="platform")
            )

            def load(label: str) -> str:
                return runtime.import_version(
                    label=label,
                    panel_location=f"panels/{label}.csv.gz",
                    dictionary_location="dictionary.csv",
                    provenance="the population double's fictional sampling rows",
                    imported_by=self.names.imported_by,
                    companion_locations={a: f"companions/{label}/{a}" for a in self.companions},
                ).version_id

            load(_LABELS_IN_ORDER[0])
            runtime.establish(
                population_id=self.names.static,
                kind=PopulationKind.STATIC,
                version_id=load(_LABELS_IN_ORDER[1]),
                operator=operator,
                reason="the population double's fictional anchor",
            )
            live_version = load(_LABELS_IN_ORDER[2])
            runtime.establish(
                population_id=self.names.live,
                kind=PopulationKind.LIVE,
                version_id=live_version,
                operator=operator,
                reason="the population double: fictional respondents for tier A (RQC10)",
            )
        runtime.record_audience_catalogue(live_version, recorded_by=self.names.imported_by)
        return live_version


def population_double(
    environment: DeploymentEnvironment | None,
    *,
    names: PopulationDoubleNames = DOUBLE_NAMES,
    omit: tuple[str, ...] = (),
) -> PopulationDouble:
    """The population double, refused (:class:`PopulationDoubleRefused`) outside local and test.

    ``omit`` leaves named companions out of the contract and the bytes (a test of what a
    population without them does); ``names`` lets a test keep its own population ids.
    """
    problem = population_double_problem(environment)
    if problem is not None:
        raise PopulationDoubleRefused(problem)
    text = _read(_ROWS).decode("utf-8")
    header_row, *body = list(csv.reader(io.StringIO(text)))
    header = tuple(header_row)
    base = [dict(zip(header, r, strict=True)) for r in body]
    panels = {
        label: gzip.compress(
            _csv(
                header,
                [
                    [r[h] if h != "panel_row_id" else f"{r[h]}-{label}" for h in header]
                    for r in base
                ],
            ),
            mtime=0,
        )
        for label in _LABELS_IN_ORDER
    }
    live_label = _LABELS_IN_ORDER[-1]
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
            # As the v17 certificate names it; the evidence gate reads a certificate only with
            # its production panel named.
            "production_panel": "FICTIONAL_PANEL_v1_4.csv",
            "panel_sha256": content_sha256(panels[live_label]),
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
    readers: dict[str, Callable[[], bytes]] = {
        _CERTIFICATE: lambda: certificate,
        _SIGNALS: lambda: _read(_CATALOG / "catalog.csv"),
        _VALUE_LABELS: lambda: _read(_LABELS),
    }
    # Read only what the contract keeps: an omitted companion is never required on disk.
    assets = {asset: read() for asset, read in readers.items() if asset not in omit}
    total = math.fsum(float(r[WEIGHT] or 0) for r in base)
    known: list[KnownVersion] = []
    for i, label in enumerate(_LABELS_IN_ORDER):
        parent = _LABELS_IN_ORDER[i - 1] if i else None
        known.append(
            KnownVersion(label, content_sha256(panels[label]), len(panels[label]), parent)
            if parent
            else KnownVersion(label, content_sha256(panels[label]), len(panels[label]))
        )
    contract = PopulationImportContract(
        contract_id=names.contract_id,
        dataset_id=names.dataset_id,
        field_count=len(header),
        field_names_sha256=field_names_fingerprint(header),
        dictionary_sha256=content_sha256(dictionary),
        primary_key="panel_row_id",
        expected_rows=len(base),
        weight_schemes=(
            WeightScheme("default_current", WEIGHT, expected_total=total, tolerance=1e-6),
        ),
        default_weight_role="default_current",
        known_versions=tuple(known),
        static_reference_label=_LABELS_IN_ORDER[1],
        enrichment_fields=(),
        companions=tuple(
            CompanionSpec(
                asset_id=asset,
                kind=CompanionKind.CORE_JOINT_STATUS
                if asset == _CERTIFICATE
                else CompanionKind.INTEGRITY_ONLY,
                sha256=content_sha256(data),
                byte_size=len(data),
                fmt="json" if asset.endswith(".json") else "csv",
            )
            for asset, data in assets.items()
        ),
        joint_certified_labels=frozenset({live_label}),
    )
    source = InMemoryPopulationSource({"dictionary.csv": dictionary})
    for label, data in panels.items():
        source.put(f"panels/{label}.csv.gz", data)
        for asset, blob in assets.items():
            source.put(f"companions/{label}/{asset}", blob)
    return PopulationDouble(
        names=names,
        contract=contract,
        source=source,
        rows=len(base),
        companions=tuple(assets),
    )
