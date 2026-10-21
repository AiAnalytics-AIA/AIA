"""What the approval ledger records decisions about: its closed set of subjects (ADR 0019).

The approval ledger is AIA's append-only record of every decision a person makes between
themselves and the AI: a gate cleared, an artifact signed off, a budget lifted, a spend
confirmed, a proposal accepted. Each row names its **subject**, one of :class:`ApprovalSubject`;
its table's CHECK constraint admits exactly these values (``infrastructure/tables.py``), and
every writer names its subject through this enum, never as a string of its own
(``make layer_check``), so a subject written in one module and matched in another cannot drift
(ARCHITECTURE.md A6).

The set is extended **once** for the MVP's lane (migration M3, ``lead-orchestration`` LO16, the
lane's first migration): the seven subjects of :data:`LANE_M3_SUBJECTS` are admitted before any
of their writers exist, so no later migration edits the same constraint (``mvp-development-plan``
§4). Each names the chunk that writes it; until that chunk lands nothing writes the subject.

No I/O: stdlib and Pydantic only.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Final

from pydantic import BaseModel, ConfigDict

__all__ = [
    "LANE_M3_SUBJECTS",
    "SUBJECTS",
    "ApprovalSubject",
    "LedgerEntry",
    "SubjectSpec",
    "subject_check_sql",
]


class ApprovalSubject(StrEnum):
    """What one ledger row decided on. The value is the stored ``subject_type``."""

    GATE = "gate"
    ARTIFACT = "artifact"
    BUDGET = "budget"
    SPEND = "spend"
    AI_PROPOSAL = "ai_proposal"
    DESIGN_RESEARCH = "design_research"
    ANSWERABILITY = "answerability"
    LEAD_EDIT = "lead_edit"
    LEAD_JOB_REQUEST = "lead_job_request"
    LEAD_SELF_UPDATE = "lead_self_update"
    # -- the lane's migration M3 (lead-orchestration LO16): admitted, written by later chunks
    WALLET = "wallet"
    LEAD_PLAN = "lead_plan"
    PLAN_STEP = "plan_step"
    CHAT_START = "chat_start"
    DATA_CONTRACT = "data_contract"
    MAP_SNAPSHOT = "map_snapshot"
    SOCIOMAP_UNLOCK = "sociomap_unlock"


@dataclass(frozen=True, slots=True)
class SubjectSpec:
    """One subject: what its ``subject_id`` names and the chunk (or decision) that writes it."""

    subject: ApprovalSubject
    subject_id: str
    written_by: str


#: Every subject, in the order the CHECK constraint lists them.
SUBJECTS: Final[tuple[SubjectSpec, ...]] = (
    SubjectSpec(ApprovalSubject.GATE, "the gate", "ADR 0019 gate decisions"),
    SubjectSpec(ApprovalSubject.ARTIFACT, "the artifact", "ADR 0019 gate 3, report approval"),
    SubjectSpec(ApprovalSubject.BUDGET, "the waiting step", "a study or client budget lift"),
    SubjectSpec(ApprovalSubject.SPEND, "the run", "ADR 0019 gate 2, a spend confirmation"),
    SubjectSpec(ApprovalSubject.AI_PROPOSAL, "the agent job's run", "an agent proposal's accept"),
    SubjectSpec(
        ApprovalSubject.DESIGN_RESEARCH, "the selection", "a Design Research proposal's accept"
    ),
    SubjectSpec(ApprovalSubject.ANSWERABILITY, "the run", "an answerability acknowledgement"),
    SubjectSpec(ApprovalSubject.LEAD_EDIT, "<turn_id>:<index>", "ADR 0026, a Lead edit decided"),
    SubjectSpec(ApprovalSubject.LEAD_JOB_REQUEST, "the Lead turn", "ADR 0026, a prepared job"),
    SubjectSpec(ApprovalSubject.LEAD_SELF_UPDATE, "the Lead turn", "ADR 0026, a self-update"),
    SubjectSpec(ApprovalSubject.WALLET, "the wallet raise", "lead-orchestration LO1 (ADR 0028)"),
    SubjectSpec(ApprovalSubject.LEAD_PLAN, "the plan", "lead-orchestration LO4 (ADR 0028)"),
    SubjectSpec(ApprovalSubject.PLAN_STEP, "the plan step", "lead-orchestration LO3 (ADR 0028)"),
    SubjectSpec(
        ApprovalSubject.CHAT_START, "the run", "lead-orchestration LO5 (ADR 0028 decision 3)"
    ),
    SubjectSpec(
        ApprovalSubject.DATA_CONTRACT, "the data contract", "client-data-in-analysis 2 (ADR 0027)"
    ),
    SubjectSpec(ApprovalSubject.MAP_SNAPSHOT, "the map snapshot", "report-delivery RD4"),
    SubjectSpec(
        ApprovalSubject.SOCIOMAP_UNLOCK,
        "the working revision unlocked",
        "working-copy-edit-ops WCE8 (ADR 0029 decision 8)",
    ),
)

#: The seven subjects migration M3 admits for the MVP's lane, before any of their writers.
LANE_M3_SUBJECTS: Final = frozenset(
    {
        ApprovalSubject.WALLET,
        ApprovalSubject.LEAD_PLAN,
        ApprovalSubject.PLAN_STEP,
        ApprovalSubject.CHAT_START,
        ApprovalSubject.DATA_CONTRACT,
        ApprovalSubject.MAP_SNAPSHOT,
        ApprovalSubject.SOCIOMAP_UNLOCK,
    }
)


def subject_check_sql(subjects: Iterable[ApprovalSubject] | None = None) -> str:
    """The CHECK constraint's condition over ``subjects`` (every subject by default), in the
    order :data:`SUBJECTS` lists them: ``subject_type in ('gate','artifact',…)``."""
    wanted = set(ApprovalSubject) if subjects is None else set(subjects)
    listed = ",".join(f"'{s.subject.value}'" for s in SUBJECTS if s.subject in wanted)
    return f"subject_type in ({listed})"


class LedgerEntry(BaseModel):
    """One ledger row as a reader of a study's decisions sees it."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    decision_id: int
    subject: ApprovalSubject
    subject_id: str
    run_id: str | None
    decision: str
    approver_user_id: str
    self_approved: bool
    comment: str
    created_at: datetime
