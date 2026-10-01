"""Compose a faithful internal report from a reconstructed research run.

The analysis reader rechecks stored drafts against the evidence gate before this
module sees them. Composition preserves their words and claim references; it
does not ask a model to invent a second interpretation of the results.
"""

from __future__ import annotations

from aia_core.application.analysis_results import RunAnalysis
from aia_core.domain.analysis import ANALYSIS_MODULES, AnalysisModuleId
from aia_core.domain.evidence import AdmittedClaim, ClaimSurface
from aia_core.domain.report.evidence import EvidenceLedger
from aia_core.domain.report.model import (
    AuditBlock,
    Block,
    Callout,
    CalloutKind,
    Classification,
    EvidenceAppendix,
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


def compose_internal_report(run: RunAnalysis, meta: ReportMeta) -> ReportDocument:
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
    sections: list[Section] = []
    audit = [("Běh", run.run_id), ("Evidence", table_fingerprint)]
    for spec in ANALYSIS_MODULES:
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
        blocks: list[Block] = [Paragraph(text(result.summary), ParagraphRole.LEDE)]
        if result.claims:
            blocks.append(
                Callout(
                    CalloutKind.NOTE,
                    text("Číselná tvrzení tohoto oddílu jsou doložena v evidenční příloze."),
                    refs=tuple(dict.fromkeys(c.row.evidence_ref for c in result.claims)),
                )
            )
        for answer in result.research_question_answers:
            blocks.append(Paragraph((Text(answer.question, "strong"), Text(" — " + answer.answer))))
            if answer.claim_ids:
                blocks.append(
                    Callout(
                        CalloutKind.NOTE,
                        text("Evidence k odpovědi."),
                        refs=tuple(by_claim[cid].row.evidence_ref for cid in answer.claim_ids),
                    )
                )
        for finding in result.key_findings:
            blocks.append(
                Callout(
                    CalloutKind.NOTE,
                    text(finding.text),
                    title="Zjištění",
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
        audit.append((spec.artifact_name, module.artifact_sha256))

    ledger = EvidenceLedger.from_claims(
        claims, surface=ClaimSurface.INTERNAL, table=reference.table
    )
    sections.append(
        Section("Evidenční příloha", (EvidenceAppendix(),), id="app-evidence", appendix=True)
    )
    sections.append(Section("Audit", (AuditBlock(tuple(audit)),), id="app-audit", appendix=True))
    return require_valid(ReportDocument(meta, tuple(sections), ledger))
