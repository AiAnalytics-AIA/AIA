"""The report templates: client, final, internal and study documentation (pure).

A template is a recipe: it takes typed content — what the analysis modules
wrote, as prose and blocks that cite evidence refs — and composes it into a
:class:`ReportDocument` in a fixed section order, adding the furniture the rules
demand (the method-status callout, the evidence key, the evidence appendix).
It decides structure, never numbers, and never formatting.

The client report follows the legacy deliverable's section order
(``legacy/npc-panel-18.6.6/app/client_report_v2.py:149-158``): executive
summary, the decision answer, research questions, findings, recommendations,
external evidence, confidence, method, limitations, conclusion. The final
report adds the external triangulation and the effective sample support
(legacy ``final_client_report.py``). The internal report is the client report
plus the audit, for the team only. The study documentation is the method.

Where the composed content comes from — ``AnalysisModuleResult`` and its
provenance — is R10, agreed with analysis-governance; these recipes take the
content already shaped.
"""

from __future__ import annotations

from dataclasses import dataclass

from aia_core.domain.report.copy import t
from aia_core.domain.report.evidence import EvidenceLedger
from aia_core.domain.report.model import (
    AuditBlock,
    Block,
    BulletList,
    Callout,
    CalloutKind,
    Column,
    EvidenceAppendix,
    EvidenceKey,
    Inline,
    KeyFinding,
    KpiRow,
    ListItem,
    Paragraph,
    ParagraphRole,
    Recommendation,
    ReportDocument,
    ReportKind,
    ReportMeta,
    Section,
    Table,
    TableRow,
    TextCell,
    text,
)


@dataclass(frozen=True, slots=True)
class QuestionAnswer:
    """Legacy ``research_question_answers``: the question, the answer, how strong."""

    question: str
    answer: str
    evidence_strength: str


@dataclass(frozen=True, slots=True)
class ReportContent:
    """What the analysis wrote for a client deliverable (legacy client report fields).

    Prose is inline content: it may cite values (``Value``) but holds no number
    of its own. ``exhibits`` are the figures, tables and KPI rows that illustrate
    the findings, in the order they are printed.
    """

    executive_summary: tuple[Inline, ...]
    decision_answer: tuple[Inline, ...]
    question_answers: tuple[QuestionAnswer, ...]
    key_findings: tuple[KeyFinding, ...]
    implications: tuple[Recommendation, ...]
    validation_summary: tuple[Inline, ...]
    confidence_summary: tuple[Inline, ...]
    method_summary: tuple[Inline, ...]
    limitations: tuple[str, ...]
    closing: tuple[Inline, ...]
    decision_refs: tuple[str, ...] = ()
    headline_kpis: KpiRow | None = None
    exhibits: tuple[Block, ...] = ()
    #: Questionnaire, glossary and the like, lettered after the chapters.
    appendices: tuple[Section, ...] = ()


@dataclass(frozen=True, slots=True)
class FinalContent:
    """What the final report adds: external triangulation and effective support."""

    triangulation: tuple[Block, ...]
    support: Table


@dataclass(frozen=True, slots=True)
class DocumentationContent:
    """The study's method documentation."""

    purpose: tuple[Inline, ...]
    design: tuple[Block, ...]
    population: tuple[Block, ...]
    support: Table
    method: tuple[Block, ...]
    limitations: tuple[str, ...]
    appendices: tuple[Section, ...] = ()


def _require_kind(meta: ReportMeta, kind: ReportKind) -> None:
    if meta.kind is not kind:
        raise ValueError(f"this template makes a {kind} report, not {meta.kind}")


def _method_callout() -> Callout:
    """The method status on the page, plainly. The renderer writes its words."""
    return Callout(CalloutKind.METHOD, ())


def _questions_table(meta: ReportMeta, answers: tuple[QuestionAnswer, ...]) -> Table:
    return Table(
        "tab-research-questions",
        t("tpl_questions_table"),
        (Column(t("tpl_question")), Column(t("tpl_answer")), Column(t("tpl_strength"))),
        tuple(
            TableRow((TextCell(a.question), TextCell(a.answer), TextCell(a.evidence_strength)))
            for a in answers
        ),
        t("tpl_source_analysis").format(study=meta.study_name),
    )


def _limitations(items: tuple[str, ...]) -> Block:
    return BulletList(tuple(ListItem(text(item)) for item in items))


