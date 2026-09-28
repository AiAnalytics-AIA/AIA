"""A lint for the report's own DOCX: no direct formatting, schema order kept.

Every paragraph and run in a report takes its look from a named style, so a
restyle is a token change. This checks the package a renderer produced and names
every place that breaks that, and every settings or section-properties element
Word would call corrupt for being out of schema order. The renderer's tests run
it on every sample report; ``tools/report_preview.py`` runs it on any file.

A paragraph with no ``w:pStyle`` is in the default paragraph style (``Normal``,
the body style), which is a named style; python-docx writes it that way.
"""

from __future__ import annotations

import io
import zipfile
from typing import Final

from lxml import etree

from aia_core.infrastructure.report_docx.ooxml import SECTPR_ORDER, SETTINGS_ORDER, in_schema_order

_W: Final = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"

#: Properties a paragraph, run, table, row or cell may carry directly. Anything
#: else is formatting, and formatting belongs in the style sheet.
_ALLOWED: Final[dict[str, frozenset[str]]] = {
    "pPr": frozenset({"pStyle", "numPr", "sectPr", "rPr"}),
    "rPr": frozenset({"rStyle"}),
    "tblPr": frozenset({"tblStyle", "tblW", "tblLook", "tblLayout"}),
    "trPr": frozenset({"tblHeader", "cantSplit"}),
    "tcPr": frozenset({"tcW", "gridSpan", "vMerge", "vAlign"}),
}

#: An rPr is a run's, or a paragraph mark's (in pPr); elsewhere it is a style's.
_RUN_OWNERS: Final = frozenset({"r", "pPr"})

#: Parts whose paragraphs the lint reads: the body, running heads, footnotes.
_STORY_ROOTS: Final = frozenset({f"{_W}document", f"{_W}hdr", f"{_W}ftr", f"{_W}footnotes"})


def _local(tag: object) -> str:
    return str(tag).rsplit("}", 1)[-1]


def _text(el: etree._Element) -> str:
    return "".join(t.text or "" for t in el.iter(f"{_W}t"))[:60]


def lint_docx(data: bytes) -> list[str]:
    """Every problem in the package, as ``part: message``. Empty means clean."""
    problems: list[str] = []
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        names = z.namelist()
        for name in names:
            if not (name.startswith("word/") and name.endswith(".xml")):
                continue
            root = etree.fromstring(z.read(name))
            if name == "word/settings.xml" and not in_schema_order(root, SETTINGS_ORDER):
                problems.append(f"{name}: children out of schema order")
            if root.tag not in _STORY_ROOTS:
                continue
            for sect in root.iter(f"{_W}sectPr"):
                if not in_schema_order(sect, SECTPR_ORDER):
                    problems.append(f"{name}: a sectPr is out of schema order")
            for container, allowed in _ALLOWED.items():
                for props in root.iter(f"{_W}{container}"):
                    parent = props.getparent()
                    # a paragraph mark's rPr sits in pPr; it may only name a style too
                    if container == "rPr" and _local(getattr(parent, "tag", "")) not in _RUN_OWNERS:
                        continue
                    if _is_separator(props):
                        continue
                    for child in props:
                        local = _local(child.tag)
                        if local not in allowed:
                            owner = props.getparent()
                            where = _text(owner) if owner is not None else ""
                            problems.append(
                                f"{name}: direct formatting <{local}> in {container} ({where!r})"
                            )
    return problems


def _is_separator(props: etree._Element) -> bool:
    """The footnote separators Word requires carry their own spacing; they are not text."""
    for ancestor in props.iterancestors(f"{_W}footnote"):
        return ancestor.get(f"{_W}type") in {"separator", "continuationSeparator"}
    return False
