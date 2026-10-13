"""A client's sources: the material a person adds, kept as it came (lifecycle K2a).

A **source** is one original -- a document, a sheet, a captured page -- stored once per
client by its SHA-256, with every time someone added it kept as an **occurrence**. What
reading it produced is its :class:`SourceReading`: the text in segments, each with a
:class:`Locator` that says where in the original it stands (a page, a paragraph, a
table cell, a row), and an outcome that never claims more than happened.

A source is not knowledge. Storing it accepts nothing, no study context reads it, and
knowledge comes from it only as proposals a person accepts
(``.planning/plans/client-knowledge-lifecycle.md`` § K2 slicing).

Pure: no I/O.
"""

from __future__ import annotations

import re
from datetime import datetime
from enum import StrEnum
from typing import Final
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .attachments import extension_of

__all__ = [
    "NAME_MAX_CHARS",
    "SOURCE_MAX_BYTES",
    "SOURCE_TEXT_MAX_CHARS",
    "Locator",
    "ReadingNote",
    "ReadingOutcome",
    "Segment",
    "SourceFamily",
    "SourceOccurrence",
    "SourceOrigin",
    "SourceReading",
    "SourceRecord",
    "SourceRejected",
    "display_name",
    "family_of",
    "media_type_of",
    "new_occurrence_id",
    "new_source_id",
    "reading_of_segments",
]

#: The most one source may hold, as a brief's attachment (``attachments.py:41``).
SOURCE_MAX_BYTES: Final = 25 * 1024 * 1024
#: The most text a reading keeps, as an attachment's (``attachments.py:45``).
SOURCE_TEXT_MAX_CHARS: Final = 250_000

_ID: Final = re.compile(r"^(SRC|SRO)-[0-9a-f]{16}$")


def new_source_id() -> str:
    return f"SRC-{uuid4().hex[:16]}"


def new_occurrence_id() -> str:
    return f"SRO-{uuid4().hex[:16]}"


class SourceRejected(ValueError):
    """A source refused before anything was stored. ``reason`` is stable."""

    def __init__(self, message: str, *, reason: str) -> None:
        super().__init__(message)
        self.reason = reason


class SourceOrigin(StrEnum):
    """How the material reached AIA."""

    UPLOAD = "UPLOAD"
    WEB = "WEB"
    DEEP_RESEARCH = "DEEP_RESEARCH"


class SourceFamily(StrEnum):
    """What kind of material a file is, by its name: the reading follows from it."""

    DOCUMENT = "DOCUMENT"
    DATASET = "DATASET"
    IMAGE = "IMAGE"
    VIDEO = "VIDEO"
    UNKNOWN = "UNKNOWN"


class ReadingOutcome(StrEnum):
    """What reading a source produced. Only ``READ`` means all of it was read."""

    #: Every part was read.
    READ = "READ"
    #: Some was read and some was not: a bound, an unreadable page. ``notes`` say what.
    PARTIAL = "PARTIAL"
    #: Kept, but AIA has no way to read it (an image, a video).
    UNREADABLE = "UNREADABLE"
    #: Kept, but a reader for this format is not in AIA yet.
    UNSUPPORTED = "UNSUPPORTED"
    #: The file is not what its name says, is encrypted, or is malformed.
    REFUSED = "REFUSED"


# The formats the owner chose on 2026-10-13 (plan § K2 slicing), by family. A reader
# that has not landed yet reads as UNSUPPORTED, never as a title-only card.
_FAMILIES: Final[dict[str, SourceFamily]] = {
    **dict.fromkeys(
        (".pdf", ".docx", ".doc", ".odt", ".txt", ".md", ".pptx"), SourceFamily.DOCUMENT
    ),
    **dict.fromkeys((".csv", ".xlsx", ".xls", ".ods"), SourceFamily.DATASET),
    **dict.fromkeys((".png", ".jpg", ".jpeg", ".gif", ".webp"), SourceFamily.IMAGE),
    **dict.fromkeys((".mp4", ".mov"), SourceFamily.VIDEO),
}

_MEDIA_TYPES: Final[dict[str, str]] = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".doc": "application/msword",
    ".odt": "application/vnd.oasis.opendocument.text",
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    ".txt": "text/plain",
    ".md": "text/markdown",
    ".csv": "text/csv",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".xls": "application/vnd.ms-excel",
    ".ods": "application/vnd.oasis.opendocument.spreadsheet",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
    ".mp4": "video/mp4",
    ".mov": "video/quicktime",
}


_CONTROL: Final = re.compile(r"[\x00-\x1f\x7f]+")
#: The longest name kept for an occurrence.
NAME_MAX_CHARS: Final = 160


def display_name(filename: str) -> str:
    """The name a person gave the file, as they wrote it, accents and all.

    A source's name is only ever shown: its bytes are stored under its hash, so the
    name needs no reduction to safe characters (a brief's attachment does, 18.6.6's
    rule). Kept: the last path component, without control characters, at most
    ``NAME_MAX_CHARS`` characters with the extension kept. An empty name is
    ``soubor``.
    """
    name = _CONTROL.sub("", filename.replace("\\", "/").rsplit("/", 1)[-1]).strip()
    if len(name) > NAME_MAX_CHARS:
        suffix = extension_of(name)
        if len(suffix) >= NAME_MAX_CHARS:
            suffix = ""
        name = name[: NAME_MAX_CHARS - len(suffix)].rstrip() + suffix
    return name or "soubor"


