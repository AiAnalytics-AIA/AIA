"""A report DOCX read for what a save could change, then a saved one compared with the draft
code wrote (artifact-report RPT8b)."""

from __future__ import annotations

import io
import zipfile
from collections.abc import Callable
from typing import Any

import pytest
from lxml import etree

from aia_core.domain.deep_research.documents import DocumentRefused
from aia_core.domain.report.model import Paragraph, Text, Value
from aia_core.domain.report.saved_changes import ChangeKind, SavedChange, Uncomparable, compare
from aia_core.infrastructure.document_text import ZIP_MAX_MEMBERS
from aia_core.infrastructure.report_docx.census import census
from aia_core.infrastructure.report_docx.renderer import DocxRenderer

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
BODY = "word/document.xml"


def _draft(report_doc: Any) -> bytes:
    return DocxRenderer().render(
        report_doc(
            Paragraph((Text("Bance důvěřuje "), Value("trust_total"), Text(" lidí."))),
            Paragraph(
                (Text("V Praze "), Value("trust_praha"), Text(", v Brně "), Value("trust_brno"))
            ),
            Paragraph((Text("Odstavec bez čísla."),)),
            Paragraph((Text("Vzorek: "), Value("n_total"), Text(" respondentů."))),
            Paragraph((Text("Závěr studie."),)),
        )
    )


def _saved(docx: bytes, edit: Callable[[etree._Element], None]) -> bytes:
    """``docx`` as an editor would save it after ``edit`` to its body."""
    out = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(docx)) as source, zipfile.ZipFile(out, "w") as target:
        for info in source.infolist():
            data = source.read(info)
            if info.filename == BODY:
                root = etree.fromstring(data)
                edit(root)
                data = etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True)
            target.writestr(info, data)
    return out.getvalue()


def _some(element: etree._Element | None) -> etree._Element:
    assert element is not None
    return element


def _control(root: etree._Element, tag: str) -> etree._Element:
    (sdt,) = (
        s for s in root.iter(f"{W}sdt") if _some(s.find(f"{W}sdtPr/{W}tag")).get(f"{W}val") == tag
    )
    return sdt


def _paragraph(root: etree._Element, starts: str) -> etree._Element:
    (p,) = (
        p
        for p in root.iter(f"{W}p")
        if "".join(t.text or "" for t in p.iter(f"{W}t")).startswith(starts)
    )
    return p


def _retype(sdt: etree._Element, text: str) -> None:
    first, *rest = sdt.iter(f"{W}t")
    first.text = text
    for t in rest:
        t.text = ""


def test_a_save_reports_the_retyped_the_deleted_and_the_typed_but_not_the_moved(
    report_doc: Any,
) -> None:
    draft = _draft(report_doc)
    was = census(draft)
    total = next(c.text for c in was.controls if c.tag == "trust_total")
    brno = next(c.text for c in was.controls if c.tag == "trust_brno")

    def edit(root: etree._Element) -> None:
        _retype(_control(root, "trust_total"), "50,0 %")
        sdt = _control(root, "trust_brno")
        _some(sdt.getparent()).remove(sdt)
        _paragraph(root, "Odstavec bez čísla").iter(
            f"{W}t"
        ).__next__().text = "Odstavec bez čísla, 7 z deseti."
        moved = _paragraph(root, "Vzorek: ")
        _paragraph(root, "Závěr studie.").addnext(moved)

    assert compare(was, census(_saved(draft, edit))).changes == (
        SavedChange(ChangeKind.CHANGED, "trust_total", was=total, now="50,0 %"),
        SavedChange(ChangeKind.REMOVED, "trust_brno", was=brno),
        SavedChange(ChangeKind.TYPED, now="7", paragraph="Odstavec bez čísla, 7 z deseti."),
    )


