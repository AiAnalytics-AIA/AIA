"""What each section of a report was composed from: the section-source manifest (pure).

Artifact-chain CHN1. Every section names its sources -- a stored artifact by id and SHA-256, a
field of the run's specification, a field the run recorded at start, the evidence refs it prints,
or, for the methodology's reading guidance alone, text the composer wrote -- and the manifest names
the run's outputs no section read, so a reader of the draft can see what it stands on and what it
left out.

The evidence refs are never declared by a composer: they are what the section's blocks print
(:func:`~aia_core.domain.report.validation.section_refs`), and the evidence appendix's are every
ref the document prints. A composer that gives a :class:`LedgerSource` of its own keeps it.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any

from aia_core.domain.report.model import (
    ArtifactSource,
    AuditBlock,
    BesideOutput,
    EvidenceAppendix,
    FixedSource,
    LedgerSource,
    ReportDocument,
    RunOutput,
    RunSource,
    SectionSource,
    SpecSource,
)
from aia_core.domain.report.validation import cited_refs, section_refs

#: The audit section's id: the manifest is printed there.
AUDIT_SECTION_ID = "app-audit"


@dataclass(frozen=True, slots=True)
class SectionSources:
    """One section's sources, by the section's id."""

    section_id: str
    title: str
    sources: tuple[SectionSource, ...]


@dataclass(frozen=True, slots=True)
class ReportSources:
    """The manifest: every section's sources, and the run's outputs no section read (a stored
    one by id and SHA-256, one made beside the report by its step)."""

    sections: tuple[SectionSources, ...]
    unread: tuple[RunOutput, ...]


def report_sources(document: ReportDocument) -> ReportSources:
    """``document``'s manifest. A section's id is its composer's, else ``section-<n>``."""
    everything = cited_refs(document)
    sections = []
    for index, section in enumerate(document.sections, start=1):
        sources = list(section.sources)
        if not any(isinstance(s, LedgerSource) for s in sources):
            appendix = any(isinstance(b, EvidenceAppendix) for b in section.blocks)
            refs = everything if appendix else section_refs(section, document.ledger)
            if refs:
                sources.append(LedgerSource(refs))
        sections.append(
            SectionSources(section.id or f"section-{index}", section.title, tuple(sources))
        )
    # The audit lists the run's artifacts; it composes nothing from them, so it is no reader.
    read = {
        (s.artifact_id, s.sha256)
        for entry in sections
        if entry.section_id != AUDIT_SECTION_ID
        for s in entry.sources
        if isinstance(s, ArtifactSource)
    }
    unread = tuple(
        o
        for o in document.outputs
        if isinstance(o, BesideOutput) or (o.artifact_id, o.sha256) not in read
    )
    return ReportSources(tuple(sections), unread)


def source_payload(source: SectionSource | BesideOutput, *, client: bool = False) -> dict[str, Any]:
    """``source`` as stored with the document model. A client deliverable's keeps an artifact's
    type and drops its id and SHA-256, as its document drops the run's identifiers."""
    if isinstance(source, ArtifactSource):
        named = {} if client else {"artifact_id": source.artifact_id, "sha256": source.sha256}
        return {"kind": "artifact", "artifact_type": source.artifact_type, **named}
    if isinstance(source, BesideOutput):
        return {"kind": "beside", "node_key": source.node_key, "step_kind": source.step_kind}
    if isinstance(source, SpecSource):
        return {"kind": "spec", "path": source.path}
    if isinstance(source, RunSource):
        return {"kind": "run", "path": source.path}
    if isinstance(source, LedgerSource):
        return {"kind": "ledger", "refs": list(source.refs)}
    return {"kind": "fixed", "text_id": source.text_id}


def source_words(source: SectionSource | BesideOutput) -> str:
    """``source`` as the audit prints it: an artifact by type, id and SHA-256, a path as
    written, the evidence by its count (the evidence appendix lists the refs)."""
    if isinstance(source, ArtifactSource):
        return f"{source.artifact_type} {source.artifact_id} · SHA-256 {source.sha256}"
    if isinstance(source, BesideOutput):
        return f"souběžný krok {source.node_key} ({source.step_kind}), zpráva z něj nečte"
    if isinstance(source, SpecSource):
        return f"specifikace: {source.path}"
    if isinstance(source, RunSource):
        return f"záznam běhu: {source.path}"
    if isinstance(source, LedgerSource):
        return f"evidence: {len(source.refs)} odkazů"
    assert isinstance(source, FixedSource)
    return f"text sestavy: {source.text_id}"


def with_source_audit(document: ReportDocument) -> ReportDocument:
    """``document`` with its manifest printed in the audit appendix, after the audit's own rows:
    one row per section, then the run's outputs no section read. A document without an audit
    appendix is returned unchanged; the manifest is stored with its document model all the
    same."""
    at = next((i for i, s in enumerate(document.sections) if s.id == AUDIT_SECTION_ID), None)
    if at is None:
        return document
    manifest = report_sources(document)
    rows = [
        (f"Zdroje · {entry.title}", "; ".join(source_words(s) for s in entry.sources) or "žádné")
        for entry in manifest.sections
        if entry.section_id != AUDIT_SECTION_ID
    ]
    rows.append(
        (
            "Nepřečtené výstupy běhu",
            "; ".join(source_words(s) for s in manifest.unread) or "žádné",
        )
    )
    audit = document.sections[at]
    blocks = tuple(
        replace(b, entries=(*b.entries, *rows)) if isinstance(b, AuditBlock) else b
        for b in audit.blocks
    )
    sections = list(document.sections)
    sections[at] = replace(audit, blocks=blocks)
    return replace(document, sections=tuple(sections))
