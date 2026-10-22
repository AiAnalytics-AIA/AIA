"""Every printed ledger number in a locked, tagged content control (artifact-report RPT8a).

An editor (ONLYOFFICE, RPT8) keeps a locked control's content as AIA printed it, and its tag names
the ledger ref the number came from, so a save can be checked against the stored document
(the editor spike's F-ED1). This covers a value in prose (P1), a table's number cells and their
intervals (P2) and a caption's base n (P4); the prose around them stays editable.
"""

from __future__ import annotations

import io
import re
import zipfile
from typing import Any

from lxml import etree
from test_report_docx_render import _meta
from test_report_docx_tables import region_table

from aia_core.domain.report.model import (
    Callout,
    CalloutKind,
    Paragraph,
    ReportDocument,
    Section,
    Text,
    Value,
)
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
