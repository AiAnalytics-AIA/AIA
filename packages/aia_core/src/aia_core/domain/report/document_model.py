"""The report's document model as stored data (pure; report-delivery RD5a, F-ED3).

A report is composed as a :class:`~aia_core.domain.report.model.ReportDocument` and rendered to
DOCX. Until RD5a the document was dropped once its bytes were written, so nothing but the DOCX
could show what a report says, and no edit could name a paragraph. :func:`document_payload` is
the document as JSON, stored beside the DOCX under the same input fingerprint, which the
workbench's Zpráva pane reads and every later edit (RD5, RD6) names its paragraph in.

Three rules hold:

* **Ids are the document's, never the reader's.** Every section has an id: the composer's own
  (``intro``, ``ch-1`` …), or ``section-<n>`` by its position when it gave none. Every block has
  ``<section id>.<n>``, its 1-based position in the section. They are fixed once stored: a later
  revision of the draft (RD5) keeps them, a new composition is a new document.
* **No number is written here.** A value is its evidence ref; the ledger beside the sections
  carries the ref's printed text, made by :mod:`~aia_core.domain.report.numbers` exactly as the
  DOCX prints it, so the pane prints what the file prints and never formats a number itself.
  A suppressed ref has no text, only its reasons.
* **No bytes.** An image is named by its SHA-256; the DOCX holds the image.

Since ``aia-report-document-2`` every section carries its ``sources`` and the document the run's
outputs no section read, ``unread`` (artifact-chain CHN1, :mod:`~aia_core.domain.report.sources`).
A stored ``-1`` document is still read: it recorded no sources, and a reader says so rather than
presuming any. Since ``-3`` every ledger entry carries its claim's ``level`` (aggregate, segment
or individual), which the client deliverable's gate reads (report-delivery RD0); an older entry
has none, so the gate cannot judge it.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from typing import Any, Final

from aia_core.domain.report import numbers
from aia_core.domain.report.evidence import EvidenceLedger
from aia_core.domain.report.model import (
    AuditBlock,
    Block,
    BulletList,
    Callout,
    Chart,
    Column,
    CrossRef,
    EmptyCell,
    EvidenceAppendix,
    EvidenceKey,
    Figure,
    Footnote,
    Heading,
    Inline,
    KeyFinding,
    KpiRow,
    Link,
    ListItem,
    NumberCell,
    PageBreak,
    Paragraph,
    Quote,
    Recommendation,
    ReportDocument,
    SociomapFigure,
    Table,
    Text,
    TextCell,
    Value,
)
from aia_core.domain.report.printable import printable, xml_text
from aia_core.domain.report.sources import report_sources, source_payload
from aia_core.domain.report.validation import CLIENT_KINDS

#: The stored form's contract. A reader refuses any other (:func:`read_document_payload`).
DOCUMENT_MODEL_CONTRACT: Final = "aia-report-document-3"
#: Contracts still read: ``-1`` (RD5a) is ``-2`` without the manifest, ``-2`` is ``-3`` without
#: each entry's level.
READABLE_CONTRACTS: Final = frozenset(
    {"aia-report-document-1", "aia-report-document-2", DOCUMENT_MODEL_CONTRACT}
)
DOCUMENT_MODEL_MEDIA_TYPE: Final = "application/json"


class DocumentModelInvalid(ValueError):
    """Stored bytes that are not a document model of this contract."""


def document_payload(document: ReportDocument) -> dict[str, Any]:
    """``document`` as JSON-ready data, its text as the DOCX printed it (``printable``). See the
    module note."""
    document = printable(document)
    client = document.meta.kind in CLIENT_KINDS
    writer = _Writer(document.ledger, client=client)
    manifest = report_sources(document)
    sections = []
    for index, (section, entry) in enumerate(
        zip(document.sections, manifest.sections, strict=True), start=1
    ):
        section_id = section.id or f"section-{index}"
        blocks = [
            writer.block(block, f"{section_id}.{position}")
            for position, block in enumerate(section.blocks, start=1)
        ]
        sections.append(
            {
                "id": section_id,
                "title": section.title,
                "appendix": section.appendix,
                "blocks": blocks,
                "refs": _unique(ref for block in blocks for ref in block["refs"]),
                "sources": [source_payload(s, client=client) for s in entry.sources],
            }
        )
    meta = document.meta
    logo = meta.branding.client_logo_png
    return {
        "contract": DOCUMENT_MODEL_CONTRACT,
        "meta": {
            "kind": meta.kind.value,
            "title": meta.title,
            "subtitle": meta.subtitle,
            "client_name": meta.client_name,
            "study_name": meta.study_name,
            "study_id": meta.study_id,
            "issued_on": meta.issued_on.isoformat(),
            "revision": meta.revision,
            "method_status": meta.method_status,
            "prepared_by": meta.prepared_by,
            "classification": meta.classification.value,
            "language": meta.language,
            "client_logo_sha256": _sha256(logo) if logo is not None else None,
            # Run ids and fingerprints print only in an internal report; so here.
            "identifiers": [] if client else [list(pair) for pair in meta.identifiers],
        },
        "sections": sections,
        "unread": [source_payload(s, client=client) for s in manifest.unread],
        "ledger": writer.ledger_payload(),
    }


def document_bytes(document: ReportDocument) -> bytes:
    """The stored form: canonical JSON (sorted keys, no spaces), so the same document is the
    same bytes and its SHA-256 names it."""
    return json.dumps(
        document_payload(document), ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def read_document_payload(data: bytes) -> dict[str, Any]:
    """Stored bytes as the document model, refused unless they are a contract still read."""
    try:
        payload = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise DocumentModelInvalid("the stored document model is not JSON") from exc
    if not isinstance(payload, dict) or payload.get("contract") not in READABLE_CONTRACTS:
        raise DocumentModelInvalid(f"the stored document model is not {DOCUMENT_MODEL_CONTRACT}")
    if not isinstance(payload.get("sections"), list) or not isinstance(payload.get("ledger"), dict):
        raise DocumentModelInvalid("the stored document model has no sections or ledger")
    return payload


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _unique(refs: Iterable[str]) -> list[str]:
    """In order of first appearance: the order a reader meets them."""
    return list(dict.fromkeys(refs))


class _Writer:
    def __init__(self, ledger: EvidenceLedger, *, client: bool) -> None:
        self._ledger = ledger
        self._client = client
        self._cited: dict[str, None] = {}

    # ------------------------------------------------------------------ ledger

    def ledger_payload(self) -> dict[str, Any]:
        """Every ref the document cites, admitted or suppressed, with its printed text."""
        rows: dict[str, Any] = {}
        for ref in self._cited:
            if self._ledger.is_suppressed(ref):
                rows[ref] = {"suppressed": True, "reasons": list(self._ledger.suppressed[ref])}
                continue
            row = self._ledger.row(ref)  # unknown refs fail here, as they fail the render
            effective = row.support.effective_n
            rows[ref] = {
                "suppressed": False,
                "value_text": numbers.with_unit(row.value, row.decimals, row.unit),
                "number_text": numbers.number(row.value, row.decimals),
                "interval_text": (
                    numbers.interval(row.interval, row.decimals, row.unit)
                    if row.interval is not None
                    else None
                ),
                # Absent n is unknown, never a guess (blocks.base_text).
                "base_text": numbers.base_n(effective) if effective is not None else None,
                "metric": xml_text(str(row.metric)),  # a choice's label, as typed
                "unit": row.unit.value,
                "grade": self._ledger.grade(ref).value,
                "indicative": self._ledger.is_indicative(ref),
                "modelled_panel": self._ledger.modelled_panel((ref,)),
                "basis": row.basis.value,
                "level": row.level.value,
                "support": row.support.status.value,
                "question_id": row.question_id,
                "data_origin": row.data_origin.value if row.data_origin is not None else None,
            }
        return {"surface": self._ledger.surface.value, "refs": rows}

    def _cite(self, ref: str) -> str:
        self._cited.setdefault(ref, None)
        return ref

    def _with_interval(self, ref: str, asked: bool) -> bool:
        """``blocks.shows_interval``: when asked, and always for a client estimate."""
        if self._ledger.is_suppressed(ref):
            return False
        row = self._ledger.row(ref)
        return row.interval is not None and (asked or (self._client and row.is_estimate))

    # ------------------------------------------------------------------ inline

    def inlines(self, content: tuple[Inline, ...], refs: list[str]) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for inline in content:
            if isinstance(inline, Text):
                out.append({"type": "text", "text": inline.text, "emphasis": inline.emphasis})
            elif isinstance(inline, Value):
                refs.append(self._cite(inline.ref))
                out.append(
                    {
                        "type": "value",
                        "ref": inline.ref,
                        "with_interval": self._with_interval(inline.ref, inline.with_interval),
                    }
                )
            elif isinstance(inline, Footnote):
                out.append({"type": "footnote", "text": inline.text})
            elif isinstance(inline, CrossRef):
                out.append({"type": "cross_ref", "target": inline.target})
            elif isinstance(inline, Link):
                out.append({"type": "link", "text": inline.text, "url": inline.url})
            else:  # pragma: no cover - the Inline union is closed
                raise TypeError(f"no stored form for {type(inline).__name__}")
        return out

    def _list_item(self, item: ListItem, refs: list[str]) -> dict[str, Any]:
        return {
            "content": self.inlines(item.content, refs),
            "children": [self._list_item(child, refs) for child in item.children],
        }

    def _refs(self, given: Iterable[str], refs: list[str]) -> list[str]:
        for ref in given:
            refs.append(self._cite(ref))
        return list(given)

    # ------------------------------------------------------------------ blocks

    def block(self, block: Block, block_id: str) -> dict[str, Any]:
        refs: list[str] = []
        body = self._body(block, refs)
        return {"id": block_id, **body, "refs": _unique(refs)}

    def _body(self, block: Block, refs: list[str]) -> dict[str, Any]:
        if isinstance(block, Heading):
            return {"type": "heading", "text": block.text, "level": block.level, "anchor": block.id}
        if isinstance(block, Paragraph):
            content = self.inlines(block.content, refs)
            return {
                "type": "paragraph",
                "role": block.role.value,
                "content": content,
                "marks": self._refs(block.refs, refs),
            }
        if isinstance(block, BulletList):
            return {
                "type": "list",
                "ordered": block.ordered,
                "items": [self._list_item(item, refs) for item in block.items],
            }
        if isinstance(block, Quote):
            return {
                "type": "quote",
                "text": block.text,
                "attribution": block.attribution,
                "synthetic": block.synthetic,
            }
        if isinstance(block, Callout):
            content = self.inlines(block.content, refs)
            return {
                "type": "callout",
                "kind": block.kind.value,
                "title": block.title,
                "content": content,
                "marks": self._refs(block.refs, refs),
            }
        if isinstance(block, KeyFinding):
            return {
                "type": "key_finding",
                "headline": block.headline,
                "finding": block.finding,
                "evidence": block.evidence,
                "meaning": block.meaning,
                "confidence": block.confidence,
                "marks": self._refs(block.refs, refs),
            }
        if isinstance(block, Recommendation):
            return {
                "type": "recommendation",
                "action": block.action,
                "why": block.why,
                "priority": block.priority,
                "marks": self._refs(block.refs, refs),
            }
        if isinstance(block, KpiRow):
            for kpi in block.items:
                refs.append(self._cite(kpi.ref))
            return {
                "type": "kpi_row",
                "items": [{"label": kpi.label, "ref": kpi.ref} for kpi in block.items],
            }
        if isinstance(block, Table):
            return self._table(block, refs)
        if isinstance(block, Figure):
            return {
                "type": "figure",
                "anchor": block.id,
                "title": block.title,
                "chart": self._chart(block.chart, refs),
                "source": block.source,
                "alt": block.alt,
                "base_ref": self._cite_optional(block.base_ref, refs),
                "notes": list(block.notes),
            }
        if isinstance(block, SociomapFigure):
            return {
                "type": "sociomap_figure",
                "anchor": block.id,
                "title": block.title,
                "image_sha256": _sha256(block.image_png),
                "methodology_status": block.methodology_status,
                "stress_1": block.stress_1,
                "fit_caption": block.fit_caption,
                "source": block.source,
                "alt": block.alt,
            }
        if isinstance(block, PageBreak):
            return {"type": "page_break"}
        if isinstance(block, EvidenceKey):
            return {"type": "evidence_key"}
        if isinstance(block, EvidenceAppendix):
            return {"type": "evidence_appendix"}
        if isinstance(block, AuditBlock):
            return {"type": "audit", "entries": [list(pair) for pair in block.entries]}
        raise TypeError(f"no stored form for {type(block).__name__}")  # pragma: no cover

    def _cite_optional(self, ref: str | None, refs: list[str]) -> str | None:
        if ref is None:
            return None
        refs.append(self._cite(ref))
        return ref

    def _table(self, table: Table, refs: list[str]) -> dict[str, Any]:
        rows = []
        removed = 0
        for row in table.rows:
            # The DOCX removes a row that cites a suppressed ref and counts it, never greys it
            # (report_docx/tables.py render_table); the stored table says what the file says.
            if any(
                isinstance(cell, NumberCell) and self._ledger.is_suppressed(cell.ref)
                for cell in row.cells
            ):
                removed += 1
                continue
            cells: list[dict[str, Any]] = []
            for cell in row.cells:
                if isinstance(cell, TextCell):
                    cells.append({"type": "text", "text": cell.text})
                elif isinstance(cell, NumberCell):
                    refs.append(self._cite(cell.ref))
                    cells.append(
                        {
                            "type": "number",
                            "ref": cell.ref,
                            "with_interval": self._with_interval(cell.ref, cell.with_interval),
                        }
                    )
                elif isinstance(cell, EmptyCell):
                    cells.append({"type": "empty", "reason": cell.reason})
            rows.append({"cells": cells, "emphasis": row.emphasis})
        return {
            "type": "table",
            "anchor": table.id,
            "title": table.title,
            "columns": [_column(column) for column in table.columns],
            "rows": rows,
            "suppressed_rows": removed,
            "source": table.source,
            "base_ref": self._cite_optional(table.base_ref, refs),
            "notes": list(table.notes),
        }

    def _chart(self, chart: Chart, refs: list[str]) -> dict[str, Any]:
        series = []
        for one in chart.series:
            for ref in one.refs:
                if ref is not None:
                    refs.append(self._cite(ref))
            series.append({"name": one.name, "refs": list(one.refs), "modelled": one.modelled})
        return {
            "kind": chart.kind.value,
            "categories": list(chart.categories),
            "series": series,
            "value_label": chart.value_label,
        }


def _column(column: Column) -> dict[str, Any]:
    return {"label": column.label, "align": column.align.value, "unit": column.unit}
