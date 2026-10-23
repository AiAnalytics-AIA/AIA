"""An approved report version as a file: the stored DOCX with its footers' status stamped.

A stored report is a draft forever: its bytes are its identity (artifact id + SHA-256) and
approval never rewrites them. The renderer states a version's status in its footers alone,
one :attr:`S.STATUS` run per footer part (``layout.py``), so the approved export is the
stored package with exactly those runs' words replaced by :func:`review.approved_words` --
the cover's, in its narrower status column (:attr:`S.COVER_FOOTER`), by
:func:`review.approved_lines` one under the other, so the version id is never broken at its
hyphen -- every other part written back as it was read, through the renderer's own package
writer.

A version stored before that layout says "KONCEPT — NESCHVÁLENO" on its cover and in its
document control too; stamping its footers would leave an "approved" file that says draft
inside. It is :class:`NotStampable`, and its caller serves it as stored, never partly
stamped (``application.report_export``).

The check reads the renderer's own status marks alone -- a run in the status style, or the
draft words themselves -- never the study's words. A bank's questionnaire asks "Jaký byl důvod
neschválení vaší žádosti o hypotéku?", a quoted source says "podíl neschválených žádostí
vzrostl": that is what the study says, not the version's status, and reading every word
beginning "neschválen" as status would serve such an approved version with its draft footers
(cross-review). That no composer's own words state a status outside
the footers is held where those words are rendered: the four templates (``test_review_stamp``),
the stored internal report and report with literature (``test_analysis_executor``) and the
client report (``test_ai_fieldwork``).
"""

from __future__ import annotations

import hashlib
import io
import re
import zipfile
from typing import Final

from lxml import etree

from aia_core.domain.report.copy import t
from aia_core.domain.report.review import ReviewMark, approved_lines, approved_words
from aia_core.infrastructure.document_text import DtdDeclared, refuse_dtd
from aia_core.infrastructure.report_docx.renderer import write_package
from aia_core.infrastructure.report_docx.styles import S

__all__ = ["NotStampable", "stamp_review"]

_W: Final = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
_FOOTER: Final = re.compile(r"word/footer\d*\.xml")
#: The parts a reader sees text in besides the footers: none may state a status.
_STORY: Final = re.compile(r"word/(document|header\d*|footnotes|endnotes)\.xml")


class NotStampable(ValueError):
    """The document does not state its status in its footers alone, one run in each."""


def _parse(name: str, data: bytes) -> etree._Element:
    """A part of the package, parsed as a stranger's: a version saved in the report editor is
    (RPT8c). A part declaring a document type is refused before any entity is read, and no
    entity is ever resolved."""
    try:
        refuse_dtd(data)
    except DtdDeclared as exc:
        raise NotStampable(f"{name} declares a document type") from exc
    return etree.fromstring(
        data, etree.XMLParser(resolve_entities=False, no_network=True, huge_tree=False)
    )


def _style_ids(styles: bytes | None) -> dict[str, str]:
    """The id the package gives each of its styles, by the style's name."""
    ids: dict[str, str] = {}
    if styles is not None:
        for style in _parse("word/styles.xml", styles).iter(f"{_W}style"):
            name = style.find(f"{_W}name")
            if name is not None:
                ids[str(name.get(f"{_W}val"))] = str(style.get(f"{_W}styleId"))
    return ids


def _status_runs(root: etree._Element, style_id: str) -> list[etree._Element]:
    return [
        run
        for run in root.iter(f"{_W}r")
        if (rs := run.find(f"{_W}rPr/{_W}rStyle")) is not None and rs.get(f"{_W}val") == style_id
    ]


def _paragraph_style(run: etree._Element) -> str | None:
    """The style id of the paragraph ``run`` is in, if it names one."""
    paragraph = next(run.iterancestors(f"{_W}p"), None)
    style = paragraph.find(f"{_W}pPr/{_W}pStyle") if paragraph is not None else None
    return None if style is None else style.get(f"{_W}val")


def _text(root: etree._Element) -> str:
    return "".join(node.text or "" for node in root.iter(f"{_W}t"))


def stamp_review(docx: bytes, mark: ReviewMark) -> bytes:
    """``docx``, the stored version ``mark`` names, with its footers' status runs saying
    :func:`approved_words`. Pure and deterministic: the same version and mark give the same
    bytes, every part but the footers byte for byte as stored, in the stored order.

    Raises ``ValueError`` for a draft mark (a draft is its stored bytes) or bytes that are not
    the version the mark names, and :class:`NotStampable` when a footer holds other than one
    status run, or a part a reader sees outside the footers holds a status run or the draft
    words.
    """
    words = approved_words(mark)
    if hashlib.sha256(docx).hexdigest() != mark.sha256:
        raise ValueError(f"these bytes are not version {mark.artifact_id}")
    with zipfile.ZipFile(io.BytesIO(docx)) as package:
        parts = [(info.filename, package.read(info.filename)) for info in package.infolist()]
    ids = _style_ids(dict(parts).get("word/styles.xml"))
    if S.STATUS not in ids:  # a package without it predates the layout
        raise NotStampable(f"the package has no {S.STATUS!r} style")
    style_id, cover_id = ids[S.STATUS], ids.get(S.COVER_FOOTER)
    for name, data in parts:
        if _STORY.fullmatch(name):
            root = _parse(name, data)
            if _status_runs(root, style_id) or t("draft") in _text(root):
                raise NotStampable(f"{name} states a status outside the footers")
    stamped: dict[str, bytes] = {}
    for name, data in parts:
        if not _FOOTER.fullmatch(name):
            continue
        root = _parse(name, data)
        runs = _status_runs(root, style_id)
        texts = runs[0].findall(f"{_W}t") if len(runs) == 1 else []
        if len(texts) != 1:
            raise NotStampable(f"{name} has {len(runs)} status runs, not one with its words")
        if cover_id is not None and _paragraph_style(runs[0]) == cover_id:
            # The cover's column is narrower than the words: one line each, so the version
            # id is never broken at its hyphen.
            status, version = approved_lines(mark)
            texts[0].text = status
            line, second = etree.Element(f"{_W}br"), etree.Element(f"{_W}t")
            second.text = version
            texts[0].addnext(line)
            line.addnext(second)
        else:
            texts[0].text = words
        stamped[name] = etree.tostring(root, encoding="UTF-8", standalone=True)
    if not stamped:
        raise NotStampable("the package has no footer")
    return write_package((name, stamped.get(name, data)) for name, data in parts)
