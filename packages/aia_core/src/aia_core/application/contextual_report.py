"""Read pinned interpretation research into a separate, unapproved study report.

No model calls, respondent context, or changes to frozen run outputs. External
citations have their own L labels; they never enter the respondent evidence ledger.
"""

from __future__ import annotations

import re
from urllib.parse import urlsplit

from sqlalchemy.orm import Session

from aia_core.application.analysis_results import reconstruct_run
from aia_core.application.deep_research import DeepResearchRuns
from aia_core.application.report import ReportCompositionRefused, compose_internal_report
from aia_core.application.report_maps import compose_map_sections
from aia_core.application.research import ResearchRuns, research_artifacts
from aia_core.domain.analysis import AnalysisModuleId
from aia_core.domain.deep_research.bundle import EvidenceBundle
from aia_core.domain.deep_research.contracts import EvidenceOrigin
from aia_core.domain.deep_research.gaps import AcquisitionReason
from aia_core.domain.deep_research.integration import DeepResearchPurpose, InterpretationLineage
from aia_core.domain.deep_research.measures import render_measure
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
from aia_core.infrastructure.artifact_repository import ArtifactStatus
from aia_core.infrastructure.scope_repository import ScopeRepository
from aia_core.infrastructure.storage import ArtifactStore

CONTEXT_REPORT_CONTRACT = "aia-contextual-report-1"
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
    """Publish accepted findings and checked synthesis, including incomplete coverage."""
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
        ids = tuple(i for f in synthesis.findings for i in f.evidence_ids)
        if synthesis.summary and ids:
            blocks.extend([Heading("Souhrn dostupného poznání", 2), cited(synthesis.summary, ids)])
        for index, subject in enumerate(bundle.subjects, 1):
            findings = [f for f in synthesis.findings if f.subject_key == subject.key]
            if findings:
                blocks.append(Heading(f"Téma rešerše {index}", 2))
                blocks.append(Paragraph(text(subject.text)))
                blocks.extend(cited(f.text, f.evidence_ids) for f in findings)
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
        has_numeric_data = False
        for a in bundle.accepted:
            e = a.evidence
            blocks.append(cited(e.claim, (e.evidence_id,)))
            for measure in e.measures:
                # A grounding measure may be an unlabelled historical year.
                # Its meaning remains in the claim, not a standalone benchmark.
                if not (measure.unit or measure.measure_name):
                    continue
                phrase = render_measure(measure)
                if phrase:
                    has_numeric_data = True
                    if measure.measure_name:
                        phrase = f"{measure.measure_name}: {phrase}"
                    blocks.append(cited(phrase, (e.evidence_id,)))
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

    if synthesis:
        for value in (*synthesis.gaps, *synthesis.limitations):
            add_limit(value)
        if synthesis.summary_withheld or synthesis.excluded:
            blocks.append(
                Paragraph(
                    text(
                        "Část navržené syntézy byla odmítnuta při ověřování. Její text není "
                        "součástí zprávy; přijaté podklady je třeba číst s tímto omezením."
                    )
                )
            )
    brief = bundle.synthesis.brief if bundle.synthesis else None
    if brief:
        for gap in brief.gaps:
            add_limit(f"{gap.need} {gap.reason}")
        if brief.acquisition_gaps:
            blocks.append(Heading("Podklady pro doplnění rešerše", 2))
            for acquisition in brief.acquisition_gaps:
                add_limit(
                    f"{acquisition.title}. {_ACQUISITION_REASONS[acquisition.reason]} "
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


def contextual_report(
    session: Session,
    scope: StudyContext,
    store: ArtifactStore,
    *,
    run_id: str,
    deep_research_run_id: str,
) -> ReportDocument:
    """Resolve both owned runs, verify their exact lineage and compose fresh bytes."""
    from aia_core.infrastructure.report_docx.object_map_figure import object_map_snapshots

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
    repo = research_artifacts(session, scope, store)
    map_id = next(
        (
            (s.get("output") or {}).get("artifact_id")
            for s in run["steps"]
            if s["node_key"] == "sociomap"
        ),
        None,
    )
    if not map_id:
        raise ReportCompositionRefused("the run has no frozen sociomap")
    map_source = repo.get(map_id)
    deps = repo.dependencies(map_id)
    if (
        map_source.artifact_type != "research_sociomap"
        or map_source.status is not ArtifactStatus.VALID
        or not any(d.sha256 == first.record.sources.dataset.sha256 for d in deps)
        or not any(
            d.artifact_type == "research_specification"
            and repo.read_json(d.artifact_id).get("specification_fingerprint")
            == first.record.sources.specification_fingerprint
            for d in deps
        )
    ):
        raise ReportCompositionRefused("sociomap does not belong to the frozen analysis inputs")
    body = repo.read_json(map_id)["sociomap"]
    maps = compose_map_sections(
        body, object_map_snapshots(body), source=f"Běh {run_id}; SHA-256 {map_source.sha256}"
    )
    names = ScopeRepository(session)
    meta = ReportMeta(
        kind=ReportKind.INTERNAL,
        title="Výzkumná zpráva s literární rešerší",
        subtitle="Syntetický výzkum" if first.record.labels.simulated_respondents else "Výzkum",
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
    return compose_internal_report(
        analysis,
        meta,
        map_sections=maps,
        context_sections=literature_sections(bundle, research_run_id=deep_research_run_id),
    )