def family_of(filename: str) -> SourceFamily:
    return _FAMILIES.get(extension_of(filename), SourceFamily.UNKNOWN)


def media_type_of(filename: str) -> str:
    """What the name says the file is; nothing is ever served by it."""
    return _MEDIA_TYPES.get(extension_of(filename), "application/octet-stream")


class Locator(BaseModel):
    """Where in the original a segment stands. Numbers are 1-based, as a reader counts.

    Exactly the fields that place the segment are set: a PDF page (``page``), a table
    on it (``page``, ``table``, ``row``), a paragraph (``paragraph``), a document table
    (``table``, ``row``), a slide (``slide``), a sheet row (``sheet``, ``row``) or a
    text line (``line``). A locator with nothing set places nothing and is refused.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    page: int | None = Field(default=None, ge=1)
    paragraph: int | None = Field(default=None, ge=1)
    slide: int | None = Field(default=None, ge=1)
    table: int | None = Field(default=None, ge=1)
    sheet: str | None = Field(default=None, min_length=1, max_length=200)
    row: int | None = Field(default=None, ge=1)
    line: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def _places_something(self) -> Locator:
        if all(v is None for v in self.model_dump().values()):
            raise ValueError("a locator places its segment")
        return self


class ReadingNote(BaseModel):
    """Something a reader could not do, as a stable code the page puts into words.

    ``at`` places it where it can be placed (the page without text); ``count`` is the
    number it concerns where there is one (characters kept, pages skipped).
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    code: str = Field(min_length=1, max_length=64)
    at: Locator | None = None
    count: int | None = Field(default=None, ge=0)


class Segment(BaseModel):
    """One readable part of a source and where it stands."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    locator: Locator
    text: str


class SourceReading(BaseModel):
    """What reading one source produced.

    ``reader`` names the reader and its version (``pdf/1``), so a reading made by an
    older reader is told apart from a new one. ``notes`` say what it could not do (a
    page without text, a bound reached); ``reason`` is the stable code of an outcome
    other than ``READ``.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    outcome: ReadingOutcome
    reader: str | None = None
    reason: str | None = None
    segments: tuple[Segment, ...] = ()
    notes: tuple[ReadingNote, ...] = ()

    @model_validator(mode="after")
    def _consistent(self) -> SourceReading:
        if self.outcome is ReadingOutcome.READ and (self.reason or self.notes):
            raise ValueError("a complete reading has nothing to explain")
        if self.outcome is not ReadingOutcome.READ and not self.reason:
            raise ValueError("an incomplete reading says why")
        if self.outcome in (ReadingOutcome.READ, ReadingOutcome.PARTIAL) and not self.reader:
            raise ValueError("a reading names its reader")
        if (
            self.outcome
            in (ReadingOutcome.UNREADABLE, ReadingOutcome.UNSUPPORTED, ReadingOutcome.REFUSED)
            and self.segments
        ):
            raise ValueError("nothing read keeps no segment")
        return self

    @property
    def characters(self) -> int:
        return sum(len(s.text) for s in self.segments)


def reading_of_segments(
    reader: str,
    segments: list[Segment],
    *,
    notes: list[ReadingNote] | None = None,
    limit: int = SOURCE_TEXT_MAX_CHARS,
) -> SourceReading:
    """A reading from what a reader found: empty segments dropped, text bounded.

    Past ``limit`` characters the rest is not kept (note ``text_bound``). Any note
    makes the reading ``PARTIAL`` under the first note's code. A reader that found no
    text at all gives ``PARTIAL`` / ``no_text``: the file opened, but nothing in it
    reads as text (a scanned PDF).
    """
    kept: list[Segment] = []
    used = 0
    all_notes = list(notes or ())
    for segment in segments:
        text = segment.text.strip()
        if not text:
            continue
        if used + len(text) > limit:
            room = limit - used
            if room > 0:
                kept.append(Segment(locator=segment.locator, text=text[:room]))
            all_notes.append(ReadingNote(code="text_bound", count=limit))
            break
        kept.append(Segment(locator=segment.locator, text=text))
        used += len(text)
    if not kept:
        return SourceReading(
            outcome=ReadingOutcome.PARTIAL,
            reader=reader,
            reason="no_text",
            notes=(*all_notes, ReadingNote(code="no_text")),
        )
    if all_notes:
        return SourceReading(
            outcome=ReadingOutcome.PARTIAL,
            reader=reader,
            reason=all_notes[0].code,
            segments=tuple(kept),
            notes=tuple(all_notes),
        )
    return SourceReading(outcome=ReadingOutcome.READ, reader=reader, segments=tuple(kept))


class SourceOccurrence(BaseModel):
    """One time someone added a source: the name it came under, who, when, how."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    occurrence_id: str
    source_id: str
    filename: str
    origin: SourceOrigin
    added_by: str | None
    added_at: datetime | None


class SourceRecord(BaseModel):
    """A client's source as listed: the original's identity and what reading produced.

    The reading's segments are not here; they are read with the source alone.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    source_id: str
    client_id: str
    sha256: str
    size_bytes: int
    media_type: str
    family: SourceFamily
    filename: str
    outcome: ReadingOutcome
    reason: str | None
    reader: str | None
    characters: int
    segments: int
    occurrences: tuple[SourceOccurrence, ...]
    created_at: datetime | None

    @model_validator(mode="after")
    def _ids(self) -> SourceRecord:
        if not _ID.fullmatch(self.source_id):
            raise ValueError("a source id is SRC- and 16 hex characters")
        return self
