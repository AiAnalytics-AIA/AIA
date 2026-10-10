"""Compose a faithful internal report from a reconstructed research run.

The analysis reader rechecks stored drafts against the evidence gate before this
module sees them. Composition preserves their words and claim references; it
does not ask a model to invent a second interpretation of the results.
"""

from __future__ import annotations

import re

from aia_core.application.analysis_results import RunAnalysis
from aia_core.domain.analysis import ANALYSIS_MODULES, AnalysisModuleId
from aia_core.domain.evidence import AdmittedClaim, ClaimSurface
from aia_core.domain.report.evidence import EvidenceLedger
from aia_core.domain.report.model import (
    AuditBlock,
    Block,
    BulletList,
    Callout,
    CalloutKind,
    Classification,
    EvidenceAppendix,
    Heading,
    ListItem,
    Paragraph,
    ParagraphRole,
    ReportDocument,
    ReportKind,
    ReportMeta,
    Section,
    Text,
    text,
)
from aia_core.domain.report.validation import require_valid

INTERNAL_REPORT_ARTIFACT_TYPE = "research_internal_docx"
INTERNAL_REPORT_MEDIA_TYPE = (
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
)


class ReportCompositionRefused(ValueError):
    """A report cannot be made from incomplete or inconsistent analysis."""


_TITLES = {
    AnalysisModuleId.EXECUTIVE: "Shrnutí pro vedení",
    AnalysisModuleId.RESEARCH_QUESTIONS: "Výzkumné otázky",
    AnalysisModuleId.OBJECTS: "Srovnání sledovaných objektů",
    AnalysisModuleId.AUDIENCE: "Cílová skupina",
    AnalysisModuleId.SEGMENTS: "Segmenty",
    AnalysisModuleId.HYPOTHESES: "Hypotézy",
    AnalysisModuleId.IMPLICATIONS: "Implikace pro rozhodnutí",
    AnalysisModuleId.LIMITATIONS: "Limity",
}


