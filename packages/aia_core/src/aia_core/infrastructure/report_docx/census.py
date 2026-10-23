"""What a report DOCX holds that a save could change: its tagged controls and loose numbers.

The census :func:`aia_core.domain.report.saved_changes.compare` compares (artifact-report RPT8b).
It reads the body (``word/document.xml``) alone: running heads and footers are furniture code
rewrites on every render. A control counts when its tag is in the grammar
(``control_tags.parse_tag``); one an editor added with any other tag is read as ordinary text. A
field's instruction and cached result (a table of contents, a caption's number, a page) are left
out, since an editor may update them on its own.

A saved DOCX comes back from the editor, so it is read as a stranger's file: the ZIP's bounds and
a declared document type are refused before the body is parsed (``document_text``), and the
parser resolves no entity and reaches no network.
"""

from __future__ import annotations

import io
import re
import zipfile
from typing import Final

from lxml import etree

from aia_core.domain.deep_research.documents import DocumentRefused
from aia_core.domain.report.control_tags import parse_tag
from aia_core.domain.report.saved_changes import Census, ControlSpan, LooseNumber
from aia_core.infrastructure.document_text import DtdDeclared, check_zip_bounds, refuse_dtd

W: Final = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
BODY: Final = "word/document.xml"
#: A number as a person reads it: a sign, digits, and the Czech separators between them.
NUMBER: Final = re.compile(r"(?:(?<!\w)[-\u2212])?\d+(?:[.,\u00a0\u202f]\d+)*")
#: What prints as a space between runs: digits on either side are two numbers.
_SPACES: Final = frozenset({f"{W}tab", f"{W}br", f"{W}cr"})
#: Where loose text stops: a token never runs across a control or a field.
_BREAK: Final = "\x00"


def _tagged(sdt: etree._Element) -> str | None:
    tag = sdt.find(f"{W}sdtPr/{W}tag")
    value = tag.get(f"{W}val") if tag is not None else None
    return value if value is not None and parse_tag(value) is not None else None


def _text(element: etree._Element) -> str:
    return "".join(t.text or "" for t in element.iter(f"{W}t"))


def _loose(p: etree._Element) -> str:
    """``p``'s text outside every tagged control and field, ``_BREAK`` where either stood."""
    out: list[str] = []
    depth = 0

    def walk(element: etree._Element) -> None:
        nonlocal depth
        for child in element:
            if child.tag == f"{W}p":  # a nested paragraph (a text box) is its own
                continue
            if child.tag == f"{W}sdt" and _tagged(child) is not None:
                out.append(_BREAK)
                continue
            if child.tag == f"{W}fldSimple":
                out.append(_BREAK)
                continue
            if child.tag == f"{W}fldChar":
                kind = child.get(f"{W}fldCharType")
                depth += 1 if kind == "begin" else -1 if kind == "end" else 0
                depth = max(depth, 0)
                out.append(_BREAK)
                continue
            if child.tag in _SPACES:
                out.append(" ")
                continue
            if child.tag == f"{W}t":
                if depth == 0:
                    out.append(child.text or "")
                continue
            walk(child)

    walk(p)
    return "".join(out)


def _malformed(exc: BaseException) -> DocumentRefused:
    return DocumentRefused(f"the DOCX has no readable body: {exc}", reason="document_malformed")


def census(docx: bytes) -> Census:
    """The tagged controls and loose numbers of ``docx``'s body, in document order.

    Raises ``DocumentRefused`` for a file past the ZIP bounds, not a ZIP, with no readable body or
    with a body that declares a document type."""
    check_zip_bounds(docx, "DOCX")
    try:
        # The member is first inflated here: a missing body, a bad CRC, a corrupt stream, an
        # encrypted or unsupported member each raise their own error; all are a damaged file.
        with zipfile.ZipFile(io.BytesIO(docx)) as archive:
            body = archive.read(BODY)
    except Exception as exc:
        raise _malformed(exc) from exc
    try:
        refuse_dtd(body)
        parser = etree.XMLParser(resolve_entities=False, no_network=True, huge_tree=False)
        root = etree.fromstring(body, parser)
    except (DtdDeclared, etree.XMLSyntaxError) as exc:
        raise _malformed(exc) from exc
    controls = tuple(
        ControlSpan(tag, _text(sdt))
        for sdt in root.iter(f"{W}sdt")
        if (tag := _tagged(sdt)) is not None
    )
    loose = tuple(
        LooseNumber(m.group(), _text(p))
        for p in root.iter(f"{W}p")
        for m in NUMBER.finditer(_loose(p))
    )
    return Census(controls, loose)
