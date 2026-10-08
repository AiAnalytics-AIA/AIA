"""A cited work's identity and standing: its DOI, and whether it was retracted (chunk 46).

A finding is only as good as its source, and a retracted paper is a known bad one. When a
captured source names its DOI, code asks the scholarly indexes the composition has
(OpenAlex, Crossref) what has happened to that work since, and records the answer on the
source; the merge then quarantines a finding resting on a retracted or withdrawn work
(``QuarantineReason.RETRACTED_SOURCE``). A correction or an expression of concern is shown,
not quarantined: the work still stands, with a notice beside it.

Unknown is never "not retracted" (CLAUDE.md § 8): a status nobody could read is
``UNKNOWN``, and it quarantines nothing *and* claims nothing. ``NONE_RECORDED`` means an
index answered and listed no notice -- a statement about the index, not a guarantee.

Pure: no I/O. The lookups are the executors', through the gate.
"""

from __future__ import annotations

import re
from datetime import date, datetime
from enum import StrEnum
from typing import Final

from pydantic import BaseModel, ConfigDict, Field

__all__ = [
    "QUARANTINING",
    "WORKS_VERSION",
    "WorkNotice",
    "WorkStatus",
    "WorkStatusRecord",
    "normalise_doi",
    "resolve_status",
]

#: The rule's version: what quarantines, and how two indexes' answers combine.
WORKS_VERSION: Final = "aia-works-1"

#: A DOI as Crossref registers it: the 10. prefix, a registrant code, a suffix.
_DOI: Final = re.compile(r"^10\.\d{4,9}/\S{1,300}$")
#: The resolver and scheme prefixes a page may write before the DOI itself.
_PREFIX: Final = re.compile(r"^(?:https?://(?:dx\.)?doi\.org/|doi:\s*|info:doi/)", re.I)


def normalise_doi(raw: str) -> str | None:
    """The DOI in ``raw``, lower-cased and without a resolver prefix; ``None`` if none.

    DOIs are case-insensitive (the DOI Handbook, § 2.4), so two spellings of one work
    are one key. Anything that is not a well-formed DOI is ``None``, never a guess.
    """
    text = _PREFIX.sub("", raw.strip()).strip().rstrip(".,;")
    return text.lower() if _DOI.match(text) else None


class WorkStatus(StrEnum):
    """What has happened to a work since publication, most severe first."""

    RETRACTED = "retracted"
    WITHDRAWN = "withdrawn"
    EXPRESSION_OF_CONCERN = "expression_of_concern"
    CORRECTED = "corrected"
    #: An index answered and lists no notice for the work.
    NONE_RECORDED = "none_recorded"
    #: No index could answer: unknown, which is not "not retracted".
    UNKNOWN = "unknown"


#: The statuses that quarantine a finding resting on the work.
QUARANTINING: Final = frozenset({WorkStatus.RETRACTED, WorkStatus.WITHDRAWN})
_SEVERITY: Final = {s: i for i, s in enumerate(WorkStatus)}


class _Closed(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class WorkNotice(_Closed):
    """One notice an index lists against the work: what kind, which record, from whom."""

    status: WorkStatus
    notice_doi: str | None = Field(default=None, max_length=320)
    #: Who recorded it: the publisher, or Retraction Watch (as Crossref says).
    source: str = Field(max_length=60)
    issued: date | None = None


class WorkStatusRecord(_Closed):
    """A work's standing as the composition's indexes answered, on the day they did."""

    doi: str = Field(max_length=320)
    status: WorkStatus
    notices: tuple[WorkNotice, ...] = ()
    #: The connectors that answered (``openalex-works-1``, ``crossref-works-1``).
    checked_by: tuple[str, ...]
    checked_at: datetime
    version: str = WORKS_VERSION

    @property
    def quarantines(self) -> bool:
        return self.status in QUARANTINING


def resolve_status(
    doi: str,
    answers: dict[str, tuple[WorkNotice, ...] | None],
    *,
    retracted_flags: dict[str, bool | None] | None = None,
    checked_at: datetime,
) -> WorkStatusRecord:
    """One record from every index's answer: the most severe status any index states.

    ``answers`` maps a connector to the notices it listed, or ``None`` when it could not
    answer (not sent, failed, unknown). ``retracted_flags`` maps a connector to a plain
    retracted flag where that is all it says (OpenAlex's ``is_retracted``): ``True`` is a
    retraction with no notice record, ``False`` is no notice, ``None`` is no answer.
    Indexes disagree in both directions; a retraction stated by any one of them stands.
    """
    flags = retracted_flags or {}
    notices: list[WorkNotice] = []
    answered: list[str] = []
    for connector, listed in answers.items():
        if listed is not None:
            answered.append(connector)
            notices.extend(listed)
    for connector, flag in flags.items():
        if flag is None:
            continue
        if connector not in answered:
            answered.append(connector)
        if flag:
            notices.append(WorkNotice(status=WorkStatus.RETRACTED, source=connector))
    if not answered:
        status = WorkStatus.UNKNOWN
    elif notices:
        status = min((n.status for n in notices), key=_SEVERITY.__getitem__)
    else:
        status = WorkStatus.NONE_RECORDED
    return WorkStatusRecord(
        doi=doi,
        status=status,
        notices=tuple(notices),
        checked_by=tuple(sorted(answered)),
        checked_at=checked_at,
    )
