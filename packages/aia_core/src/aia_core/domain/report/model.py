"""The report as data: metadata, sections and every component (pure).

A report is a :class:`ReportDocument`: metadata, chapters of blocks, and the
:class:`~aia_core.domain.report.evidence.EvidenceLedger` its numbers come from.
The renderer turns it into DOCX; templates (``templates.py``) build it; the
validator (``validation.py``) refuses one that breaks a rule before anything is
rendered.

Two conventions hold throughout:

* **No block carries a number.** A value is an ``evidence_ref`` (a string) that
  resolves in the ledger. Prose is text a model or a person wrote and that
  analysis already checked for uncited numbers; the model does not re-parse it.
* **Components, not formatting.** A block says what it *is* — a key finding, a
  method-status callout, a data table — and the style sheet decides how it looks.
  There is no colour, font or size anywhere in this module.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import StrEnum
from typing import Literal

from aia_core.domain.report.evidence import EvidenceLedger

# ---------------------------------------------------------------------- inline


@dataclass(frozen=True, slots=True)
class Text:
    """A run of prose. ``emphasis`` is semantic; the style sheet renders it."""

    text: str
    emphasis: Literal["none", "em", "strong"] = "none"


@dataclass(frozen=True, slots=True)
class Value:
    """An evidenced number inline: ``42,5 %`` with its grade mark. Never a literal."""

    ref: str
    with_interval: bool = False


@dataclass(frozen=True, slots=True)
class Footnote:
    """A footnote at this point. Its text is prose, not a number store."""

    text: str


@dataclass(frozen=True, slots=True)
class CrossRef:
    """ "viz graf 3": a reference to a figure, table or section by its id."""

    target: str


@dataclass(frozen=True, slots=True)
class Link:
    text: str
    url: str


Inline = Text | Value | Footnote | CrossRef | Link


def text(s: str) -> tuple[Inline, ...]:
    """Shorthand for a paragraph that is one plain run."""
    return (Text(s),)


# ---------------------------------------------------------------------- blocks


@dataclass(frozen=True, slots=True)
class Heading:
    """A heading inside a chapter (the chapter title itself is the section's).

    ``level`` 2 or 3: 1.1 and 1.1.1. Numbering is the style sheet's.
    """

    text: str
    level: Literal[2, 3]
    id: str | None = None


class ParagraphRole(StrEnum):
    BODY = "body"
    LEDE = "lede"  # the headline answer, set larger


@dataclass(frozen=True, slots=True)
class Paragraph:
    content: tuple[Inline, ...]
    role: ParagraphRole = ParagraphRole.BODY


@dataclass(frozen=True, slots=True)
class ListItem:
    content: tuple[Inline, ...]
    children: tuple[ListItem, ...] = ()


@dataclass(frozen=True, slots=True)
class BulletList:
    """A list, two levels at most. ``ordered`` numbers it (1., 2., …)."""

    items: tuple[ListItem, ...]
    ordered: bool = False


@dataclass(frozen=True, slots=True)
class Quote:
    """A verbatim quote. ``synthetic`` labels a synthetic respondent, always."""

    text: str
    attribution: str
    synthetic: bool


class CalloutKind(StrEnum):
    DECISION = "decision"  # "Odpověď pro rozhodnutí"
    METHOD = "method"  # the method status, printed plainly (brief :337-339)
    LIMITATION = "limitation"
    PROVISIONAL = "provisional"  # what-if / drag output: never a result
    NOTE = "note"


@dataclass(frozen=True, slots=True)
class Callout:
    """A boxed statement. ``refs`` put their grade marks beside the title."""

    kind: CalloutKind
    content: tuple[Inline, ...]
    title: str | None = None
    refs: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class KeyFinding:
    """One finding, as the analysis module wrote it (legacy ``key_findings``)."""

    headline: str
    finding: str
    evidence: str
    meaning: str
    confidence: str
    refs: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class Recommendation:
    """One implication (legacy ``implications``): action, why, priority."""

    action: str
    why: str
    priority: str
    refs: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class Kpi:
    """A stat tile: an evidenced value and what it measures. n comes from the row."""

    label: str
    ref: str


@dataclass(frozen=True, slots=True)
class KpiRow:
    items: tuple[Kpi, ...]


# ---------------------------------------------------------------------- tables


class Align(StrEnum):
    LEFT = "left"
    RIGHT = "right"


@dataclass(frozen=True, slots=True)
class Column:
    """A table column. ``unit`` belongs in the header, never in each cell."""

    label: str
    align: Align = Align.LEFT
    unit: str | None = None


@dataclass(frozen=True, slots=True)
class TextCell:
    text: str


@dataclass(frozen=True, slots=True)
class NumberCell:
    """An evidenced value; ``with_interval`` adds ``(lo-hi)`` beneath it."""

    ref: str
    with_interval: bool = False


@dataclass(frozen=True, slots=True)
class EmptyCell:
    """Nothing to show, and why — "chybí" is not zero and not suppressed."""

    reason: str = "chybí"


Cell = TextCell | NumberCell | EmptyCell


@dataclass(frozen=True, slots=True)
class TableRow:
    cells: tuple[Cell, ...]
    emphasis: bool = False  # a total or base row


@dataclass(frozen=True, slots=True)
class Table:
    """A data table. A row with a suppressed ref is removed and counted in a note.

    ``base_ref`` is the evidence whose effective n the caption states.
    """

    id: str
    title: str
    columns: tuple[Column, ...]
    rows: tuple[TableRow, ...]
    source: str
    base_ref: str | None = None
    notes: tuple[str, ...] = ()
    landscape: bool = False


# ---------------------------------------------------------------------- figures


class ChartKind(StrEnum):
    BAR = "bar"  # horizontal bars, one series
    GROUPED_BAR = "grouped_bar"
    STACKED_100 = "stacked_100"  # shares of a whole, per category
    DIVERGING = "diverging"  # Likert: negative left, positive right, neutral centred
    LINE = "line"  # a trend over an ordered axis
    DOT_INTERVAL = "dot_interval"  # point + interval, the honest default for estimates
    HEATMAP = "heatmap"  # a table coloured by a sequential ramp


@dataclass(frozen=True, slots=True)
class Series:
    """One series: a ref per category, in category order. ``None`` is no value.

    ``modelled`` hatches the marks; it must agree with the rows' grade (validated).
    """

    name: str
    refs: tuple[str | None, ...]
    modelled: bool = False


@dataclass(frozen=True, slots=True)
class Chart:
    kind: ChartKind
    categories: tuple[str, ...]
    series: tuple[Series, ...]
    value_label: str  # axis title: what the numbers are, with the unit


@dataclass(frozen=True, slots=True)
class Figure:
    """A chart with everything a reader needs: title, base, source, notes, alt text.

    The caption is built by the renderer: "Graf N — title (n = …; grade)". The
    alt text is required; a figure without one is refused.
    """

    id: str
    title: str
    chart: Chart
    source: str
    alt: str
    base_ref: str | None = None
    notes: tuple[str, ...] = ()
    landscape: bool = False


@dataclass(frozen=True, slots=True)
class SociomapFigure:
    """A Sociomap image. Rendered only through ``require_client_facing`` (fails closed).

    ``image_png`` is the rendered map; the stress it reports is printed with it.
    """

    id: str
    title: str
    image_png: bytes
    methodology_status: str
    stress_1: float
    source: str
    alt: str


# ---------------------------------------------------------------------- furniture


@dataclass(frozen=True, slots=True)
class PageBreak:
    pass


@dataclass(frozen=True, slots=True)
class EvidenceKey:
    """The persistent key to the grade marks."""


@dataclass(frozen=True, slots=True)
class EvidenceAppendix:
    """One row per cited evidence ref: value, interval, support, basis, disclosures."""


@dataclass(frozen=True, slots=True)
class AuditBlock:
    """Run ids, fingerprints, provider and model. **Internal reports only.**"""

    entries: tuple[tuple[str, str], ...]


Block = (
    Heading
    | Paragraph
    | BulletList
    | Quote
    | Callout
    | KeyFinding
    | Recommendation
    | KpiRow
    | Table
    | Figure
    | SociomapFigure
    | PageBreak
    | EvidenceKey
    | EvidenceAppendix
    | AuditBlock
)


# ---------------------------------------------------------------------- document


class ReportKind(StrEnum):
    CLIENT = "client"  # the client deliverable (legacy client_report_v2)
    FINAL = "final"  # with external triangulation (legacy final_client_report)
    INTERNAL = "internal"  # QA, provider, model and audit visible
    DOCUMENTATION = "documentation"  # the study's method documentation


class Classification(StrEnum):
    CLIENT_CONFIDENTIAL = "client_confidential"
    INTERNAL = "internal"


@dataclass(frozen=True, slots=True)
class Approval:
    """A sign-off on this revision. Recorded by ``ArtifactRepository.approve``."""

    reviewer: str
    decided_on: date


@dataclass(frozen=True, slots=True)
class RevisionEntry:
    revision: int
    on: date
    summary: str


@dataclass(frozen=True, slots=True)
class Branding:
    """Typed ``report_branding``: an optional client logo, cover only (R-D3)."""

    client_logo_png: bytes | None = None


@dataclass(frozen=True, slots=True)
class ReportMeta:
    kind: ReportKind
    title: str
    subtitle: str
    client_name: str
    study_name: str
    study_id: str
    issued_on: date
    revision: int
    method_status: str  # validation.METHOD_STATUS_*, written by code
    prepared_by: str = "AIA"
    classification: Classification = Classification.CLIENT_CONFIDENTIAL
    language: Literal["cs"] = "cs"
    approvals: tuple[Approval, ...] = ()
    history: tuple[RevisionEntry, ...] = ()
    branding: Branding = field(default_factory=Branding)
    #: Run ids, fingerprints, population version: printed only in internal reports.
    identifiers: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True, slots=True)
class Section:
    """A chapter (numbered 1, 2, …) or, with ``appendix``, an appendix (A, B, …)."""

    title: str
    blocks: tuple[Block, ...]
    id: str | None = None
    appendix: bool = False


@dataclass(frozen=True, slots=True)
class ReportDocument:
    meta: ReportMeta
    sections: tuple[Section, ...]
    ledger: EvidenceLedger
    #: Front matter the template asked for.
    table_of_contents: bool = True
    list_of_figures: bool = True
    list_of_tables: bool = True
