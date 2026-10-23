"""Every printed ledger number in a locked, tagged content control (artifact-report RPT8a).

An editor (ONLYOFFICE, RPT8) keeps a locked control's content as AIA printed it, and its tag names
the ledger ref the number came from, so a save can be checked against the stored document
(the editor spike's F-ED1). This covers a value in prose (P1), a table's number cells and their
intervals (P2) and a caption's base n (P4); the prose around them stays editable.
"""

from __future__ import annotations

import dataclasses
import io
import re
import zipfile
from typing import Any

import pytest
import report_samples
from lxml import etree
from test_report_docx_render import _meta
from test_report_docx_tables import region_table

from aia_core.domain.report.control_tags import (
    APPENDIX_COLUMNS,
    ControlTag,
    appendix_tag,
    base_n_tag,
    figure_tag,
    interval_tag,
    parse_tag,
    source_tag,
    suppressed_tag,
    value_tag,
)
from aia_core.domain.report.model import (
    Callout,
    CalloutKind,
    EvidenceAppendix,
    Figure,
    Kpi,
    NumberCell,
    Paragraph,
    ReportDocument,
    Section,
    SociomapFigure,
    Table,
    Text,
    Value,
)
from aia_core.domain.report.validation import cited_refs
from aia_core.infrastructure.document_text import extract_text
from aia_core.infrastructure.report_docx.lint import lint_docx
from aia_core.infrastructure.report_docx.renderer import DocxRenderer
from aia_core.infrastructure.source_reading import read_source

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
DIGIT = re.compile(r"\d")


def _docx(ledger: Any) -> bytes:
    doc = ReportDocument(
        _meta(),
        (
            Section(
                "Výsledky",
                (
                    Callout(CalloutKind.METHOD, ()),
                    Paragraph(
                        (
                            Text("Bance důvěřuje "),
                            Value("trust_total", with_interval=True),
                            Text(" lidí."),
                        )
                    ),
                    region_table(),
                ),
            ),
        ),
        ledger,
    )
    data = DocxRenderer().render(doc)
    assert lint_docx(data) == []
    return data


def _body(ledger: Any) -> etree._Element:
    with zipfile.ZipFile(io.BytesIO(_docx(ledger))) as z:
        return etree.fromstring(z.read("word/document.xml"))


def _controls(body: etree._Element) -> list[tuple[str, str, str]]:
    """Each inline control: its tag, its lock and its text."""
    out = []
    for sdt in body.iter(f"{W}sdt"):
        tag = sdt.find(f"{W}sdtPr/{W}tag")
        lock = sdt.find(f"{W}sdtPr/{W}lock")
        text = "".join(t.text or "" for t in sdt.iter(f"{W}t"))
        out.append(
            (
                tag.get(f"{W}val") if tag is not None else "",
                lock.get(f"{W}val") if lock is not None else "",
                text,
            )
        )
    return out


def _outside_fields(p: etree._Element) -> str:
    """The text of ``p``'s own runs (not a control's), leaving out every field's instruction and
    cached result: what a person could type over."""
    out: list[str] = []
    depth = 0
    for r in p.findall(f"{W}r"):
        for fld in r.findall(f"{W}fldChar"):
            kind = fld.get(f"{W}fldCharType")
            depth += 1 if kind == "begin" else -1 if kind == "end" else 0
        if depth == 0 and not r.findall(f"{W}fldChar"):
            out.extend(t.text or "" for t in r.findall(f"{W}t"))
    return "".join(out)


