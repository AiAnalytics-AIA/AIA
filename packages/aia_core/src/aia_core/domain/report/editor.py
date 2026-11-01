"""The report editor's lines, versions and sessions, as rules (artifact-report RPT8c), pure.

A **line** starts at a draft code composed: its koncept 1 is the composer's artifact, whose id is
the line's id. Each save the Document Server sends is the line's next version, koncept N+1. A
recompose by code is a new composer artifact, so it starts a new line and never touches another
line's versions (/pmstatus (a)). The line with the newest version opens by default.

A line's **editing session** has one document key: the line, the version it opened on and the
session's number, within ONLYOFFICE's 128 characters of ``[0-9A-Za-z._=-]``. While a session is
open every config for the line carries its key, so a second researcher joins the same
co-editing session; a status 6 force-save stores the next version and keeps the key; a status 2
or 4 closes it, and so does the next open once no callback came for :data:`SESSION_IDLE`. The
next session opens on the newest version, under a new key.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum
from typing import Final

#: The report variants the editor opens. The client report is one since RPT13 (B2 (a), the product
#: owner, 2026-10-26): its saved versions are judged by the client deliverable's checks at approval.
EDITABLE_VARIANTS: Final = frozenset({"internal", "context", "client"})
#: A saved version's artifact type, by the variant it was saved from.
EDIT_ARTIFACT_TYPES: Final = {
    "internal": "research_internal_docx_edit",
    "context": "research_internal_docx_with_research_edit",
    "client": "research_client_docx_edit",
}
#: What a version changed in what code wrote (``saved_changes.changes_payload``), beside it.
CHANGES_ARTIFACT_TYPE: Final = "research_report_changes"
#: An open session no callback reached for this long is closed by the next open.
SESSION_IDLE: Final = timedelta(hours=24)
#: ONLYOFFICE's ``document.key``: at most 128 of these characters.
KEY: Final = re.compile(r"[0-9A-Za-z._=-]{1,128}")
_SHA256: Final = re.compile(r"[0-9a-f]{64}")


class CallbackAction(StrEnum):
    #: Status 1: being edited; the session is in use.
    OPEN = "open"
    #: Status 6: a force-save (the timed autosave, or a person's save): store, keep the key.
    STORE = "store"
    #: Status 2: everyone left with changes: store, then close.
    STORE_AND_CLOSE = "store_and_close"
    #: Status 4: everyone left with no change: close, nothing stored.
    CLOSE = "close"
    #: Status 3 and 7: the Document Server failed to save; recorded, nothing stored.
    LOG = "log"


_ACTIONS: Final = {
    1: CallbackAction.OPEN,
    2: CallbackAction.STORE_AND_CLOSE,
    3: CallbackAction.LOG,
    4: CallbackAction.CLOSE,
    6: CallbackAction.STORE,
    7: CallbackAction.LOG,
}


def callback_action(status: int) -> CallbackAction:
    """What a callback's ``status`` asks; any status outside ONLYOFFICE's is ``ValueError``."""
    try:
        return _ACTIONS[status]
    except KeyError:
        raise ValueError(f"no callback status {status!r}") from None


def document_key(line_id: str, version_sha256: str, session_no: int) -> str:
    """The key of a line's ``session_no``-th session, opened on the version ``version_sha256``."""
    if not _SHA256.fullmatch(version_sha256) or session_no < 1:
        raise ValueError("a key names a version by its SHA-256 and a session from 1")
    key = f"{line_id}.{version_sha256[:40]}.{session_no}"
    if not KEY.fullmatch(key):
        raise ValueError(f"not a document key: {key!r}")
    return key


@dataclass(frozen=True)
class SessionState:
    """A line's editing session as recorded."""

    document_key: str
    session_no: int
    last_seen_at: datetime
    closed_at: datetime | None = None


def reuse_session(current: SessionState | None, now: datetime) -> bool:
    """Whether the next config for a line joins ``current``: it is open and a callback or a
    config reached it within :data:`SESSION_IDLE`."""
    return (
        current is not None
        and current.closed_at is None
        and now - current.last_seen_at < SESSION_IDLE
    )


@dataclass(frozen=True)
class LineHead:
    """A line and its newest version."""

    line_id: str
    koncept: int
    version_id: str
    saved_at: datetime


def default_line(lines: Iterable[LineHead]) -> LineHead | None:
    """The line whose newest version is newest by its stored time; on a tie, the one with more
    versions, then the line id, so the choice never depends on the order read."""
    return max(lines, key=lambda h: (h.saved_at, h.koncept, h.line_id), default=None)


#: A page's id for its edit reports: random, the page's own, within the key's characters.
PAGE: Final = re.compile(r"[0-9A-Za-z_-]{8,64}")
#: The most pages one session keeps edit reports for: a reload is a new page, so a person's
#: session sees a few; beyond this a new page's report is refused (RPT8f).
MAX_PAGES_PER_SESSION: Final = 64


@dataclass(frozen=True, slots=True)
class EditMark:
    """The newest edit start one page reported in an open session (RPT8f): its sequence, the
    page's own count from 1, and when AIA received it, by AIA's clock."""

    document_key: str
    page: str
    seq: int
    received_at: datetime


@dataclass(frozen=True, slots=True)
class SeenEdit:
    """The edit start the approving page last made: its session's key, the page, the sequence."""

    document_key: str
    page: str
    seq: int


class UnsavedEdits(StrEnum):
    #: The approving page made an edit AIA has not received: its report is in flight.
    NOT_RECEIVED = "edit_not_received"
    #: An edit AIA received is later than the last change the version holds.
    NOT_SAVED = "edit_not_saved"


def unsaved_edits(
    content_at: datetime | None, marks: Iterable[EditMark], seen: SeenEdit | None
) -> UnsavedEdits | None:
    """Why a version whose saves hold changes up to ``content_at`` (the latest ``lastsave`` of a
    save of its bytes, kept no later than AIA's receipt of that save; ``None`` for koncept 1 or a
    save that said none) does not hold every edit of the line's open sessions (``marks``) and the
    one the approving page saw (``seen``); ``None`` when it does. An edit counts as held only when
    AIA received its report no later than ``content_at``: received after the person typed, so the
    edit came first. A save made while the report was in flight holds it only once a later save
    says a later ``lastsave``: late, never early. Unknown is never held."""
    marks = list(marks)
    if seen is not None:
        own = next(
            (m for m in marks if (m.document_key, m.page) == (seen.document_key, seen.page)), None
        )
        if own is None or own.seq < seen.seq:
            return UnsavedEdits.NOT_RECEIVED
    if any(content_at is None or m.received_at > content_at for m in marks):
        return UnsavedEdits.NOT_SAVED
    return None
