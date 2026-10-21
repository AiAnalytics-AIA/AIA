"""Compose a faithful internal report from a reconstructed research run.

The analysis reader rechecks stored drafts against the evidence gate before this
module sees them. Composition preserves their words and claim references; it
does not ask a model to invent a second interpretation of the results.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

from aia_core.application.analysis_results import RunAnalysis
from aia_core.application.report_design import DesignSections
from aia_core.application.report_tables import QuestionTables
from aia_core.domain.analysis import ANALYSIS_MODULES, AnalysisModuleId
from aia_core.domain.evidence import AdmittedClaim, ClaimSurface
from aia_core.domain.fieldwork import MODELLED_DISCLOSURE, OriginKind, origin_kind
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
# The stored DOCX rendered as PDF beside it (complete-study-report B3).
INTERNAL_REPORT_PDF_ARTIFACT_TYPE = "research_internal_pdf"
# The draft's document model beside its DOCX, under the same fingerprint (report-delivery RD5a):
# what the Zpráva pane reads and every later edit names a paragraph in.
INTERNAL_REPORT_DOCUMENT_ARTIFACT_TYPE = "research_internal_document"
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

#: A research report's subtitle, by the origin's kind: never plain "Výzkum" for answers no person
#: gave.
RESEARCH_SUBTITLE: dict[OriginKind, str] = {
    OriginKind.SIMULATED: "Syntetický výzkum",
    OriginKind.MODELLED: "Modelovaný výzkum",
    OriginKind.UNKNOWN: "Výzkum neznámého původu",
}

#: How the report frames its numbers, by the origin's kind (ADR 0024 §7); every kind says one.
_FRAME_TEXT: dict[OriginKind, str] = {
    OriginKind.SIMULATED: (
        "Odpovědi v této studii vytvořili syntetičtí respondenti. "
        "Výsledky popisují chování simulace, nikoli měření skutečných "
        "osob. Slouží k ověření postupu a návrhu dalšího výzkumu; "
        "závěry o reálném publiku vyžadují samostatné ověření."
    ),
    OriginKind.MODELLED: (
        f"Všechna čísla v této zprávě jsou {MODELLED_DISCLOSURE}. Odpovědi vytvořil model "
        "za respondenty sestavené z osob vybraných z populace běhu; nejde o měření ani "
        "o výpovědi skutečných respondentů. Nejistota se počítá z počtu podkladových osob."
    ),
    OriginKind.UNKNOWN: (
        "Původ dat této studie není znám. Výsledky nelze číst jako měření skutečných osob "
        "ani jako modelovaný odhad, dokud původ není doložen."
    ),
}
_LIMITATION_TEXT: dict[OriginKind, str] = {
    OriginKind.SIMULATED: (
        "Respondenti jsou syntetičtí. Tato studie není měřením skutečných osob."
    ),
    OriginKind.MODELLED: (
        f"Respondenti jsou {MODELLED_DISCLOSURE}. Tato studie není měřením skutečných osob."
    ),
    OriginKind.UNKNOWN: "Původ dat není znám. Tato studie není měřením skutečných osob.",
}


def _deviation_text(deviation: Mapping[str, Any]) -> str:
    """What a reader of the report must know about an aggregate that is not 18.6.6's port:
    the method it was computed under, every value it changed and every formula it replaced."""
    parts = [
        f"{c.get('path')} (18.6.6: {c.get('unit')}, zde {c.get('used')})"
        for c in deviation.get("changed") or []
        if isinstance(c, Mapping)
    ]
    formulas = [str(f) for f in deviation.get("replaced_formulas") or []]
    named = "; ".join(
        ([f"změněno: {', '.join(parts)}"] if parts else [])
        + ([f"nahrazené vzorce: {', '.join(formulas)}"] if formulas else [])
    )
    return (
        "Agregace v tomto běhu se odchyluje od přenosu 18.6.6: počítala podle metodiky "
        f"{deviation.get('methodology_version') or 'neuvedené verze'}"
        + (f" ({named})" if named else "")
        + ". Odhady a intervaly proto nejsou bez této výhrady srovnatelné s výsledky 18.6.6."
    )


def _folded(question: str) -> str:
    """A research question's text with its whitespace folded: how a gap the run recorded at
    start is matched to the question the analysis answered."""
    return " ".join(question.split())


def compose_internal_report(
    run: RunAnalysis,
    meta: ReportMeta,
    *,
    map_sections: tuple[Section, ...] = (),
    context_sections: tuple[Section, ...] = (),
    question_tables: QuestionTables | None = None,
    design: DesignSections | None = None,
    method: Section | None = None,
    research_question_gaps: Mapping[str, str] | None = None,
) -> ReportDocument:
    """Make an unapproved AIA-branded internal draft from all eight admitted modules.

    Caller supplies the Study-scoped ``reconstruct_run`` outcome and metadata.
    ``question_tables`` (``compose_question_tables``) follow the methodology chapter; their
    claims must be over this run's evidence table, admitted for the internal surface.
    ``design`` (``compose_design_sections``): its chapter follows the introduction and the
    questionnaire is an appendix before the evidence appendix. ``method``
    (``compose_method_section``): who answered and the run's methods, after the methodology.
    ``research_question_gaps`` (``research_question_gaps``): the research questions the run
    recorded at start as gaps, in words, by their text; the introduction's list and every answer
    to one of them say so where the answer is read.
    Client deliverables have a separate admission and review contract; this
    function never upgrades internal claims to a client-facing surface.
    """
    if meta.kind is not ReportKind.INTERNAL or meta.classification is not Classification.INTERNAL:
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
    kind = origin_kind(labels.data_origin)
    if meta.method_status != first.result.method_status:
        raise ReportCompositionRefused("report method status differs from analysis")

    gaps = {_folded(q): words for q, words in (research_question_gaps or {}).items()}
    marked: set[str] = set()
    gap_mark = " (bez doložené odpovědi" + (
        ", viz kapitola Respondenti a výpočet)" if method is not None else ")"
    )
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
                BulletList(
                    tuple(
                        ListItem(text(q + (gap_mark if _folded(q) in gaps else "")))
                        for q in reference.research_questions
                    )
                ),
            ]
        )
    if context_sections:
        introduction.append(
            Paragraph(
                text(
                    "Literární rešerše po odpovědích na výzkumné otázky vysvětluje dostupné "
                    "externí poznání, uvádí jeho zdroje a vymezuje jeho použitelnost. "
                    "Studijní výsledky a externí podklady mají oddělenou evidenci."
                )
            )
        )
    introduction.append(
        Callout(CalloutKind.LIMITATION, text(_FRAME_TEXT[kind]), title="Rámec interpretace")
    )
    deviation = run.aggregation_deviation
    if deviation is not None:
        introduction.append(
            Callout(
                CalloutKind.LIMITATION, text(_deviation_text(deviation)), title="Odchylka od 18.6.6"
            )
        )
    sections: list[Section] = [Section("Úvod a rámec studie", tuple(introduction), id="intro")]
    if design is not None:
        sections.append(design.chapter)
    audit = [("Běh", run.run_id), ("Evidence", table_fingerprint)]
    if deviation is not None:
        audit.append(("Metodika agregace", str(deviation.get("methodology_version") or "?")))
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
            sections.extend(context_sections)
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
                        *(
                            ()
                            if deviation is None
                            else (Paragraph(text(_deviation_text(deviation))),)
                        ),
                    ),
                    id="methodology",
                )
            )
            if method is not None:
                sections.append(method)
            if question_tables is not None:
                for claim in question_tables.claims:
                    if (
                        claim.surface is not ClaimSurface.INTERNAL
                        or reference.table.rows.get(claim.row.evidence_ref) != claim.row
                    ):
                        raise ReportCompositionRefused(
                            f"question table cites {claim.row.evidence_ref!r} outside run evidence"
                        )
                claims.extend(question_tables.claims)
                sections.extend(question_tables.sections)
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
            # Titles its answer: kept on the page with the qualification and answer below it.
            blocks.append(Paragraph((Text(answer.question, "strong"),), ParagraphRole.LEAD_IN))
            folded = _folded(answer.question)
            if folded in gaps and folded not in marked:
                # Why, once: at the first answer to it. Several modules answer the same
                # research questions, and the full callout under each repeated one reason up
                # to 16 times in the fictional render (research-integrity-report review 3).
                marked.add(folded)
                blocks.append(
                    Callout(
                        CalloutKind.LIMITATION,
                        # By what the record holds, never "no measure": a comparison gap's
                        # measures were answered, only the comparison was not shown (review 3).
                        text(
                            f"Při spuštění běh zaznamenal: {gaps[folded]}. Odpověď níže proto "
                            "čtěte jako nedoloženou; totéž platí pro každou další odpověď na "
                            "tuto otázku ve zprávě."
                        ),
                        title="Bez doložené odpovědi",
                    )
                )
            elif folded in gaps:
                blocks.append(
                    Callout(
                        CalloutKind.LIMITATION,
                        text(
                            "Ani tuto odpověď nečtěte jako doloženou (důvod je u první "
                            "odpovědi na tuto otázku)."
                        ),
                    )
                )
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
        if spec.module_id is AnalysisModuleId.LIMITATIONS:
            blocks.append(Callout(CalloutKind.LIMITATION, text(_LIMITATION_TEXT[kind])))
        if spec.module_id is AnalysisModuleId.LIMITATIONS and deviation is not None:
            blocks.append(
                Callout(
                    CalloutKind.LIMITATION,
                    text(
                        "Agregace se odchyluje od přenosu 18.6.6. Srovnání s výsledky 18.6.6 "
                        "platí jen s touto výhradou."
                    ),
                )
            )
        sections.append(Section(_TITLES[spec.module_id], tuple(blocks), id=f"ch-{spec.ordinal}"))
        if spec.module_id is AnalysisModuleId.OBJECTS:
            sections.extend(map_sections)
        audit.append((spec.artifact_name, module.artifact_sha256))

    ledger = EvidenceLedger.from_claims(
        claims, surface=ClaimSurface.INTERNAL, table=reference.table
    )
    if design is not None:
        sections.append(design.appendix)
    sections.append(
        Section("Evidenční příloha", (EvidenceAppendix(),), id="app-evidence", appendix=True)
    )
    sections.append(Section("Audit", (AuditBlock(tuple(audit)),), id="app-audit", appendix=True))
    sections[0] = _with_contents(sections[0], sections, literature=bool(context_sections))
    return require_valid(ReportDocument(meta, tuple(sections), ledger))


def _with_contents(intro: Section, sections: list[Section], *, literature: bool) -> Section:
    """The introduction with what this variant of the report holds (research-integrity-report
    chunk 3): a reader of a downloaded file -- DOCX or its PDF -- sees whether the literature
    review is in it and which chapters and appendices it has, without the screen it came from."""
    chapters = [s.title for s in sections[1:] if not s.appendix]
    appendices = [s.title for s in sections if s.appendix]
    variant = (
        "Tato varianta zprávy obsahuje literární rešerši vybranou k tomuto běhu."
        if literature
        else "Tato varianta je základní zprávou běhu: literární rešerše není její součástí. "
        "Zpráva s vybranou rešerší je samostatná varianta: vychází z týchž uložených výsledků "
        "běhu a navíc má kapitolu o literatuře."
    )
    contents: list[Block] = [
        Paragraph(text(f"{variant} Zpráva má tyto kapitoly:")),
        BulletList(tuple(ListItem(text(title)) for title in chapters)),
        Paragraph(
            text(
                "Přílohy: " + "; ".join(appendices) + "." if appendices else "Zpráva nemá přílohy."
            )
        ),
    ]
    blocks = (intro.blocks[0], *contents, *intro.blocks[1:])
    return Section(intro.title, blocks, id=intro.id, appendix=intro.appendix)
