"""A person's review of a run's key findings (artifact-analysis ANL11, research build spec szz/A7).

A key finding a model wrote is a proposal until a person decides on it: accepted as written,
edited (its wording replaced, its cited claims kept), or dropped. Each decision is one row in the
approval ledger (subject ``analysis_finding``, ``<run>:<module>:<index>``); a later row replaces an
earlier one, and ``undone`` takes the finding back to undecided. Nothing is overwritten.

A decision is bound to the module outcome it was made on, by that stored artifact's id: it applies
wherever that outcome is shown, on the run it was made on and on an analysis retry that reuses the
outcome, and to nothing else, so a replaced outcome is never read as reviewed.

An edit may change words, never numbers: every number in the new wording must be backed by a claim
the finding already cites, the rule :func:`~aia_core.domain.analysis.draft.uncovered_numbers`
holds a model's draft to, so a person cannot type a number the evidence gate never admitted. A
range or bound the cited claims' cells or the original wording write (``18-29``) stays allowed.

No I/O.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Final

from ..approval_ledger import ApprovalSubject, LedgerEntry
from .draft import uncovered_numbers
from .modules import AnalysisModuleId

__all__ = [
    "MAX_WORDING",
    "FindingDecision",
    "FindingKey",
    "FindingReview",
    "review_comment",
    "reviews_of",
    "wording_problem",
]

#: The longest edited wording kept, in characters (a key finding is a sentence or two).
MAX_WORDING: Final = 2000


class FindingDecision(StrEnum):
    """What one ledger row decided about a finding. ``undone`` withdraws the decision before it."""

    ACCEPTED = "accepted"
    EDITED = "edited"
    DROPPED = "dropped"
    UNDONE = "undone"


@dataclass(frozen=True, slots=True, order=True)
class FindingKey:
    """One key finding of a run: its module and its place in that module's stored list."""

    module: AnalysisModuleId
    index: int

    def subject_id(self, run_id: str) -> str:
        return f"{run_id}:{self.module.value}:{self.index}"

    @classmethod
    def of_subject(cls, subject_id: str) -> FindingKey | None:
        """The finding a ledger row names (of whichever run), or ``None`` for a malformed one."""
        parts = subject_id.split(":")
        if len(parts) != 3 or not parts[0] or not parts[2].isdigit():
            return None
        try:
            return cls(AnalysisModuleId(parts[1]), int(parts[2]))
        except ValueError:
            return None


@dataclass(frozen=True, slots=True)
class FindingReview:
    """A finding's decision in force: accepted, edited (with its wording) or dropped."""

    key: FindingKey
    decision: FindingDecision
    wording: str | None
    decided_by: str
    decided_at: datetime
    self_approved: bool


def review_comment(artifact_id: str, wording: str | None) -> str:
    """What a review row keeps in its comment: the module outcome it was made on, and an edit's
    wording."""
    return json.dumps({"artifact_id": artifact_id, "wording": wording}, ensure_ascii=False)


def reviews_of(
    entries: Iterable[LedgerEntry], outcomes: Mapping[AnalysisModuleId, str]
) -> dict[FindingKey, FindingReview]:
    """Each finding's decision in force over the module outcomes shown (``outcomes``: each
    module's stored artifact id), from the study's review rows: only rows made on that very
    outcome count, the newest wins, and a finding whose newest row is ``undone`` has none. A
    finding with no row is absent: unknown, never read as accepted."""
    rows = sorted(
        (e for e in entries if e.subject is ApprovalSubject.ANALYSIS_FINDING),
        key=lambda e: e.decision_id,
    )
    found: dict[FindingKey, FindingReview] = {}
    for entry in rows:
        key = FindingKey.of_subject(entry.subject_id)
        comment = json.loads(entry.comment) if entry.comment else {}
        if key is None or comment.get("artifact_id") != outcomes.get(key.module):
            continue
        decision = FindingDecision(entry.decision)
        if decision is FindingDecision.UNDONE:
            found.pop(key, None)
            continue
        wording = comment.get("wording")
        found[key] = FindingReview(
            key=key,
            decision=decision,
            wording=wording if decision is FindingDecision.EDITED else None,
            decided_by=entry.approver_user_id,
            decided_at=entry.created_at,
            self_approved=entry.self_approved,
        )
    return found


def wording_problem(
    wording: str, *, cited_values: Sequence[float], names: Sequence[str]
) -> tuple[float, ...] | str | None:
    """Why an edited wording cannot stand, or ``None``: ``"empty"``, ``"too_long"``, or the
    numbers in it that no claim the finding cites backs (``names``: the cited claims' cells and
    the original wording, whose ranges and bounds stay allowed)."""
    text = wording.strip()
    if not text:
        return "empty"
    if len(text) > MAX_WORDING:
        return "too_long"
    return uncovered_numbers(text, cited_values, names) or None