def test_every_printed_ledger_number_is_locked_and_tagged_with_its_ref(report_ledger: Any) -> None:
    body = _body(report_ledger())
    controls = _controls(body)
    # Every control is locked and names a ref the ledger holds (or a ref's base n).
    assert controls and all(lock == "sdtContentLocked" for _tag, lock, _text in controls)
    tags = {tag for tag, _lock, _text in controls}
    # The prose value, every table cell not suppressed, its interval line, the caption's base n.
    # Each span its own tag: the value, a cell's interval line, the caption's base n.
    assert tags == {
        "trust_total",
        "trust_praha",
        "trust_brno",
        "trust_ostrava",
        "trust_total#interval",
        "trust_praha#interval",
        "trust_brno#interval",
        "trust_ostrava#interval",
        "trust_total#n",
        # The rows suppression removed, counted in the notes row (P13).
        "count:suppressed:tab-regions",
    }
    # The suppressed cell's ref prints nowhere, so it is tagged nowhere.
    assert "trust_zlin" not in tags
    prose = next(
        p
        for p in body.iter(f"{W}p")
        if "Bance důvěřuje" in "".join(t.text or "" for t in p.iter(f"{W}t"))
    )
    # The prose around the number stays outside the control, editable; the number is inside it.
    outside = "".join(t.text or "" for r in prose.findall(f"{W}r") for t in r.iter(f"{W}t"))
    assert "Bance důvěřuje" in outside and not DIGIT.search(outside)
    assert any(tag == "trust_total" and "42,5" in text for tag, _lock, text in controls)


def test_no_digit_of_a_number_cell_or_base_n_is_left_outside_a_control(report_ledger: Any) -> None:
    body = _body(report_ledger())
    table = next(
        t
        for t in body.iter(f"{W}tbl")
        if "Region" in "".join(x.text or "" for x in t.iter(f"{W}t"))
    )
    # A number cell's paragraphs hold their digits in controls only: a run of a cell's paragraph
    # with a digit is the Region label column's text at most, which has none.
    # The notes row (the source line and the suppressed count, P13) is the next chunk's.
    for p in (p for tr in table.findall(f"{W}tr")[:-1] for p in tr.iter(f"{W}p")):
        loose = "".join(t.text or "" for r in p.findall(f"{W}r") for t in r.iter(f"{W}t"))
        assert not DIGIT.search(loose), loose
    # The caption: the paragraph holding the base n's control (the list of tables repeats it).
    caption = next(
        p for p in body.iter(f"{W}p") if any(tag == "trust_total#n" for tag, _l, _t in _controls(p))
    )
    assert "n" in "".join(text for tag, _l, text in _controls(caption) if tag == "trust_total#n")
    # Outside the control only furniture holds a digit: the SEQ field's cached table number.
    assert not DIGIT.search(_outside_fields(caption)), _outside_fields(caption)


def test_a_past_report_read_as_a_client_source_keeps_its_locked_numbers(report_ledger: Any) -> None:
    """A past report uploaded as a client source is read with its numbers: python-docx's
    Paragraph.text skips a control, which would read it without any. The brief's attachment reader
    stays the unit's, which read none (parity)."""
    data = _docx(report_ledger())
    assert "Bance důvěřuje 42,5" not in extract_text(data, "zprava.docx").replace("\u00a0", " ")
    reading = read_source(data, "zprava.docx")
    assert reading.reader == "docx/2"
    read = " ".join(segment.text for segment in reading.segments).replace("\u00a0", " ")
    assert "Bance důvěřuje 42,5" in read and "48,2" in read


def _printed(doc: ReportDocument) -> tuple[set[str], set[str], set[str], set[str], bool]:
    """What the stored document prints as a number: the refs of its values and number cells and
    of its KPI tiles (not suppressed), its figures' and tables' ids, and whether it has an evidence
    appendix."""
    refs: set[str] = set()
    kpis: set[str] = set()
    figures: set[str] = set()
    tables: set[str] = set()
    appendix = False

    def walk(obj: Any) -> None:
        nonlocal appendix
        if isinstance(obj, (Value, NumberCell, Kpi)):
            if not doc.ledger.is_suppressed(obj.ref):
                refs.add(obj.ref)
                if isinstance(obj, Kpi):
                    kpis.add(obj.ref)
        elif isinstance(obj, (Figure, SociomapFigure)):
            figures.add(obj.id)
        elif isinstance(obj, Table):
            tables.add(obj.id)
        elif isinstance(obj, EvidenceAppendix):
            appendix = True
        if isinstance(obj, (tuple, list)):
            for item in obj:
                walk(item)
        elif dataclasses.is_dataclass(obj) and not isinstance(obj, type):
            for f in dataclasses.fields(obj):
                if f.name != "ledger":
                    walk(getattr(obj, f.name))

    walk(doc.sections)
    return refs, kpis, figures, tables, appendix


