"""Read pinned interpretation research into a separate, unapproved study report.

No model calls, respondent context, or changes to frozen run outputs. External
citations have their own L labels; they never enter the respondent evidence ledger.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit

from sqlalchemy.orm import Session

from aia_core.application.analysis_results import reconstruct_run
from aia_core.application.deep_research import DeepResearchRuns
from aia_core.application.report import (
    RESEARCH_SUBTITLE,
    ReportCompositionRefused,
    compose_internal_report,
)
from aia_core.application.report_chapters import report_chapters
from aia_core.application.research import ResearchRuns, research_artifacts
from aia_core.domain.analysis import ANALYSIS_MODULES, AnalysisModuleId
from aia_core.domain.deep_research.bundle import EvidenceBundle
from aia_core.domain.deep_research.contracts import EvidenceOrigin
from aia_core.domain.deep_research.gaps import AcquisitionReason
from aia_core.domain.deep_research.integration import DeepResearchPurpose, InterpretationLineage
from aia_core.domain.fieldwork import origin_kind
from aia_core.domain.pipeline import fingerprint
from aia_core.domain.report.model import (
    Block,
    Classification,
    Heading,
    Inline,
    Link,
    Paragraph,
    ReportDocument,
    ReportKind,
    ReportMeta,
    Section,
    Text,
    text,
)
from aia_core.domain.scope import Permission, StudyContext
from aia_core.infrastructure.artifact_repository import Artifact
from aia_core.infrastructure.scope_repository import ScopeRepository
from aia_core.infrastructure.storage import ArtifactStore

CONTEXT_REPORT_CONTRACT = "aia-contextual-report-3"
# Stored beside the run's own report, on the Study's design project (ADR 0016).
CONTEXT_REPORT_ARTIFACT_TYPE = "research_internal_docx_with_research"
CONTEXT_REPORT_STAGE = "REPORT"
_ACQUISITION_REASONS = {
    AcquisitionReason.PAYWALL: "Zdroj vyžaduje placený přístup.",
    AcquisitionReason.LOGIN: "Zdroj vyžaduje přihlášení.",
    AcquisitionReason.NOT_PUBLIC: "Zdroj nebyl veřejně přístupný.",
    AcquisitionReason.NOT_FOUND: "Zdroj se nepodařilo nalézt.",
    AcquisitionReason.ROBOTS: "Pravidla webu neumožnila automatické získání zdroje.",
    AcquisitionReason.NOT_PURSUED: "Získání tohoto zdroje nebylo v tomto běhu dokončeno.",
}


def _web_url(url: str | None) -> str | None:
    if url:
        parsed = urlsplit(url)
        if parsed.scheme in {"https", "http"} and parsed.hostname and not parsed.username:
            return url
    return None


def literature_sections(bundle: EvidenceBundle, *, research_run_id: str) -> tuple[Section, ...]:
    """Publish accepted source claims; citation checks do not approve model inferences."""
    if not bundle.verify():
        raise ReportCompositionRefused("Deep Research bundle seal is invalid")
    accepted = {a.evidence.evidence_id: a for a in bundle.accepted}
    labels: dict[str, str] = {}
    sources: dict[str, tuple[str, str | None, str]] = {}
    snapshots = {s.snapshot_id: s for s in bundle.snapshots}
    for a in bundle.accepted:
        e = a.evidence
        snapshot = snapshots.get(e.source_ref)
        url = _web_url(e.source_url or (snapshot.final_url if snapshot else None))
        key = url or e.source_ref
        if key not in sources:
            label = f"L{len(sources) + 1}"
            retrieved = snapshot.retrieved_at.date().isoformat() if snapshot else "neuvedeno"
            sources[key] = (
                label,
                url,
                f"{e.source_title or e.source_ref}. Datum zdroje: {e.source_date or 'neuvedeno'}. "
                f"Získáno: {retrieved}.",
            )
        labels[e.evidence_id] = sources[key][0]

    def cited(value: str, ids: tuple[str, ...]) -> Paragraph:
        if not ids or any(i not in accepted for i in ids):
            raise ReportCompositionRefused("synthesis cites evidence outside its accepted bundle")
        content: list[Inline] = [Text(value + " ")]
        for label in dict.fromkeys(labels[i] for i in ids):
            url = next(s[1] for s in sources.values() if s[0] == label)
            content.append(Link(f"[{label}]", url) if url else Text(f"[{label}]"))
            content.append(Text(" "))
        return Paragraph(tuple(content))

    blocks: list[Block] = [
        Paragraph(
            text(
                "Tato kapitola doplňuje zmrazené výsledky studie o veřejné zdroje vyhledané "
                "nástrojem Deep Research. Jejím účelem je vysvětlit širší souvislosti, doložit "
                "dostupné poznatky a identifikovat otázky, které vyžadují další výzkum. "
                "Jde o cílenou rešerši dostupné evidence, nikoli o systematický přehled veškeré "
                "akademické literatury. Externí zjištění nejsou odpověďmi respondentů této studie."
            )
        ),
        Paragraph(
            text(
                "Rešerše vychází z výzkumného cíle a témat uložených u vybraného výsledku. "
                "Zjištění prošla kontrolou citované pasáže a zdroje; neověřené nebo odmítnuté "
                "návrhy do této kapitoly nevstupují. Odkazy L označují externí literaturu "
                "a jsou oddělené od evidence samotné studie."
            )
        ),
    ]
    if EvidenceOrigin.RECORDED_FIXTURE in bundle.origins:
        blocks.append(
            Paragraph(
                text(
                    "Část podkladů pochází z nahraných testovacích výměn. Tato rešerše proto "
                    "dokládá funkci systému a nesmí být vydávána za aktuální živý výzkum."
                )
            )
        )
    synthesis = bundle.synthesis.check if bundle.synthesis else None
    if synthesis:
        # Preserve the foreign-citation refusal, even though proposed prose is omitted.
        for finding in synthesis.findings:
            if not finding.evidence_ids or any(i not in accepted for i in finding.evidence_ids):
                raise ReportCompositionRefused(
                    "synthesis cites evidence outside its accepted bundle"
                )
        blocks.append(
            Paragraph(
                text(
                    "Automatický návrh syntézy prošel kontrolou citací a čísel, nikoli "
                    "schválením věcné platnosti všech interpretací. Do této kapitoly proto "
                    "vstupují přijatá zjištění ze zdrojů; generované závěry a důvody mezer "
                    "zůstávají odděleným pracovním návrhem. Historický původ metody ani "
                    "nenalezený zdroj sám neprokazuje její vhodnost či nevhodnost pro jiný účel."
                )
            )
        )
    for index, subject in enumerate(bundle.subjects, 1):
        blocks.append(Heading(f"Téma rešerše {index}", 2))
        blocks.append(Paragraph(text(subject.text)))
    if not accepted:
        blocks.append(
            Paragraph(
                text(
                    "Rešerše nepřinesla žádné přijaté zjištění. Literatura ani benchmarky "
                    "proto zatím neposkytují oporu pro interpretaci výsledků; před rozhodnutím "
                    "je nutné doplnit zdroje a rešerši znovu ověřit."
                )
            )
        )
    elif not synthesis or not synthesis.findings:
        blocks.append(
            Paragraph(
                text(
                    "Souvislá syntéza nebyla přijata. Níže jsou uvedena jednotlivá ověřená "
                    "zjištění, která lze použít jako podklady pro další interpretaci."
                )
            )
        )

    if accepted:
        blocks.append(Heading("Ověřené podklady a číselné údaje", 2))
        has_numeric_data = any(
            measure.unit or measure.measure_name
            for a in bundle.accepted
            for measure in a.evidence.measures
        )
        for a in bundle.accepted:
            e = a.evidence
            blocks.append(cited(e.claim, (e.evidence_id,)))
            # Numeric metadata may capture just the first year of a range. Keep
            # numbers with the accepted claim's full scope instead of reconstructing
            # an independently unverified indicator or period from those fields.
        if not has_numeric_data:
            blocks.append(
                Paragraph(
                    text(
                        "Přijaté zdroje neobsahují strukturovaný číselný benchmark. "
                        "Z dostupné literatury proto nelze odvozovat referenční hodnotu ani "
                        "číselný rozdíl vůči výsledkům této studie."
                    )
                )
            )

    blocks.extend(
        [
            Heading("Význam pro interpretaci studie", 2),
            Paragraph(
                text(
                    "Při čtení výsledků posuzujte, zda se zde citovaný poznatek vztahuje "
                    "ke stejnému jevu, populaci a výzkumné otázce. Výskyt sledovaného jevu, "
                    "chování, postoje a hodnocení představují odlišné ukazatele. "
                    "Externí kontext pomáhá formulovat vysvětlení a následné otázky; sám "
                    "neprokazuje příčinu zjištěného vztahu ani účinek navrženého opatření."
                )
            ),
            Paragraph(
                text(
                    "Před číselným porovnáním je nutné ověřit shodu definice ukazatele, "
                    "jednotky, období, geografie, populace a jmenovatele. Chybějící údaj "
                    "není důkazem srovnatelnosti. Syntetické odpovědi nelze použít jako "
                    "odhad reálné populace. Rešerše nemění uložené odpovědi, analytická "
                    "zjištění ani výpočet vzdáleností a výšek sociomap."
                )
            ),
            Heading("Pokrytí a omezení rešerše", 2),
            Paragraph(
                text(
                    f"Stav evidence: {bundle.quality_status.value}. Přijatá zjištění: "
                    f"{len(bundle.accepted)}; zachycené zdroje: {len(bundle.snapshots)}; "
                    f"odmítnutá zjištění: {len(bundle.quarantined)}. "
                    "Počet zdrojů sám o sobě nevypovídá o úplnosti ani kvalitě přehledu."
                )
            ),
        ]
    )
    shown_limits: set[str] = set()

    def add_limit(value: str) -> None:
        # The checked synthesis and brief may state the same gap with different punctuation.
        key = re.sub(r"[\W_]+", " ", value.casefold()).strip()
        if key not in shown_limits:
            shown_limits.add(key)
            blocks.append(Paragraph(text(value)))

    brief = bundle.synthesis.brief if bundle.synthesis else None
    if brief:
        for gap in brief.gaps:
            # A search gap's model-authored reason can contain the same unsupported
            # inference as a summary. Report the unmet need, not that inference.
            add_limit(f"V tomto běhu nebyl doložen požadovaný podklad: {gap.need}.")
        if brief.acquisition_gaps:
            blocks.append(Heading("Podklady pro doplnění rešerše", 2))
            for acquisition in brief.acquisition_gaps:
                title = "Další nedostupný zdroj" if acquisition.text_withheld else acquisition.title
                add_limit(
                    f"{title}. {_ACQUISITION_REASONS[acquisition.reason]} "
                    f"{acquisition.how_to_obtain}"
                )
    blocks.append(Heading("Literatura a zdroje", 2))
    blocks.extend(
        Paragraph(
            (Text(f"[{label}] {description} "), Link(url, url))
            if url
            else text(f"[{label}] {description}")
        )
        for label, url, description in sources.values()
    )
    blocks.append(
        Paragraph(
            text(
                f"Deep Research: {research_run_id}. Otisk ověřeného balíčku: {bundle.sha256}. "
                "Tato kapitola je součástí interního neschváleného návrhu zprávy."
            )
        )
    )
    return (Section("Literární rešerše a externí kontext", tuple(blocks), id="literature"),)


@dataclass(frozen=True, slots=True)
class _Composed:
    """A composed report with literature and every source it was composed from."""

    document: ReportDocument
    run: Mapping[str, Any]
    sources: dict[str, Any]
    depends_on: tuple[str, ...]


def contextual_report(
    session: Session,
    scope: StudyContext,
    store: ArtifactStore,
    *,
    run_id: str,
    deep_research_run_id: str,
) -> ReportDocument:
    """Resolve both owned runs, verify their exact lineage and compose the document."""
    return _compose(
        session, scope, store, run_id=run_id, deep_research_run_id=deep_research_run_id
    ).document


def stored_contextual_report(
    session: Session,
    scope: StudyContext,
    store: ArtifactStore,
    *,
    run_id: str,
    deep_research_run_id: str,
    build: str = "",
) -> tuple[Artifact, bytes]:
    """The report with literature as a stored, unapproved draft artifact, and its bytes.

    Composed from the same verified sources every time; rendered and stored only when
    no valid artifact exists for exactly those sources. A later download of the same
    pair reads the stored bytes, and a person can approve that artifact (B2) -- a
    document rendered afresh on each download could never be the one approved.
    """
    from aia_core.infrastructure.report_docx.renderer import DocxRenderer

    composed = _compose(
        session, scope, store, run_id=run_id, deep_research_run_id=deep_research_run_id
    )
    artifacts = research_artifacts(session, scope, store)
    key = fingerprint(composed.sources)
    found = artifacts.find_reusable(
        project_id=composed.run["project_id"],
        stage_type=CONTEXT_REPORT_STAGE,
        artifact_type=CONTEXT_REPORT_ARTIFACT_TYPE,
        input_fingerprint=key,
    )
    if found is not None:
        return found, artifacts.read(found.artifact_id)
    data = DocxRenderer().render(composed.document)
    artifact, _created = artifacts.put(
        project_id=composed.run["project_id"],
        revision=int(composed.run["project_revision"]),
        stage_type=CONTEXT_REPORT_STAGE,
        artifact_type=CONTEXT_REPORT_ARTIFACT_TYPE,
        data=data,
        content_type=DocxRenderer.media_type,
        input_fingerprint=key,
        runtime_version=build,
        metadata={
            "run_id": run_id,
            "deep_research_run_id": deep_research_run_id,
            "report_kind": ReportKind.INTERNAL.value,
            "review_state": "DRAFT_UNAPPROVED",
            "report_contract": CONTEXT_REPORT_CONTRACT,
            "evidence_bundle_sha256": composed.sources["bundle"],
        },
        depends_on=list(composed.depends_on),
    )
    return artifact, data


def _compose(
    session: Session,
    scope: StudyContext,
    store: ArtifactStore,
    *,
    run_id: str,
    deep_research_run_id: str,
) -> _Composed:

    scope.require(Permission.EDIT_STUDY)
    run = ResearchRuns(session, scope).get(run_id)
    service = DeepResearchRuns(session, scope)
    deep_run = service.get(deep_research_run_id)
    if str(deep_run["status"]) != "COMPLETED":
        raise ReportCompositionRefused("Deep Research must be completed before export")
    provenance = service.provenance(deep_research_run_id, store=store)
    lineage = service.resolve_lineage(deep_research_run_id, store=store)
    if (
        provenance.purpose is not DeepResearchPurpose.INTERPRETATION_RESEARCH
        or not isinstance(lineage, InterpretationLineage)
        or lineage.research_run_id != run_id
        or lineage.design.design_revision_id != run["metadata"]["design_revision_id"]
    ):
        raise ReportCompositionRefused("Deep Research does not interpret this research run")
    bundle = service.bundle(deep_research_run_id, store=store)
    if (
        bundle.design_revision_id != lineage.design.design_revision_id
        or bundle.design_revision != lineage.design.design_revision
    ):
        raise ReportCompositionRefused("Deep Research bundle has different design lineage")
    analysis = reconstruct_run(session, scope, store, run_id=run_id)
    first = analysis.modules[AnalysisModuleId.EXECUTIVE]
    if first.result is None:
        raise ReportCompositionRefused("executive analysis is incomplete")
    # The same run-derived chapters as the stored internal report (complete-study-report B1d).
    chapters = report_chapters(
        research_artifacts(session, scope, store),
        run,
        analysis,
        map_artifact_id=next(
            (
                (s.get("output") or {}).get("artifact_id")
                for s in run["steps"]
                if s["node_key"] == "sociomap"
            ),
            None,
        ),
        run_id=run_id,
    )
    names = ScopeRepository(session)
    meta = ReportMeta(
        kind=ReportKind.INTERNAL,
        title="Výzkumná zpráva s literární rešerší",
        subtitle=RESEARCH_SUBTITLE[origin_kind(first.record.labels.data_origin)],
        client_name=names.client_of_study(scope).name,
        study_name=names.get_study(scope).name,
        study_id=scope.study_id,
        issued_on=deep_run["created_at"].date(),
        revision=lineage.design.design_revision,
        method_status=first.result.method_status,
        classification=Classification.INTERNAL,
        identifiers=(
            ("Běh", run_id),
            ("Deep Research", deep_research_run_id),
            ("Balíček", provenance.evidence_bundle_artifact_sha256),
            ("Kontrakt", CONTEXT_REPORT_CONTRACT),
        ),
    )
    document = compose_internal_report(
        analysis,
        meta,
        map_sections=chapters.maps,
        context_sections=literature_sections(bundle, research_run_id=deep_research_run_id),
        question_tables=chapters.questions,
        design=chapters.design,
        method=chapters.method,
    )
    modules = [analysis.modules[m.module_id] for m in ANALYSIS_MODULES]
    return _Composed(
        document=document,
        run=run,
        sources={
            "contract": CONTEXT_REPORT_CONTRACT,
            "run_id": run_id,
            "deep_research_run_id": deep_research_run_id,
            "analysis": [m.artifact_sha256 for m in modules],
            "sociomap": chapters.map_sha256,
            "bundle": provenance.evidence_bundle_artifact_sha256,
            "title": meta.title,
            "subtitle": meta.subtitle,
            "client": meta.client_name,
            "study": meta.study_name,
            "issued_on": meta.issued_on.isoformat(),
        },
        depends_on=(*(m.artifact_id for m in modules), chapters.map_artifact_id),
    )
