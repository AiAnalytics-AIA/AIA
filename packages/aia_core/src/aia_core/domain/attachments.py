"""A research Study's brief attachments: what is kept of a file a person adds (ADR 0018).

The brief can carry files (a client's presentation, a data sheet) whose text the
analysis reads. 18.6.6 stored them in its working tree and served them by name to
anyone who knew it (``ui_server.py:1020-1045,1712-1715``). In AIA the bytes are an
artifact of the Study's working project, in AIA's storage, read only through the
Study; the brief keeps the :class:`AttachmentRecord`.

The rules are the unit's -- 25 MiB, a name reduced to safe characters, the first
6 000 characters of text as the analysis' context, ``text_extracted`` true only
when text was read -- so a record means what it meant in 18.6.6. What changed is
where the bytes live and who can reach them.

Pure: no I/O.
"""

from __future__ import annotations

import re
from pathlib import PurePosixPath
from typing import Final, Literal

from pydantic import BaseModel, ConfigDict

__all__ = [
    "ATTACHMENT_ARTIFACT_TYPE",
    "ATTACHMENT_MAX_BYTES",
    "ATTACHMENT_STAGE",
    "CONTEXT_EXCERPT_CHARS",
    "TEXT_MAX_CHARS",
    "AttachmentRecord",
    "AttachmentRejected",
    "attachment_record",
    "content_type_of",
    "extension_of",
    "safe_filename",
    "validate_attachment",
]

#: The unit's own ceiling on one attachment (``ui_server.py:1023``).
ATTACHMENT_MAX_BYTES: Final = 25 * 1024 * 1024
#: How much of the text a record carries for the analysis (``context_excerpt``).
CONTEXT_EXCERPT_CHARS: Final = 6000
#: How much text is read at most, as the unit's ``data_library._extract_text``.
TEXT_MAX_CHARS: Final = 250_000
#: ``project_artifacts.artifact_type`` of an attachment's bytes.
ATTACHMENT_ARTIFACT_TYPE: Final = "STUDY_ATTACHMENT"
#: The stage an attachment belongs to: the brief.
ATTACHMENT_STAGE: Final = "BRIEF"

_UNSAFE: Final = re.compile(r"[^A-Za-z0-9._ -]+")

# What the recorded content type says about a file; nothing is served by it (a
# download is always ``application/octet-stream``, as the unit served it).
_CONTENT_TYPES: Final = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".xlsm": "application/vnd.ms-excel.sheet.macroEnabled.12",
    ".csv": "text/csv",
    ".tsv": "text/tab-separated-values",
    ".txt": "text/plain",
    ".md": "text/markdown",
    ".json": "application/json",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
    ".mp4": "video/mp4",
    ".mov": "video/quicktime",
}


class AttachmentRejected(ValueError):
    """The file cannot become an attachment."""

    def __init__(self, message: str, *, reason: str) -> None:
        super().__init__(message)
        self.reason = reason


def safe_filename(name: str) -> str:
    """The file's base name reduced to safe characters, exactly as the unit reduced it.

    Only the last path component counts; everything outside ``A-Z a-z 0-9 . _ -``
    and space becomes ``_``, the result is cut to 160 characters, and an empty one
    is ``attachment`` (``ui_server.py:1024-1026``). AIA never uses the name as a
    path -- the bytes are stored by artifact id -- so it is only what people see.
    """
    base = PurePosixPath(str(name or "attachment")).name
    return _UNSAFE.sub("_", base)[:160] or "attachment"


def extension_of(filename: str) -> str:
    """The lower-case extension with its dot (``.pdf``), or an empty string."""
    return PurePosixPath(filename).suffix.lower()


def content_type_of(filename: str) -> str:
    """The media type recorded for a file, by its extension."""
    return _CONTENT_TYPES.get(extension_of(filename), "application/octet-stream")


def validate_attachment(filename: str, data: bytes) -> str:
    """The safe name of a file that may be attached; :class:`AttachmentRejected` otherwise."""
    if not data:
        raise AttachmentRejected("the attachment is empty", reason="empty")
    if len(data) > ATTACHMENT_MAX_BYTES:
        raise AttachmentRejected("one attachment may be at most 25 MB", reason="too_large")
    return safe_filename(filename)


class AttachmentRecord(BaseModel):
    """What the brief keeps of one attached file (``briefing.attachments[]``).

    The keys the stages read are the unit's (``kind``, ``filename``, ``size_bytes``,
    ``sha256``, ``extension``, ``text_extracted``, ``context_excerpt``);
    ``attachment_id`` names the artifact, which only the Study's download route
    serves. A record never carries a URL: where a file is served from is the
    API's business, not the brief's.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: Literal["file"] = "file"
    attachment_id: str
    filename: str
    extension: str
    content_type: str
    size_bytes: int
    sha256: str
    text_extracted: bool
    context_excerpt: str


def attachment_record(
    *, attachment_id: str, filename: str, size_bytes: int, sha256: str, text: str
) -> AttachmentRecord:
    """The record of a stored attachment and the text read from it (``""``: none)."""
    return AttachmentRecord(
        attachment_id=attachment_id,
        filename=filename,
        extension=extension_of(filename),
        content_type=content_type_of(filename),
        size_bytes=size_bytes,
        sha256=sha256,
        text_extracted=bool(text),
        context_excerpt=text[:CONTEXT_EXCERPT_CHARS],
    )
