"""What a report must satisfy before it is rendered (pure). Fails closed.

The renderer trusts a validated document completely, so every rule a report must
keep is here, checked on the data, before one byte of DOCX exists. ``validate``
returns every problem at once, so a template author fixes them in one pass;
``require_valid`` raises.

The rules restate governance the report does not own (evidence admission,
suppression, intervals, the Sociomap gate, the client/internal split) at the one
boundary where a report could otherwise quietly break them.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from dataclasses import dataclass
from enum import StrEnum
from typing import Final

from aia_core.domain.evidence.claims import ClaimSurface
from aia_core.domain.report.copy import METHOD_STATUS_COPY
from aia_core.domain.report.evidence import PrintGrade, grade_of
from aia_core.domain.report.model import (
    AuditBlock,
    Block,
    BulletList,
    Callout,
    CalloutKind,
    Chart,
    ChartKind,
    Classification,
    CrossRef,
    Figure,
    Heading,
    Inline,
    KeyFinding,
    KpiRow,
    ListItem,
    NumberCell,
    Paragraph,
    Quote,
    Recommendation,
    ReportDocument,
    ReportKind,
    SociomapFigure,
    Table,
    Text,
    TextCell,
    Value,
)
from aia_core.domain.research_sociomap import MethodologyStatus

CLIENT_KINDS: Final = frozenset({ReportKind.CLIENT, ReportKind.FINAL})

#: The categorical palette has six hues in fixed order; a seventh series folds
#: into "Ostatní" upstream, never into a generated colour.
MAX_SERIES: Final = 6

#: Words that mark internals a client must never see (legacy
#: ``tests/test_release_core.py:22`` checks "quality gate" and "provider").
_INTERNAL_MARKERS: Final = re.compile(
    r"\b(quality gate|provider|prompt|system prompt|claude|anthropic|openai|gpt-\d)\b",
    re.IGNORECASE,
)


class ProblemCode(StrEnum):
    NO_SECTIONS = "no_sections"
    UNKNOWN_REF = "unknown_ref"
    SUPPRESSED_CITED = "suppressed_cited"
    WRONG_SURFACE = "wrong_surface"
    MISSING_INTERVAL = "missing_interval"
    INTERNAL_BLOCK = "internal_block"
    INTERNAL_LEAK = "internal_leak"
    CLASSIFICATION = "classification"
    METHOD_STATUS = "method_status"
    FIGURE_INCOMPLETE = "figure_incomplete"
    SERIES_SHAPE = "series_shape"
    MIXED_UNITS = "mixed_units"
    TOO_MANY_SERIES = "too_many_series"
    MODELLED_MISMATCH = "modelled_mismatch"
    TABLE_SHAPE = "table_shape"
    TABLE_INCOMPLETE = "table_incomplete"
    DUPLICATE_ID = "duplicate_id"
    DANGLING_CROSSREF = "dangling_crossref"
    HEADING_SKIP = "heading_skip"
    LIST_DEPTH = "list_depth"
    QUOTE_UNATTRIBUTED = "quote_unattributed"
    SOCIOMAP_NOT_APPROVED = "sociomap_not_approved"


@dataclass(frozen=True, slots=True)
class Problem:
    code: ProblemCode
    message: str
    where: str


class ReportInvalid(ValueError):
    def __init__(self, problems: tuple[Problem, ...]) -> None:
        self.problems = problems
        lines = "\n".join(f"  [{p.code}] {p.where}: {p.message}" for p in problems)
        super().__init__(f"the report breaks {len(problems)} rule(s):\n{lines}")


def _inlines(block: Block) -> Iterator[Inline]:
    if isinstance(block, Paragraph | Callout):
        yield from block.content
    elif isinstance(block, BulletList):
        yield from _item_inlines(block.items)


def _item_inlines(items: tuple[ListItem, ...]) -> Iterator[Inline]:
    for item in items:
        yield from item.content
        yield from _item_inlines(item.children)


def _prose(block: Block) -> Iterator[str]:
    """Every piece of text a block prints, for the internal-leak scan."""
    for inline in _inlines(block):
        if isinstance(inline, Text):
            yield inline.text
    if isinstance(block, Heading):
        yield block.text
    elif isinstance(block, Callout) and block.title:
        yield block.title
    elif isinstance(block, KeyFinding):
        yield from (block.headline, block.finding, block.evidence, block.meaning)
    elif isinstance(block, Recommendation):
        yield from (block.action, block.why)
    elif isinstance(block, Quote):
        yield block.text
    elif isinstance(block, Table):
        yield block.title
        yield from block.notes
        for trow in block.rows:
            for cell in trow.cells:
                if isinstance(cell, TextCell):
                    yield cell.text
    elif isinstance(block, Figure):
        yield from (block.title, block.alt, *block.notes, *block.chart.categories)


def _prose_refs(block: Block) -> Iterator[str]:
    """Refs a block *prints as a value* outside a table or chart (no suppression)."""
    for inline in _inlines(block):
        if isinstance(inline, Value):
            yield inline.ref
    if isinstance(block, Callout | KeyFinding | Recommendation):
        yield from block.refs
    elif isinstance(block, KpiRow):
        yield from (k.ref for k in block.items)
    elif isinstance(block, Table | Figure) and block.base_ref:
        yield block.base_ref


def _data_refs(block: Block) -> Iterator[str]:
    """Refs in table cells and chart points: a suppressed one is omitted, not printed."""
    if isinstance(block, Table):
        for row in block.rows:
            for cell in row.cells:
                if isinstance(cell, NumberCell):
                    yield cell.ref
    elif isinstance(block, Figure):
        for series in block.chart.series:
            yield from (r for r in series.refs if r is not None)


def _ids(doc: ReportDocument) -> Iterator[tuple[str, str]]:
    for i, section in enumerate(doc.sections):
        if section.id:
            yield section.id, f"section {i + 1}"
        for block in section.blocks:
            bid = getattr(block, "id", None)
            if isinstance(bid, str):
                yield bid, f"section {i + 1}"


def validate(doc: ReportDocument) -> tuple[Problem, ...]:
    """Every rule the document breaks, in document order. Empty means renderable."""
    problems: list[Problem] = []

    def add(code: ProblemCode, message: str, where: str) -> None:
        problems.append(Problem(code, message, where))

    meta, ledger = doc.meta, doc.ledger
    client = meta.kind in CLIENT_KINDS

    if not doc.sections:
        add(ProblemCode.NO_SECTIONS, "a report has at least one chapter", "document")
    if client and ledger.surface is not ClaimSurface.CLIENT_FACING:
        add(
            ProblemCode.WRONG_SURFACE,
            f"a {meta.kind} report prints only claims admitted CLIENT_FACING",
            "ledger",
        )
    if client and meta.classification is not Classification.CLIENT_CONFIDENTIAL:
        add(ProblemCode.CLASSIFICATION, "a client report is client-confidential", "meta")
    if not client and meta.classification is not Classification.INTERNAL:
        add(ProblemCode.CLASSIFICATION, f"a {meta.kind} report is internal", "meta")
    if client and meta.identifiers:
        add(ProblemCode.INTERNAL_BLOCK, "run ids and fingerprints are internal", "meta")
    if not meta.method_status.strip():
        add(ProblemCode.METHOD_STATUS, "the method status is written by code, always", "meta")
    elif meta.method_status not in METHOD_STATUS_COPY:
        add(
            ProblemCode.METHOD_STATUS,
            f"no printed wording for method status {meta.method_status!r}",
            "meta",
        )
    if client and not any(
        isinstance(b, Callout) and b.kind is CalloutKind.METHOD
        for s in doc.sections
        for b in s.blocks
    ):
        add(
            ProblemCode.METHOD_STATUS,
            "the method status must be on the page, plainly, not only in a footnote",
            "document",
        )

    seen: dict[str, str] = {}
    for ident, where in _ids(doc):
        if ident in seen:
            add(ProblemCode.DUPLICATE_ID, f"id {ident!r} is also used in {seen[ident]}", where)
        seen.setdefault(ident, where)

    for si, section in enumerate(doc.sections):
        last_level = 1
        for bi, block in enumerate(section.blocks):
            where = f"section {si + 1} ({section.title}), block {bi + 1}"

            for ref in _prose_refs(block):
                if ledger.is_suppressed(ref):
                    add(ProblemCode.SUPPRESSED_CITED, f"{ref!r} is suppressed", where)
                elif not ledger.knows(ref):
                    add(ProblemCode.UNKNOWN_REF, f"{ref!r} is not in the ledger", where)
            for ref in _data_refs(block):
                if not ledger.knows(ref):
                    add(ProblemCode.UNKNOWN_REF, f"{ref!r} is not in the ledger", where)

            for ref in (*_prose_refs(block), *_data_refs(block)):
                if ref in ledger.rows:
                    evidence = ledger.rows[ref]
                    if client and evidence.is_estimate and evidence.interval is None:
                        add(
                            ProblemCode.MISSING_INTERVAL,
                            f"{ref!r} is a client-facing estimate without an interval",
                            where,
                        )

            for inline in _inlines(block):
                if isinstance(inline, CrossRef) and inline.target not in seen:
                    add(ProblemCode.DANGLING_CROSSREF, f"no target {inline.target!r}", where)

            if client:
                if isinstance(block, AuditBlock):
                    add(ProblemCode.INTERNAL_BLOCK, "the audit block is internal-only", where)
                for chunk in _prose(block):
                    hit = _INTERNAL_MARKERS.search(chunk)
                    if hit:
                        add(ProblemCode.INTERNAL_LEAK, f"internal term {hit.group(0)!r}", where)

            if isinstance(block, Heading):
                if block.level > last_level + 1:
                    add(ProblemCode.HEADING_SKIP, f"level {block.level} after {last_level}", where)
                last_level = block.level
            elif isinstance(block, BulletList):
                if any(child.children for item in block.items for child in item.children):
                    add(ProblemCode.LIST_DEPTH, "lists nest two levels at most", where)
            elif isinstance(block, Quote):
                if not block.attribution.strip():
                    add(ProblemCode.QUOTE_UNATTRIBUTED, "a quote names who said it", where)
            elif isinstance(block, Table):
                if not block.title.strip() or not block.source.strip():
                    add(ProblemCode.TABLE_INCOMPLETE, "a table has a title and a source", where)
                for ri, trow in enumerate(block.rows):
                    if len(trow.cells) != len(block.columns):
                        add(
                            ProblemCode.TABLE_SHAPE,
                            f"row {ri + 1} has {len(trow.cells)} cells for "
                            f"{len(block.columns)} columns",
                            where,
                        )
            elif isinstance(block, Figure):
                if not (block.title.strip() and block.source.strip() and block.alt.strip()):
                    add(
                        ProblemCode.FIGURE_INCOMPLETE,
                        "a figure has a title, a source and alt text",
                        where,
                    )
                problems.extend(_chart_problems(block.chart, doc, where))
            elif isinstance(block, SociomapFigure):
                if not (block.alt.strip() and block.source.strip()):
                    add(ProblemCode.FIGURE_INCOMPLETE, "a map has a source and alt text", where)
                if client and block.methodology_status != MethodologyStatus.CLIENT_FACING.value:
                    add(
                        ProblemCode.SOCIOMAP_NOT_APPROVED,
                        "this Sociomap's methodology is not approved for clients (D6, OI-17)",
                        where,
                    )
    return tuple(problems)


def _chart_problems(chart: Chart, doc: ReportDocument, where: str) -> Iterator[Problem]:
    if len(chart.series) > MAX_SERIES:
        yield Problem(
            ProblemCode.TOO_MANY_SERIES,
            f"{len(chart.series)} series; fold the rest into 'Ostatní' (max {MAX_SERIES})",
            where,
        )
    units: set[str] = set()
    for series in chart.series:
        if len(series.refs) != len(chart.categories):
            yield Problem(
                ProblemCode.SERIES_SHAPE,
                f"series {series.name!r} has {len(series.refs)} values for "
                f"{len(chart.categories)} categories",
                where,
            )
        rows = [doc.ledger.rows[r] for r in series.refs if r is not None and r in doc.ledger.rows]
        units.update(row.unit for row in rows)
        modelled = [grade_of(row, doc.ledger.field_grades) is PrintGrade.MODELLED for row in rows]
        if rows and series.modelled != all(modelled):
            yield Problem(
                ProblemCode.MODELLED_MISMATCH,
                f"series {series.name!r}: hatching must match the rows' grade",
                where,
            )
    if len(units) > 1:
        yield Problem(ProblemCode.MIXED_UNITS, "one chart, one unit, one axis", where)
    if chart.kind is ChartKind.STACKED_100 and units and units != {"%"}:
        yield Problem(ProblemCode.MIXED_UNITS, "a 100 % stack shows percentages", where)


def cited_refs(doc: ReportDocument) -> tuple[str, ...]:
    """Every admitted ref the document prints, once each, in document order.

    What the evidence appendix lists. Suppressed refs are omitted: the document
    removes them, it does not cite them.
    """
    out: dict[str, None] = {}
    for section in doc.sections:
        for block in section.blocks:
            for ref in (*_prose_refs(block), *_data_refs(block)):
                if ref in doc.ledger.rows:
                    out.setdefault(ref, None)
    return tuple(out)


def require_valid(doc: ReportDocument) -> ReportDocument:
    """``doc`` unchanged if it breaks no rule; otherwise :class:`ReportInvalid`."""
    problems = validate(doc)
    if problems:
        raise ReportInvalid(problems)
    return doc