def compose_internal_report(
    run: RunAnalysis, meta: ReportMeta, *, map_sections: tuple[Section, ...] = ()
) -> ReportDocument:
    """Make an unapproved AIA-branded internal draft from all eight admitted modules.

    Caller supplies the Study-scoped ``reconstruct_run`` outcome and metadata.
    Client deliverables have a separate admission and review contract; this
    function never upgrades internal claims to a client-facing surface.
    """
    if (
        meta.kind is not ReportKind.INTERNAL
        or meta.classification is not Classification.INTERNAL
        or meta.approvals
    ):
        raise ReportCompositionRefused("composition makes an unapproved internal draft only")
    if not run.complete or set(run.modules) != set(AnalysisModuleId):
        raise ReportCompositionRefused("all eight analysis modules must be complete")

    first = run.modules[AnalysisModuleId.EXECUTIVE]
    if first.result is None:
        raise ReportCompositionRefused("executive result is missing")
    reference = first.inputs
    sources = first.record.sources.content()
    table_fingerprint = reference.table.fingerprint()
    labels = first.record.labels
    if meta.method_status != first.result.method_status:
        raise ReportCompositionRefused("report method status differs from analysis")

    claims: list[AdmittedClaim] = []
    introduction: list[Block] = [
        Paragraph(
            text(
                f"Tato zpráva představuje výsledky studie „{meta.study_name}“ pro "
                f"{meta.client_name}. Je určena k interní interpretaci a přípravě "
                "rozhodnutí. Výsledky vycházejí ze zmrazeného běhu studie; každý "
                "analytický oddíl zachovává přijatá zjištění a jejich evidenci."
            ),
            ParagraphRole.LEDE,
        ),
        Paragraph(
            text(
                "Nejprve si přečtěte shrnutí a odpovědi na výzkumné otázky. "
                "Metodika a popis publika vymezují, jak výsledky číst. Srovnání "
                "objektů, sociomapy a segmenty pak rozvíjejí "
                "kontext výsledků. Hypotézy a implikace pomáhají formulovat další "
                "kroky; jejich použitelnost posuzujte společně s oddílem limitů. "
                "Číselná tvrzení lze ověřit v evidenční příloze."
            )
        ),
    ]
    if reference.research_questions:
        introduction.extend(
            [
                Paragraph(text("Studie byla vedena následujícími výzkumnými otázkami:")),
                BulletList(tuple(ListItem(text(q)) for q in reference.research_questions)),
            ]
        )
    if labels.simulated_respondents:
        introduction.append(
            Callout(
                CalloutKind.LIMITATION,
                text(
                    "Odpovědi v této studii vytvořili syntetičtí respondenti. "
                    "Výsledky popisují chování simulace, nikoli měření skutečných "
                    "osob. Slouží k ověření postupu a návrhu dalšího výzkumu; "
                    "závěry o reálném publiku vyžadují samostatné ověření."
                ),
                title="Rámec interpretace",
            )
        )
    sections: list[Section] = [Section("Úvod a rámec studie", tuple(introduction), id="intro")]
    audit = [("Běh", run.run_id), ("Evidence", table_fingerprint)]
    # Put the population context before object-level findings; keep module IDs
    # and their admitted paragraphs intact rather than rewriting the evidence.
    order = (
        AnalysisModuleId.EXECUTIVE,
        AnalysisModuleId.RESEARCH_QUESTIONS,
        AnalysisModuleId.AUDIENCE,
        AnalysisModuleId.OBJECTS,
        AnalysisModuleId.SEGMENTS,
        AnalysisModuleId.HYPOTHESES,
        AnalysisModuleId.IMPLICATIONS,
        AnalysisModuleId.LIMITATIONS,
    )
    specs = {s.module_id: s for s in ANALYSIS_MODULES}
    for module_id in order:
        spec = specs[module_id]
        if module_id is AnalysisModuleId.AUDIENCE:
            sections.append(
                Section(
                    "Metodika a způsob interpretace",
                    (
                        Paragraph(
                            text(
                                "Analýza vychází ze společného souboru odpovědí a výzkumné "
                                "specifikace uložených pro tento běh studie. Jednotlivé kapitoly "
                                "proto čtou tutéž evidenci z různých hledisek: odpovídají na "
                                "výzkumné otázky, porovnávají objekty, popisují publikum a "
                                "zkoumají možné segmenty. Vzájemné rozdíly v důrazu je třeba "
                                "posuzovat v kontextu této společné datové základny."
                            )
                        ),
                        Paragraph(
                            text(
                                "Popisné výsledky, jejich interpretace a doporučení mají odlišnou "
                                "úlohu. Výsledek uvádí, co evidence podporuje; interpretace "
                                "vysvětluje jeho možné souvislosti a doporučení navrhuje další "
                                "postup. Doporučení samo o sobě není důkazem účinku a vztah mezi "
                                "dvěma charakteristikami neprokazuje příčinnou souvislost. "
                                "Před rozhodnutím je proto nutné číst závěry společně s limity."
                            )
                        ),
                        Paragraph(
                            text(
                                "Odkazy u tvrzení umožňují dohledat příslušné podklady v "
                                "evidenční příloze. Sociomapy doplňují slovní analýzu vizuálním "
                                "pohledem; vysvětlení jejich vzdáleností, výšky, kvality zobrazení "
                                "a omezení je uvedeno přímo v kapitole s mapami."
                                if map_sections
                                else "Odkazy u tvrzení umožňují dohledat příslušné podklady v "
                                "evidenční příloze. Ta slouží k ověření zjištění, zatímco "
                                "následující kapitoly rozvíjejí jejich věcný význam."
                            )
                        ),
                    ),
                    id="methodology",
                )
            )
        module = run.modules[spec.module_id]
        result = module.result
        if result is None or result.module_id is not spec.module_id:
            raise ReportCompositionRefused(f"{spec.module_id}: no admitted result")
        if (
            result.surface is not ClaimSurface.INTERNAL
            or module.record.surface is not ClaimSurface.INTERNAL
            or module.inputs.surface is not ClaimSurface.INTERNAL
        ):
            raise ReportCompositionRefused(f"{spec.module_id}: internal admission required")
        if (
            result.method_status != meta.method_status
            or result.input_fingerprint != module.record.input_fingerprint
            or module.inputs.table.fingerprint() != table_fingerprint
            or module.record.sources.content() != sources
            or module.inputs.research_questions != reference.research_questions
            or module.inputs.language != reference.language
            or module.inputs.system_fingerprint != reference.system_fingerprint
            or module.record.labels != labels
        ):
            raise ReportCompositionRefused(f"{spec.module_id}: analysis inputs disagree")
        by_claim = {claim.claim_id: claim for claim in result.claims}
        for claim in result.claims:
            if reference.table.rows.get(claim.row.evidence_ref) != claim.row:
                raise ReportCompositionRefused(f"{spec.module_id}: claim is outside run evidence")
        claims.extend(result.claims)
        # Analysis prose is body text. A lede is a short answer, not an entire
        # module summary promoted to display typography.
        refs = tuple(dict.fromkeys(c.row.evidence_ref for c in result.claims))
        blocks: list[Block] = [
            Paragraph(text(part.strip()), refs=refs)
            for part in re.split(r"\n\s*\n", result.summary)
            if part.strip()
        ]
        if result.research_question_answers:
            blocks.append(Heading("Odpovědi na výzkumné otázky", 2))
        for answer in result.research_question_answers:
            blocks.append(Paragraph((Text(answer.question, "strong"),)))
            blocks.extend(
                Paragraph(
                    text(part.strip()),
                    refs=tuple(by_claim[cid].row.evidence_ref for cid in answer.claim_ids),
                )
                for part in re.split(r"\n\s*\n", answer.answer)
                if part.strip()
            )
        if result.key_findings:
            blocks.append(Heading("Podstatná zjištění", 2))
        for finding in result.key_findings:
            blocks.append(
                Paragraph(
                    text(finding.text),
                    refs=tuple(by_claim[cid].row.evidence_ref for cid in finding.claim_ids),
                )
            )
        if spec.module_id is AnalysisModuleId.LIMITATIONS and labels.simulated_respondents:
            blocks.append(
                Callout(
                    CalloutKind.LIMITATION,
                    text("Respondenti jsou syntetičtí. Tento návrh není měřením skutečných osob."),
                )
            )
        sections.append(Section(_TITLES[spec.module_id], tuple(blocks), id=f"ch-{spec.ordinal}"))
        if spec.module_id is AnalysisModuleId.OBJECTS:
            sections.extend(map_sections)
        audit.append((spec.artifact_name, module.artifact_sha256))

    ledger = EvidenceLedger.from_claims(
        claims, surface=ClaimSurface.INTERNAL, table=reference.table
    )
    sections.append(
        Section("Evidenční příloha", (EvidenceAppendix(),), id="app-evidence", appendix=True)
    )
    sections.append(Section("Audit", (AuditBlock(tuple(audit)),), id="app-audit", appendix=True))
    return require_valid(ReportDocument(meta, tuple(sections), ledger))