def test_a_save_of_prose_edits_only_reports_nothing(report_doc: Any) -> None:
    draft = _draft(report_doc)

    def edit(root: etree._Element) -> None:
        _paragraph(root, "Bance důvěřuje ").iter(f"{W}t").__next__().text = "Bankám věří "
        _paragraph(root, "Závěr studie.").iter(f"{W}t").__next__().text = "Závěr celé studie."
        cover = _paragraph(root, "Důvěra v banky 2026")
        cover.iter(f"{W}t").__next__().text = "Důvěra v naše banky 2026"

    result = compare(census(draft), census(_saved(draft, edit)))
    assert result.comparable and result.changes == ()


def test_a_fields_result_is_left_to_the_editor(report_doc: Any) -> None:
    """A table of contents' or a caption's cached result an editor updates is no change."""
    draft = _draft(report_doc)

    def edit(root: etree._Element) -> None:
        for begin in root.iter(f"{W}fldChar"):
            if begin.get(f"{W}fldCharType") == "separate":
                result = _some(_some(begin.getparent()).getnext())
                result.append(etree.fromstring(f'<w:t xmlns:w="{W[1:-1]}">99</w:t>'))

    saved = _saved(draft, edit)
    assert b">99<" in zipfile.ZipFile(io.BytesIO(saved)).read(BODY)
    assert compare(census(draft), census(saved)).changes == ()


def test_a_draft_rendered_without_controls_cannot_be_compared(report_doc: Any) -> None:
    draft = _draft(report_doc)

    def unlock(root: etree._Element) -> None:
        for sdt in list(root.iter(f"{W}sdt")):
            content = _some(sdt.find(f"{W}sdtContent"))
            for child in list(content):
                sdt.addprevious(child)
            _some(sdt.getparent()).remove(sdt)

    result = compare(census(_saved(draft, unlock)), census(draft))
    assert result.uncomparable is Uncomparable.NO_CONTROLS and result.changes == ()


def test_a_saved_file_is_read_as_a_strangers(report_doc: Any) -> None:
    draft = _draft(report_doc)
    with pytest.raises(DocumentRefused):
        census(b"not a zip")
    out = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(draft)) as source, zipfile.ZipFile(out, "w") as target:
        for info in source.infolist():
            data = source.read(info)
            if info.filename == BODY:
                data = (
                    b'<?xml version="1.0"?><!DOCTYPE w [<!ENTITY x "1">]>' + data.split(b"?>", 1)[1]
                )
            target.writestr(info, data)
    with pytest.raises(DocumentRefused):
        census(out.getvalue())
    bodiless = io.BytesIO()
    with zipfile.ZipFile(bodiless, "w") as target:
        target.writestr("word/other.xml", b"<x/>")
    crowded = io.BytesIO()
    with zipfile.ZipFile(crowded, "w") as target:
        for i in range(ZIP_MAX_MEMBERS + 1):
            target.writestr(f"m/{i}.xml", b"")
    for refused in (bodiless.getvalue(), crowded.getvalue(), _damaged(draft)):
        with pytest.raises(DocumentRefused):
            census(refused)


def _damaged(docx: bytes) -> bytes:
    """``docx`` with its body stored uncompressed and a byte of it flipped: a bad CRC, met only
    when the member is inflated."""
    out = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(docx)) as source, zipfile.ZipFile(out, "w") as target:
        for info in source.infolist():
            target.writestr(info.filename, source.read(info), zipfile.ZIP_STORED)
    data = bytearray(out.getvalue())
    at = data.index(b"<w:body")
    data[at + 1] ^= 0x01
    return bytes(data)


def test_numbers_a_tab_parts_are_two(report_doc: Any) -> None:
    draft = _draft(report_doc)

    def edit(root: etree._Element) -> None:
        run = etree.fromstring(f'<w:r xmlns:w="{W[1:-1]}"><w:t>12</w:t><w:tab/><w:t>34</w:t></w:r>')
        _paragraph(root, "Závěr studie.").append(run)

    changes = compare(census(draft), census(_saved(draft, edit))).changes
    assert [c.now for c in changes] == ["12", "34"]
