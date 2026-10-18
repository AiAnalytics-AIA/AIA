"""The client report of a modelled research run (complete-study-report B5b/B5c).

The internal report is for the team. This is the document a client receives, and it prints
only what may leave AIA:

* numbers admitted ``CLIENT_FACING``, one question at a time, from the run's evidence judged
  under the owner's recorded lift (:data:`MODELLED_CLIENT_REPORT_LIFT`) and the population's
  certificate the run recorded (B5a) -- support, intervals and suppression unchanged;
* every number labelled modelled, beside it and in the method callout on the page;
* only the maps the Sociomap register approves, as figures (B4);
* the design and the questionnaire, which are words, not results.

A run whose respondents were not modelled from the population (fictional or unknown) has no
client report: it is refused by name, never printed with a caveat. So is a run none of whose
numbers passed: a client report without numbers is not a report.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from aia_core.application.analysis_results import SourcesRefused, native_sources
from aia_core.application.report import RESEARCH_SUBTITLE
from aia_core.application.report_chapters import verified_map
from aia_core.application.report_design import compose_design_sections
from aia_core.application.report_export import review_stamp_record
from aia_core.application.report_maps import compose_map_sections
from aia_core.application.report_method import compose_method_section
from aia_core.application.report_tables import question_tables
from aia_core.application.research import ResearchRuns, research_artifacts
from aia_core.domain.analysis.native import native_evidence, native_items
from aia_core.domain.evidence import ClaimSurface, EvidenceTable
from aia_core.domain.evidence.claims import Disclosure
from aia_core.domain.evidence.report_lift import MODELLED_CLIENT_REPORT_LIFT
from aia_core.domain.evidence.validation import method_status
from aia_core.domain.fieldwork import MODELLED_DISCLOSURE, OriginKind, origin_kind
from aia_core.domain.pipeline import fingerprint
from aia_core.domain.report.evidence import EvidenceLedger
from aia_core.domain.report.model import (
    Callout,
    CalloutKind,
    Classification,
    EvidenceAppendix,
    Paragraph,
    ReportDocument,
    ReportKind,
    ReportMeta,
    Section,
    text,
)
from aia_core.domain.report.validation import require_valid
from aia_core.domain.scope import Permission, StudyContext
from aia_core.infrastructure.artifact_repository import Artifact, ArtifactRepository, ArtifactStatus
from aia_core.infrastructure.scope_repository import ScopeRepository
from aia_core.infrastructure.storage import ArtifactStore

CLIENT_REPORT_ARTIFACT_TYPE = "research_client_docx"
CLIENT_REPORT_CONTRACT = "aia-client-report-3"
CLIENT_REPORT_STAGE = "REPORT"


class ClientReportRefused(Exception):
    """This run has no client report, and why, in words a researcher can act on."""

    def __init__(self, reason: str, message: str) -> None:
        super().__init__(message)
        self.reason = reason


@dataclass(frozen=True, slots=True)
class ComposedClientReport:
    document: ReportDocument
    #: Everything the document was composed from: its stored artifact's fingerprint.
    sources: dict[str, Any]
    depends_on: tuple[str, ...]


def _with_scope(table: EvidenceTable) -> EvidenceTable:
    """The table with every row carrying the scope disclosure, because this report prints the
    scope with every table (who the respondents were, from which population, how many)."""
    rows = [
        dataclasses.replace(row, disclosures=frozenset({*row.disclosures, Disclosure.SCOPE}))
        for row in table.rows.values()
    ]
    built = EvidenceTable.build(rows)
    return EvidenceTable(rows=built.rows, suppressed=table.suppressed)


def compose_client_report(
    session: Session, scope: StudyContext, store: ArtifactStore, *, run_id: str
) -> ComposedClientReport:
    """The client report of ``run_id``. Raises :class:`ClientReportRefused` when it has none."""
    from aia_core.infrastructure.report_docx.object_map_figure import object_map_snapshots

    scope.require(Permission.EXPORT_DELIVERABLE)
    run = ResearchRuns(session, scope).get(run_id)
    try:
        sources = native_sources(session, scope, store, run)
    except SourcesRefused as exc:
        raise ClientReportRefused("sources_refused", f"{exc.reason}: {exc}") from exc
    origin = sources.dataset_origin
    if origin_kind(origin) is not OriginKind.MODELLED:
        raise ClientReportRefused(
            "not_modelled",
            "Klientská zpráva vzniká jen z běhu, v němž odpovídali AI respondenti sestavení "
            "z populace. Tento běh použil smyšlené respondenty nebo neznámý zdroj.",
        )
    evidence = native_evidence(
        sources.specification,
        sources.aggregate,
        dataset_sha256=sources.refs.dataset.sha256,
        origin=origin,
        support=sources.support.analysis,
        respondent_system=sources.respondent_system,
        joint_certificate=sources.joint_certificate,
        report_lift=MODELLED_CLIENT_REPORT_LIFT,
    )
    meta_run: Mapping[str, Any] = run.get("metadata") or {}
    population = (
        meta_run.get("population") if isinstance(meta_run.get("population"), Mapping) else None
    )
    label = (population or {}).get("version_label") or "neuvedená"
    # The scope every table prints (each also prints its base n): who answered, from where.
    scope_line = f"AI respondenti sestavení z populace {label}; {MODELLED_DISCLOSURE}"
    tables = question_tables(
        _with_scope(evidence.table),
        native_items(sources.specification),
        book=evidence.book,
        joint_status=evidence.joint_status,
        source=scope_line,
        surface=ClaimSurface.CLIENT_FACING,
    )
    if not tables.claims:
        reasons = sorted({r for _, why in tables.refused for r in why})
        raise ClientReportRefused(
            "nothing_admitted",
            "Žádné číslo tohoto běhu nesplnilo pravidla pro klienta: " + "; ".join(reasons[:5]),
        )

    mapped = verified_map(
        research_artifacts(session, scope, store),
        next(
            (
                (s.get("output") or {}).get("artifact_id")
                for s in run["steps"]
                if s["node_key"] == "sociomap"
            ),
            None,
        ),
        dataset_sha256=sources.refs.dataset.sha256,
        specification_fingerprint=sources.refs.specification_fingerprint,
    )
    maps = compose_map_sections(
        mapped.body, object_map_snapshots(mapped.body), source=scope_line, client=True
    )
    design = compose_design_sections(sources.specification, sources.research_questions)

    names = ScopeRepository(session)
    meta = ReportMeta(
        kind=ReportKind.CLIENT,
        title="Výzkumná zpráva",
        subtitle=RESEARCH_SUBTITLE[OriginKind.MODELLED],
        client_name=names.client_of_study(scope).name,
        study_name=names.get_study(scope).name,
        study_id=scope.study_id,
        issued_on=run["created_at"].date(),
        revision=int(run["project_revision"]),
        method_status=method_status(None, evidence.system_fingerprint),
        classification=Classification.CLIENT_CONFIDENTIAL,
        identifiers=(),
    )
    intro = Section(
        "Úvod",
        (
            Callout(
                CalloutKind.METHOD,
                text(
                    f"{MODELLED_CLIENT_REPORT_LIFT.reader_note} Každé číslo je označeno: "
                    f"{MODELLED_DISCLOSURE}."
                ),
                title="Jak číst tuto zprávu",
            ),
            Paragraph(
                text(
                    "Zpráva uvádí návrh studie, kdo odpovídal, výsledky jednotlivých otázek "
                    "a mapy hodnocených objektů. Uvádí jen čísla s dostatečnou oporou a vždy "
                    "s 95% intervalem."
                )
            ),
        ),
        id="ch-intro",
    )
    sections = [
        intro,
        design.chapter,
        compose_method_section(meta_run, origin, client=True),
        *tables.sections,
        *maps,
        design.appendix,
        Section("Evidenční příloha", (EvidenceAppendix(),), id="app-evidence", appendix=True),
    ]
    ledger = EvidenceLedger.from_claims(
        tables.claims, surface=ClaimSurface.CLIENT_FACING, table=_with_scope(evidence.table)
    )
    document = require_valid(ReportDocument(meta, tuple(sections), ledger))
    return ComposedClientReport(
        document=document,
        sources={
            "contract": CLIENT_REPORT_CONTRACT,
            "run_id": run_id,
            "lift": MODELLED_CLIENT_REPORT_LIFT.lift_id,
            "evidence": evidence.system_fingerprint,
            "table": evidence.table.fingerprint(),
            "sociomap": mapped.sha256,
            "client": meta.client_name,
            "study": meta.study_name,
            "issued_on": meta.issued_on.isoformat(),
            "claims": fingerprint(sorted(c.claim_id for c in tables.claims)),
        },
        depends_on=(
            sources.refs.specification.artifact_id,
            sources.refs.dataset.artifact_id,
            sources.refs.aggregate.artifact_id,
            mapped.artifact_id,
        ),
    )


def approved_client_report(
    artifacts: ArtifactRepository, run: Mapping[str, Any], *, run_id: str
) -> Artifact | None:
    """The newest valid client report of ``run`` a person approved, under any composition
    contract; ``None`` while none is. Found as itself on the run's project, never by the
    fingerprint of what composing would give today (D2: the approved version is exported)."""
    approved = [
        a
        for a in artifacts.list_for_stage(
            project_id=str(run["project_id"]),
            revision=int(run["project_revision"]),
            stage_type=CLIENT_REPORT_STAGE,
        )
        if a.artifact_type == CLIENT_REPORT_ARTIFACT_TYPE
        and a.status is ArtifactStatus.VALID
        and a.metadata.get("run_id") == run_id
        and a.is_approved
    ]
    return approved[-1] if approved else None


def stored_client_report(
    session: Session,
    scope: StudyContext,
    store: ArtifactStore,
    *,
    run_id: str,
    build: str = "",
) -> tuple[Artifact, bytes]:
    """The run's client report as a stored artifact, and its bytes.

    Once a person has approved one (B2, research-integrity-report D2), the newest valid
    approved version is the client report, whatever composition contract it was stored under:
    nothing is composed, so a later deploy that changes the contract, or what composition
    accepts, never replaces it with a new draft or refuses it. Until then it is composed from
    the run's verified sources every time, and rendered and stored as a draft only when no
    valid artifact has exactly those sources, so the document a person approves is the
    document they downloaded.
    """
    from aia_core.infrastructure.report_docx.renderer import DocxRenderer

    scope.require(Permission.EXPORT_DELIVERABLE)
    run = ResearchRuns(session, scope).get(run_id)
    artifacts = research_artifacts(session, scope, store)
    approved = approved_client_report(artifacts, run, run_id=run_id)
    if approved is not None:
        return approved, artifacts.read(approved.artifact_id)
    composed = compose_client_report(session, scope, store, run_id=run_id)
    key = fingerprint(composed.sources)
    found = artifacts.find_reusable(
        project_id=run["project_id"],
        stage_type=CLIENT_REPORT_STAGE,
        artifact_type=CLIENT_REPORT_ARTIFACT_TYPE,
        input_fingerprint=key,
    )
    if found is not None:
        return found, artifacts.read(found.artifact_id)
    data = DocxRenderer().render(composed.document)
    artifact, _created = artifacts.put(
        project_id=run["project_id"],
        revision=int(run["project_revision"]),
        stage_type=CLIENT_REPORT_STAGE,
        artifact_type=CLIENT_REPORT_ARTIFACT_TYPE,
        data=data,
        content_type=DocxRenderer.media_type,
        input_fingerprint=key,
        runtime_version=build,
        metadata={
            "run_id": run_id,
            "report_kind": ReportKind.CLIENT.value,
            "review_state": "DRAFT_UNAPPROVED",
            "data_origin": "MODELLED_AI_PANEL",
            "lift": MODELLED_CLIENT_REPORT_LIFT.lift_id,
            "report_contract": CLIENT_REPORT_CONTRACT,
            **review_stamp_record(data),
        },
        depends_on=list(composed.depends_on),
    )
    return artifact, data
