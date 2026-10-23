"""What a deleted client's kept rows may still say (settings-backends SB5; MVPQ-07: kept rows
are content-free -- identifiers, codes, digests, numbers and times; no text, no client name).

:func:`rename` replaces a deleted client's and its studies' names with their ids, inside any
string; :func:`content_free` then erases every string that is not an AIA identifier, an
enumerated code, a digest or a time. Numbers, booleans and nulls stay. Pure.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from enum import StrEnum
from typing import Any, Final

from .client_sources import ReadingOutcome, SourceFamily, SourceOrigin
from .knowledge import KnowledgeAuthor, KnowledgeDecision, KnowledgeKind
from .residency import DataClass
from .scope import ClientStatus, OrganizationRole, StudyKind, StudyStatus
from .workflow import AttemptStatus, ReservationStatus, StepRunStatus, WorkflowRunStatus

__all__ = ["AUDIT_ACTIONS", "ERASED", "ID_PREFIXES", "content_free", "rename"]

ERASED: Final = "erased"

#: The prefixes AIA's own identifiers carry (``new_*_id`` and the repositories' ids). A
#: string of another shape -- "SKODA", "Coca-Cola" -- is text and is erased.
ID_PREFIXES: Final = frozenset(
    {
        "ART", "ATT", "AUE", "CALL", "CLI", "CNF", "CON", "CWJ", "DRP", "DRS", "DRT", "EOB",
        "EOP", "EV", "FWJ", "GAP", "GATE", "IND", "KNF", "KNL", "KNP", "KNW", "LDT", "LEAD",
        "LMM", "LRV", "MTV", "ORG", "PL", "PRJ", "PRM", "PV", "REV", "ROW", "RSV", "RUN", "SMK",
        "SNP", "SRC", "SRO", "STP", "STU", "TOOL", "USR", "WAL", "WRK",
    }
)  # fmt: skip
_ID: Final = re.compile(r"^(?P<prefix>[A-Z]{2,5})-[0-9A-Za-z]{4,64}$")
#: The codes an audit row is written under (``access_audit.action``); one inside a payload is
#: the code's word, not the client's. Held to the repositories' ``action=`` literals by
#: test_content_free.py::test_every_audit_action_the_code_writes_is_a_kept_code.
AUDIT_ACTIONS: Final = frozenset(
    {
        "AIA_SESSION", "AIA_SESSION_DENIED", "CLIENT_BUDGET_CHANGED", "CLIENT_CONTACT_ADDED",
        "CLIENT_CONTACT_CHANGED", "CLIENT_CONTACT_REMOVED", "CLIENT_CREATED", "CLIENT_DELETED",
        "CLIENT_DELETION_OBJECTS", "CLIENT_KNOWLEDGE_AUTHORED", "CLIENT_KNOWLEDGE_DECIDED",
        "CLIENT_KNOWLEDGE_FOLDER_CREATED", "CLIENT_KNOWLEDGE_FOLDER_DELETED",
        "CLIENT_KNOWLEDGE_FOLDER_RENAMED", "CLIENT_KNOWLEDGE_LABEL_CHANGED",
        "CLIENT_KNOWLEDGE_LABEL_CREATED", "CLIENT_KNOWLEDGE_LABEL_DELETED",
        "CLIENT_KNOWLEDGE_ORGANIZED", "CLIENT_KNOWLEDGE_SELECTED", "CLIENT_KNOWLEDGE_UNSELECTED",
        "CLIENT_PROFILE_CHANGED", "CLIENT_RULES_CHANGED", "CLIENT_SOURCE_ADDED",
        "CLIENT_SOURCE_MARKED_INTERNAL",
        "CLIENT_SOURCE_REREAD", "CLIENT_SOURCE_UNMARKED_INTERNAL", "CLIENT_STATUS_CHANGED",
        "DR_SETTING_APPROVED", "DR_SETTING_PROPOSAL_DECLINED", "DR_SETTING_PROPOSAL_WITHDRAWN",
        "DR_SETTING_PROPOSED", "DR_SETTING_WITHDRAWN",
        "DR_TEST_POLICY_APPROVED", "DR_TEST_POLICY_PROPOSED", "DR_TEST_POLICY_WITHDRAWN",
        "IDENTITY_SUBJECT_CLEARED", "LEAD_ERASED", "LEAD_SEALED", "LEAD_UNSEALED", "MEMBER_ADDED",
        "MEMBER_DEACTIVATED", "MEMBER_REACTIVATED", "MEMBER_ROLE_DENIED", "METHODOLOGIST_GRANTED",
        "METHODOLOGIST_REVOKED", "METHODOLOGY_ACTIVATED", "METHODOLOGY_PROPOSED",
        "METHODOLOGY_RESET", "ORGANIZATION_CREATED", "PERMISSION_DENIED", "PROMPT_ACTIVATED",
        "PROMPT_RESET_TO_BASELINE", "PROMPT_VERSION_CREATED", "RESEARCH_LEAD_PREFERENCES_SET",
        "SELF_APPROVAL_CONFIGURED", "STUDY_BUDGET_CHANGED", "STUDY_CREATED",
        "STUDY_SPEND_CONFIRM_CHANGED", "STUDY_STATUS_CHANGED", "USER_DEACTIVATED",
        "WORKSPACE_MIGRATED",
    }
)  # fmt: skip
#: A kept code is a value of one of the code's own vocabularies (ARCHIVED, ADMIN, READ,
#: CLIENT_DELETED); a string's shape decides nothing: "ACME_SECRET" and "SKODA" are text.
_ENUMS: Final[tuple[type[StrEnum], ...]] = (
    ClientStatus,
    OrganizationRole,
    StudyKind,
    StudyStatus,
    WorkflowRunStatus,
    StepRunStatus,
    AttemptStatus,
    ReservationStatus,
    ReadingOutcome,
    SourceFamily,
    SourceOrigin,
    KnowledgeAuthor,
    KnowledgeDecision,
    KnowledgeKind,
    DataClass,
)
_WORDS: Final = frozenset(m.value for e in _ENUMS for m in e) | AUDIT_ACTIONS
_DIGEST: Final = re.compile(r"^[0-9a-f]{12,128}$")
_TIME: Final = re.compile(r"^\d{4}-\d{2}-\d{2}(?:[T ][0-9:.]+(?:Z|[+-]\d{2}:?\d{2})?)?$")
#: A name shorter than this is not searched for inside other text: "S" is in every id.
_MIN_NAME: Final = 4


def _kept(text: str) -> bool:
    m = _ID.match(text)
    if m and m.group("prefix") in ID_PREFIXES:
        return True
    return bool(text in _WORDS or _DIGEST.match(text) or _TIME.match(text))


def rename(value: Any, names: Mapping[str, str]) -> Any:
    """``value`` with each of ``names`` (a name -> its id) replaced by its id: a whole string,
    or, for a name of four characters or more, as a whole word inside a longer one (never
    part of another word: "Pilot" is not in "Pilotní"); nested. A string that is itself an id,
    a code, a digest or a time is never rewritten."""
    if isinstance(value, str):
        if value in names:
            return names[value]
        if _kept(value):
            return value
        for name in sorted((n for n in names if len(n) >= _MIN_NAME), key=len, reverse=True):
            value = re.sub(rf"(?<!\w){re.escape(name)}(?!\w)", names[name], value)
        return value
    if isinstance(value, list):
        return [rename(v, names) for v in value]
    if isinstance(value, dict):
        return {k: rename(v, names) for k, v in value.items()}
    return value


def content_free(value: Any) -> Any:
    """``value`` with every string that is no AIA id, code, digest or time replaced by
    :data:`ERASED`, nested; numbers, booleans and nulls stay; keys stay (they are the code's)."""
    if isinstance(value, str):
        return value if _kept(value) else ERASED
    if isinstance(value, list):
        return [content_free(v) for v in value]
    if isinstance(value, dict):
        return {k: content_free(v) for k, v in value.items()}
    return value