@pytest.mark.parametrize("kind", report_samples.KINDS)
def test_every_sample_kind_locks_every_ledger_number_it_prints(
    kind: str, report_ledger: Any
) -> None:
    """Every kind of report (client, final, internal, documentation): each value, number cell
    and KPI tile is a locked control tagged with its ref, a KPI tile's base line too; each
    figure's picture is locked; with an evidence appendix, every cell of each cited ref's row;
    a suppressed count names its table or figure; and every tag parses and names a source the
    document holds. The map's own numbers carry their map's tag (part 3; the map's own test)."""
    doc = report_samples.build(kind, report_ledger)
    data = DocxRenderer().render(doc)
    assert lint_docx(data) == []
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        body = etree.fromstring(z.read("word/document.xml"))
    controls = _controls(body)
    assert all(lock == "sdtContentLocked" for _tag, lock, _text in controls)
    cited = set(cited_refs(doc))
    printed, kpis, figures, tables, appendix = _printed(doc)
    tags = {tag for tag, _l, _t in controls}
    for tag in tags:
        parsed = parse_tag(tag)
        assert parsed is not None, tag
        if parsed.kind in ("value", "interval", "base_n", "appendix"):
            assert parsed.name in cited, tag
        elif parsed.kind == "figure":
            assert parsed.name in figures, tag
        elif parsed.kind == "suppressed":
            assert parsed.name in tables | figures, tag
    assert {value_tag(r) for r in printed} <= tags, printed - tags
    assert {base_n_tag(r) for r in kpis} <= tags
    assert {figure_tag(f) for f in figures} <= tags
    if appendix:
        assert {appendix_tag(r, c) for r in cited for c in APPENDIX_COLUMNS} <= tags


def test_the_tag_grammar_reads_back_what_it_writes() -> None:
    """One grammar for the renderer and the save census (RPT8b): every tag it writes parses to
    what it names, and a tag outside it is refused, never guessed."""
    assert parse_tag(value_tag("q2.pct.2")) == ControlTag("value", "q2.pct.2")
    assert parse_tag(interval_tag("q2.pct.2")) == ControlTag("interval", "q2.pct.2")
    assert parse_tag(base_n_tag("q2")) == ControlTag("base_n", "q2")
    assert parse_tag(appendix_tag("q2", "value")) == ControlTag("appendix", "q2", "value")
    assert parse_tag(figure_tag("fig-1")) == ControlTag("figure", "fig-1")
    assert parse_tag(suppressed_tag("tab-regions")) == ControlTag("suppressed", "tab-regions")
    assert parse_tag(source_tag("map", "set-1/aia-sociomap-3")) == ControlTag(
        "map", "set-1/aia-sociomap-3"
    )
    assert parse_tag(source_tag("design", "0123abcd0123abcd")) == ControlTag(
        "design", "0123abcd0123abcd"
    )
    assert parse_tag(source_tag("run", "RUN-1")) == ControlTag("run", "RUN-1")
    for wrong in (
        "",
        "figure:",
        "count:suppressed:",
        "appendix:q2#nope",
        "q2#other",
        "x:y",
        "map:",
    ):
        assert parse_tag(wrong) is None, wrong
    with pytest.raises(ValueError):
        suppressed_tag("")
    with pytest.raises(ValueError):
        source_tag("map", "")


def test_a_block_written_from_a_stored_source_holds_no_ledger_value(report_doc: Any) -> None:
    """A ledger value inside it would be a locked control within a locked control, and the
    client-source reader, one control deep, would lose the number (review of RPT8a part 3)."""
    from aia_core.domain.report.validation import ProblemCode, validate

    mixed = Paragraph((Text("Poměr "), Value("trust_total")), control=source_tag("map", "s/m"))
    assert ProblemCode.CONTROLLED_VALUE in {p.code for p in validate(report_doc(mixed))}
    alone = Paragraph((Text("Stress-1 je 0,123."),), control=source_tag("map", "s/m"))
    assert ProblemCode.CONTROLLED_VALUE not in {p.code for p in validate(report_doc(alone))}