def _client_sections(meta: ReportMeta, c: ReportContent) -> list[Section]:
    summary: list[Block] = [Paragraph(c.executive_summary, ParagraphRole.LEDE), _method_callout()]
    if c.headline_kpis is not None:
        summary.append(c.headline_kpis)
    return [
        Section(t("tpl_executive_summary"), tuple(summary), id="ch-summary"),
        Section(
            t("decision_answer"),
            (Callout(CalloutKind.DECISION, c.decision_answer, refs=c.decision_refs),),
            id="ch-decision",
        ),
        Section(
            t("tpl_research_questions"),
            (_questions_table(meta, c.question_answers),),
            id="ch-questions",
        ),
        Section(t("tpl_findings"), (*c.key_findings, *c.exhibits), id="ch-findings"),
        Section(t("tpl_recommendations"), c.implications, id="ch-recommendations"),
        Section(t("tpl_external_evidence"), (Paragraph(c.validation_summary),), id="ch-external"),
        Section(
            t("tpl_confidence"),
            (Paragraph(c.confidence_summary), EvidenceKey()),
            id="ch-confidence",
        ),
        Section(t("tpl_method"), (Paragraph(c.method_summary),), id="ch-method"),
        Section(t("tpl_limitations"), (_limitations(c.limitations),), id="ch-limitations"),
        Section(t("tpl_conclusion"), (Paragraph(c.closing),), id="ch-conclusion"),
    ]


def _evidence_appendix() -> Section:
    return Section(t("evidence_appendix"), (EvidenceAppendix(),), id="app-evidence", appendix=True)


def client_report(
    meta: ReportMeta, content: ReportContent, ledger: EvidenceLedger
) -> ReportDocument:
    """The client deliverable, in the legacy section order."""
    _require_kind(meta, ReportKind.CLIENT)
    sections = [*_client_sections(meta, content), *content.appendices, _evidence_appendix()]
    return ReportDocument(meta, tuple(sections), ledger)


def final_report(
    meta: ReportMeta, content: ReportContent, final: FinalContent, ledger: EvidenceLedger
) -> ReportDocument:
    """The client report with external triangulation and the effective sample support."""
    _require_kind(meta, ReportKind.FINAL)
    sections = _client_sections(meta, content)
    at = next(i for i, s in enumerate(sections) if s.id == "ch-external") + 1
    sections[at:at] = [
        Section(t("tpl_triangulation"), final.triangulation, id="ch-triangulation"),
        Section(t("tpl_support"), (final.support,), id="ch-support"),
    ]
    sections += [*content.appendices, _evidence_appendix()]
    return ReportDocument(meta, tuple(sections), ledger)


def internal_report(
    meta: ReportMeta,
    content: ReportContent,
    audit: tuple[tuple[str, str], ...],
    ledger: EvidenceLedger,
) -> ReportDocument:
    """The client report for the team: identifiers on the control page, and the audit."""
    _require_kind(meta, ReportKind.INTERNAL)
    sections = [
        *_client_sections(meta, content),
        *content.appendices,
        _evidence_appendix(),
        Section(t("audit"), (AuditBlock(audit),), id="app-audit", appendix=True),
    ]
    return ReportDocument(meta, tuple(sections), ledger)


def study_documentation(
    meta: ReportMeta,
    content: DocumentationContent,
    audit: tuple[tuple[str, str], ...],
    ledger: EvidenceLedger,
) -> ReportDocument:
    """How the study was done: purpose, design, population, support, method, limits."""
    _require_kind(meta, ReportKind.DOCUMENTATION)
    sections = [
        Section(
            t("tpl_purpose"),
            (Paragraph(content.purpose, ParagraphRole.LEDE), _method_callout()),
            id="ch-purpose",
        ),
        Section(t("tpl_design"), content.design, id="ch-design"),
        Section(t("tpl_population"), content.population, id="ch-population"),
        Section(t("tpl_support"), (content.support,), id="ch-support"),
        Section(t("tpl_method"), (*content.method, EvidenceKey()), id="ch-method"),
        Section(t("tpl_limitations"), (_limitations(content.limitations),), id="ch-limitations"),
        *content.appendices,
        _evidence_appendix(),
        Section(t("audit"), (AuditBlock(audit),), id="app-audit", appendix=True),
    ]
    return ReportDocument(meta, tuple(sections), ledger, list_of_figures=False)
