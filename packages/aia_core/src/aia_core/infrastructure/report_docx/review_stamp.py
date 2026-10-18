"""An approved report version as a file: the stored DOCX with its footers' status stamped.

A stored report is a draft forever: its bytes are its identity (artifact id + SHA-256) and
approval never rewrites them. The renderer states a version's status in its footers alone,
one :attr:`S.STATUS` run per footer part (``layout.py``), so the approved export is the
stored package with exactly those runs' words replaced by :func:`review.approved_words` --
every other part written back as it was read, through the renderer's own package writer.

A version stored before that layout says "KONCEPT — NESCHVÁLENO" on its cover and in its
document control too; stamping its footers would leave an "approved" file that says draft
inside. It is :class:`NotStampable`, and its caller serves it as stored, never partly
stamped (``application.report_export``).
"""

from __future__ import annotations

import hashlib
import io
import re
import zipfile
from typing import Final

from lxml import etree

from aia_core.domain.report.copy import t
from aia_core.domain.report.review import ReviewMark, approved_words
from aia_core.infrastructure.report_docx.renderer import write_package
from aia_core.infrastructure.report_docx.styles import S

__all__ = ["NotStampable", "stamp_review"]

_W: Final = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
_FOOTER: Final = re.compile(r"word/footer\d*\.xml")
#: The parts a reader sees text in besides the footers: none may state a status.
_STORY: Final = re.compile(r"word/(document|header\d*|footnotes|endnotes)\.xml")


class NotStampable(ValueError):
    """The document does not state its status in its footers alone, one run in each."""


def _status_style_id(styles: bytes | None) -> str:
    """The id the package gives the status style; a package without it predates the layout."""
    if styles is not None:
        for style in etree.fromstring(styles).iter(f"{_W}style"):
            name = style.find(f"{_W}name")
            if name is not None and name.get(f"{_W}val") == S.STATUS:
                return str(style.get(f"{_W}styleId"))
    raise NotStampable(f"the package has no {S.STATUS!r} style")


def _status_runs(root: etree._Element, style_id: str) -> list[etree._Element]:
    return [
        run
        for run in root.iter(f"{_W}r")
        if (rs := run.find(f"{_W}rPr/{_W}rStyle")) is not None and rs.get(f"{_W}val") == style_id
    ]


def _text(root: etree._Element) -> str:
    return "".join(node.text or "" for node in root.iter(f"{_W}t"))


def stamp_review(docx: bytes, mark: ReviewMark) -> bytes:
    """``docx``, the stored version ``mark`` names, with its footers' status runs saying
    :func:`approved_words`. Pure and deterministic: the same version and mark give the same
    bytes, every part but the footers byte for byte as stored, in the stored order.

    Raises ``ValueError`` for a draft mark (a draft is its stored bytes) or bytes that are not
    the version the mark names, and :class:`NotStampable` when a footer holds other than one
    status run, or anything a reader sees outside the footers states a status.
    """
    words = approved_words(mark)
    if hashlib.sha256(docx).hexdigest() != mark.sha256:
        raise ValueError(f"these bytes are not version {mark.artifact_id}")
    with zipfile.ZipFile(io.BytesIO(docx)) as package:
        parts = [(info.filename, package.read(info.filename)) for info in package.infolist()]
    named = dict(parts)
    style_id = _status_style_id(named.get("word/styles.xml"))
    for name, data in parts:
        if _STORY.fullmatch(name):
            root = etree.fromstring(data)
            if _status_runs(root, style_id) or t("draft") in _text(root):
                raise NotStampable(f"{name} states a status outside the footers")
    stamped: dict[str, bytes] = {}
    for name, data in parts:
        if not _FOOTER.fullmatch(name):
            continue
        root = etree.fromstring(data)
        runs = _status_runs(root, style_id)
        texts = runs[0].findall(f"{_W}t") if len(runs) == 1 else []
        if len(texts) != 1:
            raise NotStampable(f"{name} has {len(runs)} status runs, not one with its words")
        texts[0].text = words
        stamped[name] = etree.tostring(root, encoding="UTF-8", standalone=True)
    if not stamped:
        raise NotStampable("the package has no footer")
    return write_package((name, stamped.get(name, data)) for name, data in parts)
