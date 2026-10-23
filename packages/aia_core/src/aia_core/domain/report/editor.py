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

#: The report variants the editor opens; the client report is never one (refused by name).
EDITABLE_VARIANTS: Final = frozenset({"internal", "context"})
#: A saved version's artifact type, by the variant it was saved from.
EDIT_ARTIFACT_TYPES: Final = {
    "internal": "research_internal_docx_edit",
    "context": "research_internal_docx_with_research_edit",
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
