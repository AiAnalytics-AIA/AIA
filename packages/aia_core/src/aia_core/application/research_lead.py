"""The Research Lead ("Vedoucí výzkumu"): a researcher's conversation in a Study (ADR 0026).

The API never calls a model. A person's message is stored, the turn's context is frozen
(:func:`~aia_core.domain.research_lead.freeze_context`) and a ``research_lead`` run with one
``research_lead_turn`` step is started under the Study's design project, owned as an agent
job is (``DESIGN_PROJECT_OWNER``). The worker answers it; its reply is read from the run's
step output, never copied into the turn (the product owner, 2026-10-19).

What the Lead proposes changes nothing until a person decides, on the server:

* **An edit** is accepted or dismissed through :meth:`ResearchLead.decide_edits`: the edits
  are applied to the current working copy by the domain's rules
  (:func:`~aia_core.domain.research_lead.apply_edit`), saved, and each decision written to the
  approval ledger, in one transaction (ADR 0019 gate 1).
* **What the Lead wants to keep for all of the researcher's work** -- a personal note, a SOUL,
  USER or name change -- waits for :meth:`ResearchLead.decide_self_update`; only what stays
  inside the turn's client is applied by the turn itself (Codex on #484).
* **A prepared paid job** starts only through :meth:`ResearchLead.approve_request`, which
  holds it to the study's spend limit and writes the ledger row in the transaction that starts
  it (ADR 0026 decision 7).

Each researcher has their own Lead (the product owner, 2026-10-19): a conversation is one
researcher's in one Study, and nobody reads another's. :class:`LeadProfile` hatches and reads
the caller's Lead; its files change only through chat, by the Lead's ``self_update``.
"""

from __future__ import annotations

import json
import math
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any, Final

from sqlalchemy.orm import Session

from ..domain.analysis.steps import module_of_node
from ..domain.approval_ledger import ApprovalSubject
from ..domain.design import DESIGN_PROJECT_OWNER
from ..domain.edit_log import ActorKind, OpSource, WriteBy
from ..domain.lead_commands import MatchedCommand, match_command
from ..domain.lead_context import manifest_view, omitted_page
from ..domain.lead_digest import DigestEntry, decision_digest, edit_item
from ..domain.lead_hatch import HatchInput, HatchOutput, hatch_refusals
from ..domain.lead_research_targets import (
    DEEP_RESEARCH_RUNS,
    RUNS_FOR_TARGETS,
    FinishedRun,
    ModuleOutcome,
    deep_research_layer,
    targets_layer,
)
from ..domain.research_agents import ResearchAction, design_material, knowledge_entries
from ..domain.research_lead import (
    FOCUS_ID,
    LEAD_HARNESS_VERSION,
    LEAD_PROMPT_ID,
    MESSAGE_MAX_BYTES,
    MESSAGE_MAX_CHARS,
    MESSAGES_NOTE,
    QUEUE_MAX,
    RUNS_IN_CONTEXT,
    STAGES,
    AgentJobRequest,
    DeepResearchRetryRequest,
    DesignResearchRequest,
    InterpretationResearchRequest,
    LeadContextTooLarge,
    LeadNote,
    LeadOutput,
    LeadTurn,
    ResearcherLead,
    SelfUpdate,
    context_sha256,
    design_research_questions,
    freeze_context,
    is_text_edit,
    new_turn_id,
    notes_layer,
    readiness_layer,
    stale_files,
    take_queued,
    target_refusal,
)
from ..domain.research_template import research_template
from ..domain.scope import OrganizationContext, Permission, Study, StudyContext
from ..domain.workflow import StepRunStatus, WorkflowRunStatus
from ..domain.workflow_templates import RESEARCH, RESEARCH_LEAD
from ..domain.workspace import edited_from_current
from ..infrastructure.artifact_repository import ArtifactNotFound
from ..infrastructure.client_knowledge_repository import ClientKnowledgeRepository
from ..infrastructure.prompt_repository import PromptResolver
from ..infrastructure.researcher_lead_repository import (
    LeadAlreadyHatched,
    LeadHatchNotPending,
    LeadNotHatched,
    PendingHatch,
    ResearcherLeadRepository,
)
from ..infrastructure.scope_repository import ScopeRepository
from ..infrastructure.storage import ArtifactStore, IntegrityError, ObjectNotFound
from ..infrastructure.study_design_repository import StudyDesignRepository
from ..infrastructure.study_lead_repository import StudyLeadRepository
from ..infrastructure.study_workspace_repository import (
    StudyWorkspaceRepository,
    WorkspaceConflict,
)
from ..infrastructure.workflow_repository import BudgetWaitNotLiftable, WorkflowRepository
from .analysis_results import SourcesRefused, _external_context
from .deep_research import DeepResearchRuns
from .lead_chat_start import RunStartSettings, approve_chat_start, chat_start_decisions
from .lead_deep_research import (
    DeepResearchCardRequest,
    DeepResearchCardSettings,
    DeepResearchCardUnavailable,
    approve_deep_research_card,
)
from .research import ResearchAgentJobs, ResearchRuns, readiness_in_force, research_artifacts
from .workflows import start_workflow
from .working_copy import apply_edit_ops

__all__ = [
    "GREETING_WINDOW",
    "LeadAlreadyHatched",
    "LeadBusy",
    "LeadCardStale",
    "LeadContextTooLarge",
    "LeadDisabled",
    "LeadEditsStale",
    "LeadHatchNotPending",
    "LeadHatchRefused",
    "LeadHatchUnavailable",
    "LeadNotHatched",
    "LeadProfile",
    "LeadRejected",
    "LeadSelfUpdateDecided",
    "LeadSelfUpdateNone",
    "LeadTurnNotFound",
    "LeadTurnNotReady",
    "LeadTurnStale",
    "LeadUnavailable",
    "NotAPaidRequest",
    "ResearchLead",
    "WorkspaceConflict",
    "release_lead_budget_waits",
    "set_study_budget",
    "worker_readiness",
]

#: The ledger subjects a Lead conversation decides (the decision digest's source).
_DIGEST_SUBJECTS: Final = frozenset(
    {ApprovalSubject.LEAD_EDIT, ApprovalSubject.LEAD_JOB_REQUEST, ApprovalSubject.LEAD_SELF_UPDATE}
)
#: A greeting within this long of the Lead's last turn is a no-op: the Lead has spoken.
GREETING_WINDOW: Final = timedelta(hours=8)
#: The stage a Design Revision is submitted from when a Lead-prepared job starts, by action,
#: as the web submits it before its own buttons start the same job.
_SOURCE_STAGE: Final[dict[ResearchAction, str]] = {
    ResearchAction.ANALYZE: "brief",
    ResearchAction.AUDIENCE: "audience",
    ResearchAction.DIMENSIONS: "persona",
}


class LeadUnavailable(Exception):
    """The deployment has not switched the Lead on (``AIA_AI_RESEARCH_LEAD_ENABLED``)."""

    reason = "research_lead_unavailable"


class LeadHatchUnavailable(Exception):
    """A hatch cannot be asked of the model yet (lead-identity LI1).

    Its request needs a payer outside any client: the AIA organization the product owner
    decided on 2026-10-25 ("create the AIA organization for charges spent that dont belong to
    a single client"), which is not built. Until it is, asking is refused by name, before
    anything is sent or charged; no code writes the files instead.
    """

    reason = "lead_hatch_unavailable"


class LeadHatchRefused(Exception):
    """The hatched files hold what a personal file may not (ADR 0030 decision 3): they are
    not kept, by name, and the person writes again."""

    reason = "client_fact_in_personal_file"

    def __init__(self, files: Mapping[str, str]) -> None:
        super().__init__(f"refused: {', '.join(sorted(files))}")
        self.files = dict(files)


class LeadDisabled(LeadUnavailable):
    """A card the Lead's model prepared, approved while the Lead is switched off (Q42, D22).

    The card waits: it is approvable again once the Lead is on. Deciding a turn's stored
    edits is not refused: it calls no model and spends nothing.
    """

    reason = "research_lead_disabled"


#: The park reasons that say the worker's composition cannot answer a Lead turn: the Lead's
#: switch or keys unset there (``aia_executors.research_lead.LEAD_UNCONFIGURED``), or no AI
#: runtime at all.
WORKER_NOT_READY_REASONS: Final = frozenset(
    {"research_lead_unconfigured", "ai_runtime_unavailable"}
)


def worker_readiness(
    turns: Sequence[Mapping[str, Any]],
) -> tuple[bool | None, str | None, str | None]:
    """Whether the worker can answer a Lead turn, as far as the caller's own turns show: the
    answer, where it was read, and the reason when it is ``False``.

    There is no worker composition record yet (lead-orchestration LO12b), so the one honest
    source the API holds is this conversation's newest Lead turn a worker has decided. Parked
    or failed for a reason that names the worker's composition
    (:data:`WORKER_NOT_READY_REASONS`), the worker is not ready:
    ``(False, "newest_turn", <reason>)``. Nothing here can say a worker *is* ready -- a turn
    answered yesterday proves nothing about the worker running today -- so the answer is
    otherwise ``(None, None, None)``: unknown, never ``True``. LO12b's record replaces this.
    """
    for turn in reversed(turns):
        if turn["actor"] != "lead" or turn["status"] in ("QUEUED", "RUNNING", "CANCELLED"):
            continue
        reason = turn["reason"]
        if turn["status"] in ("WAITING", "FAILED") and reason in WORKER_NOT_READY_REASONS:
            return False, "newest_turn", str(reason)
        return None, None, None
    return None, None, None


class LeadBusy(Exception):
    """A Lead turn of this researcher in this Study is queued or running."""

    reason = "lead_busy"


class LeadQueueFull(Exception):
    """Five of this researcher's messages already wait for the Lead (ADR 0041 decision 7)."""

    reason = "lead_queue_full"


class LeadMessageNotQueued(Exception):
    """A message that is no longer waiting: answered, withdrawn, or not a message."""

    reason = "lead_message_not_queued"


class LeadTurnNotFound(LookupError):
    """No such Lead turn in the caller's own conversation on this Study."""

    reason = "lead_turn_not_found"


class LeadTurnNotReady(Exception):
    """The Lead turn has no completed output to decide on."""

    reason = "lead_turn_not_completed"


class NotAPaidRequest(Exception):
    """The turn prepared no paid job: its request only opens a stage, whose own start gates it."""

    reason = "not_a_paid_request"


class LeadSelfUpdateDecided(Exception):
    """The researcher has already accepted or dismissed this turn's waiting self-update."""

    reason = "lead_self_update_decided"


class LeadSelfUpdateNone(Exception):
    """The turn left no self-update waiting for the researcher."""

    reason = "lead_self_update_none"


class LeadEditsStale(Exception):
    """The working copy moved since the edits were shown; nothing was applied."""

    reason = "stale_revision"

    def __init__(self, current_revision: int | None) -> None:
        super().__init__("the working content changed since the edits were shown")
        self.current_revision = current_revision


class LeadTurnStale(LeadEditsStale):
    """An automatic accept of a turn whose frozen working revision is no longer the current one:
    someone saved while the Lead was working, so its edits wait for a click."""

    reason = "stale_turn"

    def __init__(self, current_revision: int | None, turn_revision: int | None) -> None:
        super().__init__(current_revision)
        self.args = ("the working content changed while the Lead was working on this turn",)
        self.turn_revision = turn_revision


class LeadCardStale(Exception):
    """A card approved after the working copy moved past the revision its turn was written from
    (lead-orchestration LO10): the job would run on a design the card was not prepared for.
    Approved again naming the current revision, it starts on that one."""

    reason = "stale_card"

    def __init__(self, current_revision: int | None, turn_revision: int | None) -> None:
        super().__init__("the working content changed since the Lead prepared this card")
        self.current_revision = current_revision
        self.turn_revision = turn_revision


class LeadRejected(ValueError):
    """A turn that cannot be stored as asked. ``reason`` is a stable word."""

    def __init__(self, message: str, *, reason: str) -> None:
        super().__init__(message)
        self.reason = reason


# --------------------------------------------------------------------------- a turn's state

#: What a Lead turn's run says, by its one step's status.
_QUEUED: Final = frozenset({StepRunStatus.BLOCKED, StepRunStatus.RUNNABLE})
_WAITING: Final = frozenset(
    {
        StepRunStatus.AWAITING_GATE,
        StepRunStatus.AWAITING_BUDGET,
        StepRunStatus.WAITING_PROVIDER,
        StepRunStatus.WAITING_CAPACITY,
        StepRunStatus.RECOVERY_REQUIRED,
    }
)


def _lead_status(step: Mapping[str, Any], last: Mapping[str, Any] | None) -> tuple[str, str | None]:
    """A Lead turn's status and its reason, from its step: QUEUED, RUNNING, COMPLETED,
    FAILED, WAITING (a parked step, with its reason code) or CANCELLED."""
    status = step["status"]
    error = (last or {}).get("error") or {}
    failure = (last or {}).get("failure_class")
    if status is StepRunStatus.SUCCEEDED:
        return "COMPLETED", None
    if status is StepRunStatus.RUNNING:
        return "RUNNING", None
    if status in _QUEUED:
        return "QUEUED", None
    if status is StepRunStatus.FAILED:
        reason = error.get("reason") or (failure.value.lower() if failure else None)
        return "FAILED", str(reason) if reason else None
    if status in _WAITING:
        reason = error.get("reason") or step.get("waiting_reason") or status.value.lower()
        return "WAITING", str(reason)
    return "CANCELLED", None


def _holds(turn: Mapping[str, Any]) -> bool:
    """Whether a Lead turn holds the conversation: queued or running.

    A turn parked for any reason does not: one that held the conversation while parked held
    it for ever when nothing released it (F4). A turn parked on the budget is sent when a
    person sets or raises the budget (:func:`release_lead_budget_waits`) or superseded by the
    next message (:meth:`ResearchLead.post`), so at most one turn waits to be paid; while it
    waits, the conversation stays open.
    """
    return turn["actor"] == "lead" and turn["status"] in ("QUEUED", "RUNNING")


def _view(
    turn: LeadTurn,
    *,
    run: Mapping[str, Any] | None,
    last: Mapping[str, Any] | None,
    decisions: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """One turn as the conversation reads it. A person's turn is COMPLETED and has no output;
    a Lead turn carries its run's state, its output once completed, and the ledger's
    decisions on its edits and its prepared job."""
    base: dict[str, Any] = {
        "turn_id": turn.turn_id,
        "sequence_no": turn.sequence_no,
        "actor": turn.actor,
        "kind": turn.kind,
        "stage": turn.stage,
        "text": turn.text,
        "focus": turn.focus,
        "run_id": turn.run_id,
        "workspace_revision": turn.workspace_revision,
        "created_at": turn.created_at,
        "created_by": turn.created_by,
        # The typed start the server matched in a person's message (LO5); its card is theirs.
        "command": turn.command,
        "status": "COMPLETED",
        "reason": None,
        "output": None,
        "changes": None,
        "dropped": [],
        "data_class": None,
        "edit_decisions": {},
        "request_decision": None,
        "self_update_decision": None,
        "self_update_pending": False,
        "self_update_waiting": None,
        # The files the turn saw; read by decide_self_update, never sent to the browser.
        "self_update_base": None,
        # Parked on the study's budget (see _holds); never sent to the browser.
        "awaiting_budget": False,
        # What waits for the researcher's yes, as the step stored it; read by
        # decide_self_update, never sent to the browser.
        "pending_self_update": None,
    }
    if turn.actor == "person":
        if turn.command is not None and decisions and decisions.get("request"):
            base["request_decision"] = {
                "status": "approved",
                "run_id": decisions["request"].get("run_id"),
                # The job was already started for this design by an earlier approval (LO5).
                "reused": bool(decisions["request"].get("reused")),
            }
        return base
    if decisions:
        base["edit_decisions"] = dict(decisions.get("edits") or {})
        request = decisions.get("request")
        if request:
            base["request_decision"] = {"status": "approved", "run_id": request.get("run_id")}
        if decisions.get("self_update"):
            base["self_update_decision"] = dict(decisions["self_update"])
    if run is None or not run.get("steps"):
        # A run this listing could not read is not reported as anything it did.
        return {**base, "status": "QUEUED"}
    step = run["steps"][0]
    status, reason = _lead_status(step, last)
    base.update(
        status=status,
        reason=reason,
        awaiting_budget=step["status"] is StepRunStatus.AWAITING_BUDGET,
    )
    out = step.get("output") or {}
    if status == "COMPLETED" and isinstance(out.get("lead_output"), dict):
        base.update(
            output=out["lead_output"],
            changes=out.get("self_update_applied"),
            dropped=list(out.get("dropped") or []),
            data_class=out.get("data_class"),
        )
        pending = out.get("self_update_pending")
        if isinstance(pending, dict):
            base["pending_self_update"] = pending
            base["self_update_pending"] = base["self_update_decision"] is None
            waiting = out.get("self_update_waiting")
            base["self_update_waiting"] = dict(waiting) if isinstance(waiting, dict) else None
            seen = out.get("self_update_base")
            base["self_update_base"] = dict(seen) if isinstance(seen, dict) else None
    return base


def release_lead_budget_waits(
    session: Session, scope: StudyContext, *, budget_before: float, note: str = ""
) -> list[str]:
    """Send the Lead turns of this Study parked at the budget cap, once a person set or raised
    the budget (the product owner, 2026-10-21, Q39: "once the budget is set or raised, it should
    automatically resend the message the researcher attempted to send in the first place").

    Called in the transaction that changed the budget, after the change. The person who set it
    is the consent: each released turn's wait is lifted through
    :meth:`WorkflowRepository.resume_budget_waits`, one approval row in the ledger naming that
    person, as every other budget lift is. Nothing is released unless the budget went up, the
    person holds ``APPROVE_BUDGET`` and the Study is open. A turn is released only when the hold
    its attempt asked for (the parked attempt's ``requested_usd``) now fits what remains; one
    whose hold would still pass the budget, or whose hold was not recorded (unknown is never
    taken to fit), stays parked with its words. Oldest first, each released turn's hold counted
    against the rest. Returns the released runs' ids.

    The study row is already locked by the change; a parked Lead run has no attempt in flight,
    so taking its lock after the study's waits on nothing that holds the study.
    """
    if not scope.has(Permission.APPROVE_BUDGET) or not scope.study_status.accepts_work:
        return []
    project_id = StudyDesignRepository(session, scope).project_id()
    if project_id is None:
        return []
    workflows = WorkflowRepository(session, scope)
    # The waiting steps themselves, oldest first: a page of the newest runs would miss a turn
    # parked behind more than a page of later ones (Codex on #547).
    waiting = workflows.steps_awaiting_budget(project_id=project_id, workflow_type=RESEARCH_LEAD)
    if not waiting:
        return []
    study = ScopeRepository(session).get_study(scope, for_update=True)
    budget_after = float(study.budget_usd)
    if budget_after <= budget_before:
        return []
    remaining = budget_after - float(study.spent_usd) - workflows.study_reserved_usd()
    asked = workflows.last_attempt_errors([step_id for _, step_id in waiting])
    released: list[str] = []
    for run_id, step_id in waiting:
        requested = _recorded_hold((asked.get(step_id) or {}).get("error", {}).get("requested_usd"))
        if requested is None or requested > remaining + 1e-9:
            continue
        workflows.lock_run(run_id)
        try:
            workflows.resume_budget_waits(
                [step_id],
                note=note,
                budget_before=budget_before,
                budget_after=budget_after,
            )
        except BudgetWaitNotLiftable:
            continue  # superseded or cancelled since it was listed
        remaining -= requested
        released.append(run_id)
    return released


def _recorded_hold(value: object) -> float | None:
    """A parked attempt's ``requested_usd`` as a hold, or None when it is not a finite,
    non-negative number of USD: NaN compares as fitting anything and a bool is an int, so either
    would be taken to fit, which is unknown scored as good."""
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    hold = float(value)
    return hold if math.isfinite(hold) and hold >= 0 else None


def set_study_budget(
    session: Session, scope: StudyContext, budget_usd: float
) -> tuple[Study, list[str]]:
    """Set the study's budget (``ScopeRepository.set_study_budget``, audited) and send the Lead
    turns that waited for it (:func:`release_lead_budget_waits`). Returns the study and the
    released runs' ids."""
    scopes = ScopeRepository(session)
    before = float(scopes.get_study(scope, for_update=True).budget_usd)
    study = scopes.set_study_budget(scope, budget_usd)
    released = release_lead_budget_waits(
        session, scope, budget_before=before, note="budget set in Nastavení → Studie"
    )
    return study, released


@dataclass(frozen=True, slots=True)
class ResearchLead:
    """The calling researcher's Lead conversation in the Study in scope."""

    session: Session
    scope: StudyContext
    #: The API's ``ai_research_lead_enabled``: off, a message is refused, never queued.
    enabled: bool = False
    #: With the API's ``ai_analysis_external_context`` on, the store a turn reads the Study's
    #: newest Design Research bundle from (evidence-integrity 7); ``None``: no external context.
    external_store: ArtifactStore | None = None
    #: The store each finished run's specification is read from for the ``targets`` layer
    #: (lead-orchestration LO5a.1); ``None``: the turn is offered no Interpretation target.
    store: ArtifactStore | None = None
    clock: Callable[[], datetime] = field(default=lambda: datetime.now(UTC))

    def _turns(self) -> StudyLeadRepository:
        return StudyLeadRepository(self.session, self.scope)

    def _workflows(self) -> WorkflowRepository:
        return WorkflowRepository(self.session, self.scope)

    # -- reading ----------------------------------------------------------------

    def _annotated(self, turns: Sequence[LeadTurn]) -> list[dict[str, Any]]:
        """``turns`` with each Lead turn's run state, output and ledger decisions: one query
        for the runs with their steps, one for the steps' last attempts, one for the ledger."""
        run_ids = [t.run_id for t in turns if t.run_id]
        runs: dict[str, dict[str, Any]] = {}
        project_id = StudyDesignRepository(self.session, self.scope).project_id()
        if run_ids and project_id is not None:
            listed = self._workflows().list_runs(
                project_id=project_id,
                workflow_type=RESEARCH_LEAD,
                run_ids=run_ids,
                steps=True,
                limit=len(run_ids),
            )
            runs = {r["run_id"]: r for r in listed}
        step_ids = [r["steps"][0]["step_id"] for r in runs.values() if r.get("steps")]
        last = self._workflows().last_attempt_errors(step_ids)
        decisions = self._workflows().lead_decisions(
            [t.turn_id for t in turns if t.actor == "lead"]
        )
        # A typed command's card is decided by its chat_start row (LO5).
        started = chat_start_decisions(
            self._workflows(), [t.turn_id for t in turns if t.command is not None]
        )
        for turn_id, done in started.items():
            decisions[turn_id] = {"request": {"run_id": done["run_id"], "reused": done["reused"]}}
        lead_ids = [t.turn_id for t in turns if t.actor == "lead"]
        answers = self._turns().answers(lead_ids)
        person_ids = [t.turn_id for t in turns if t.actor == "person" and t.kind == "message"]
        queued = {t.turn_id for t in self._turns().queued()} if person_ids else set()
        withdrawn = self._turns().withdrawn(person_ids)
        views = []
        for turn in turns:
            run = runs.get(turn.run_id) if turn.run_id else None
            step_id = run["steps"][0]["step_id"] if run and run.get("steps") else None
            view = _view(
                turn,
                run=run,
                last=last.get(step_id) if step_id else None,
                decisions=decisions.get(turn.turn_id),
            )
            # What waits and what was answered, derived from the rows (ADR 0041 decision 7).
            view["queued"] = turn.turn_id in queued
            view["withdrawn"] = turn.turn_id in withdrawn
            view["answers"] = answers.get(turn.turn_id, [])
            views.append(view)
        return views

    def state(self, *, limit: int = 100) -> dict[str, Any]:
        """This researcher's conversation in the Study, oldest first, and whether a Lead turn
        is queued or running (``busy``)."""
        stored = [t for t in self._turns().turns(limit=limit) if t.kind != "withdrawal"]
        turns = self._annotated(stored)
        busy = any(_holds(t) for t in turns)
        return {"busy": busy, "turns": turns}

    def _frozen(self, turn_id: str) -> Mapping[str, Any] | None:
        """The context the caller's own Lead turn froze at enqueue, as its step holds it;
        ``None`` when the step holds none. Another researcher's turn, or a person's, is not
        found."""
        turn = self._turns().get(turn_id)
        if turn is None or turn.actor != "lead" or turn.run_id is None:
            raise LeadTurnNotFound(turn_id)
        frozen = (self._workflows().step_input(turn.run_id, "turn") or {}).get("context")
        return frozen if isinstance(frozen, Mapping) else None

    def manifest(self, turn_id: str) -> dict[str, Any]:
        """What the caller's own Lead turn could see (Co Vedoucí vidí, plan lead-conversation
        LC2): read from the context it froze, never rebuilt from today's study.
        ``recorded: False`` when the turn's step holds no context."""
        frozen = self._frozen(turn_id)
        if frozen is None:
            return {"turn_id": turn_id, "recorded": False, "manifest": None}
        return {"turn_id": turn_id, "recorded": True, "manifest": manifest_view(frozen)}

    def omitted(
        self, turn_id: str, layer_name: str, *, after: int = 0
    ) -> tuple[list[dict[str, str]], int]:
        """The ids a layer of the caller's own Lead turn left out, from ``after``: the rest of
        what its manifest lists the first fifty of."""
        frozen = self._frozen(turn_id)
        return omitted_page(frozen, layer_name, after=after) if frozen is not None else ([], 0)

    def _completed(self, turn_id: str) -> tuple[LeadTurn, LeadOutput]:
        """The caller's own completed Lead turn and its output, or why not."""
        turn = self._turns().get(turn_id)
        if turn is None or turn.actor != "lead" or turn.run_id is None:
            raise LeadTurnNotFound(turn_id)
        view = self._annotated([turn])[0]
        if view["status"] != "COMPLETED" or not isinstance(view["output"], dict):
            raise LeadTurnNotReady("the Lead has not finished this turn")
        return turn, LeadOutput.model_validate(view["output"])

    # -- posting ----------------------------------------------------------------

    def post(
        self,
        *,
        kind: str,
        stage: str,
        text: str | None = None,
        focus: Mapping[str, str] | None = None,
    ) -> list[dict[str, Any]]:
        """Store the person's message (none for a greeting) and queue the Lead's turn.

        Needs ``EDIT_STUDY`` and ``RUN_WORKFLOW`` on an open Study, a hatched Lead and no
        Lead turn of this researcher queued or running here (:class:`LeadBusy`). A greeting
        within :data:`GREETING_WINDOW` of the Lead's last turn stores nothing and returns
        no turns. When the Lead's last turn is parked on the study's budget, a message
        supersedes it (its run cancelled, never paid; its message kept in the history the new
        turn sees) and a greeting stores nothing. The researcher's Lead row is locked first,
        so two posts at once (two tabs opening the Study) are decided one after the other:
        one greeting, never two. Returns the turns stored, as :meth:`state` reads them.

        A message that is exactly one of the composer's typed start commands
        (:func:`~aia_core.domain.lead_commands.match_command`) is not sent to the Lead at all:
        it is stored as the person's command, its card theirs, with no model in the path
        (lead-orchestration LO5) -- so it is taken while the Lead is switched off (Q43), and
        needs no hatched Lead and no free conversation (:meth:`_post_command`).
        """
        matched = match_command(text) if kind == "message" else None
        if matched is not None:
            return self._post_command(stage=stage, text=text, focus=focus, matched=matched)
        if not self.enabled:
            raise LeadUnavailable("the Research Lead is not switched on in this deployment")
        self.scope.require(Permission.EDIT_STUDY)
        self.scope.require(Permission.RUN_WORKFLOW)
        self.scope.require_open_study()
        lead = ResearcherLeadRepository(self.session, self.scope).lock()
        if lead is None:
            raise LeadNotHatched("hatch your Research Lead first")
        message, focus_ = self._checked(kind=kind, stage=stage, text=text, focus=focus)

        turns = self._turns()
        latest = turns.latest_lead_turn()
        if (
            kind == "greeting"
            and latest is not None
            and latest.created_at > self.clock() - GREETING_WINDOW
        ):
            return []
        superseded: LeadTurn | None = None
        busy = False
        if latest is not None:
            current = self._annotated([latest])[0]
            if _holds(current):
                # A message waits in the queue, stored and visible in every tab; a greeting
                # waits for the conversation to be free (ADR 0041 decision 7).
                if kind == "greeting":
                    raise LeadBusy("the Lead is still answering your last message")
                busy = True
            elif current["awaiting_budget"]:
                # A greeting never cancels the person's own waiting message.
                if kind == "greeting":
                    return []
                superseded = latest
        if busy and len(turns.queued()) >= QUEUE_MAX:
            # A free Lead answers what waits with this message; only a busy one fills up.
            raise LeadQueueFull(f"{QUEUE_MAX} of your messages already wait for the Lead")

        content, _analysis, workspace_revision = self._working_content()
        # Against the copy this message is stored with, read once: a focus valid on an earlier
        # read could name a filter another tab removed since (Codex on #624).
        self._focus_shown(focus_, content)
        stored: list[LeadTurn] = []
        if kind == "message":
            stored.append(
                turns.append(
                    actor="person",
                    kind=kind,
                    stage=stage,
                    text=message,
                    focus=focus_,
                    workspace_revision=workspace_revision,
                )
            )
        if busy:
            return self._annotated(stored)
        resent: list[LeadTurn] = []
        if superseded is not None:
            # The parked turn sent nothing and holds no reservation (a budget park spends no
            # attempt): cancelling it pays nothing, and the messages it held are answered by
            # the new turn. Nothing paid is started without this person's message.
            assert superseded.run_id is not None
            self._workflows().request_cancel(superseded.run_id, reason="lead_turn_superseded")
            held = turns.answers([superseded.turn_id]).get(superseded.turn_id, [])
            resent = [t for t in (turns.get(i) for i in held) if t is not None]
        messages = [*resent, *turns.queued()] if kind == "message" else []
        return self._annotated([*stored, self._start_turn(lead, kind, stage, focus_, messages)])

    def answer_queued(self) -> list[dict[str, Any]]:
        """Start the Lead's turn on the messages that wait, once the conversation is free:
        the next turn after one that ran while they were posted, or after one that left some
        for later. Nothing waits, the Lead is still at work, or a turn waits on the budget:
        nothing is started and no turn is returned. Any tab may ask; the researcher's Lead row
        is locked first, so two asks start one turn."""
        if not self.enabled:
            raise LeadUnavailable("the Research Lead is not switched on in this deployment")
        self.scope.require(Permission.EDIT_STUDY)
        self.scope.require(Permission.RUN_WORKFLOW)
        self.scope.require_open_study()
        lead = ResearcherLeadRepository(self.session, self.scope).lock()
        if lead is None:
            raise LeadNotHatched("hatch your Research Lead first")
        turns = self._turns()
        latest = turns.latest_lead_turn()
        if latest is not None:
            current = self._annotated([latest])[0]
            if _holds(current) or current["awaiting_budget"]:
                return []
        messages = turns.queued()
        if not messages:
            return []
        newest = messages[-1]
        return self._annotated(
            [self._start_turn(lead, "message", newest.stage, newest.focus, messages)]
        )

    def withdraw(self, turn_id: str) -> list[dict[str, Any]]:
        """Withdraw one of the caller's messages that still waits: a ``withdrawal`` row names
        it, the message stays stored, and no turn is ever sent it (ADR 0041 decision 7)."""
        self.scope.require(Permission.EDIT_STUDY)
        self.scope.require_open_study()
        ResearcherLeadRepository(self.session, self.scope).lock()
        turns = self._turns()
        message = turns.get(turn_id)
        if message is None or message.actor != "person":
            raise LeadTurnNotFound(turn_id)
        if turn_id not in {t.turn_id for t in turns.queued()}:
            raise LeadMessageNotQueued("this message no longer waits for the Lead")
        turns.append(
            actor="person",
            kind="withdrawal",
            stage=message.stage,
            parent_turn_id=turn_id,
        )
        return self._annotated([message])

    def _start_turn(
        self,
        lead: ResearcherLead,
        kind: str,
        stage: str,
        focus: dict[str, str] | None,
        messages: Sequence[LeadTurn],
    ) -> LeadTurn:
        """Freeze and queue one Lead turn answering the oldest of ``messages`` that fit layer 9
        (:func:`~aia_core.domain.research_lead.take_queued`); the rest wait, named in its view.
        One answer row per message it was sent, in its transaction."""
        turns = self._turns()
        taken = list(messages[: take_queued([str(m.text or "") for m in messages])])
        deferred = [m.turn_id for m in messages[len(taken) :]]
        waiting = {m.turn_id for m in messages}
        history = [
            t
            for t in self._annotated(turns.turns(limit=50))
            if t["turn_id"] not in waiting and not t.get("queued") and not t.get("withdrawn")
        ]
        content, analysis, workspace_revision = self._working_content()

        def shown(f: dict[str, str] | None) -> dict[str, str] | None:
            # A waiting message's focus is checked again against the copy the turn is frozen
            # with: another tab may have removed what it named since (Codex on #624). One that
            # no longer shows is left out, never sent to the model; the message still is.
            return f if f is None or target_refusal(f["id"], content) is None else None

        if taken:
            stage, focus = taken[-1].stage, shown(taken[-1].focus)
        project_id, design_revision = self._design_project(content, workspace_revision)
        if workspace_revision is None:
            # A Study with no working copy had the template saved as one for its first Design
            # Revision: the turn is frozen from that revision, and names it, so an automatic
            # accept of its text edits is not refused as written from an older copy.
            content, analysis, workspace_revision = self._working_content()
        view_extra: dict[str, Any] = {}
        if len(taken) > 1:
            view_extra = {
                "note": MESSAGES_NOTE,
                "messages": [
                    {
                        "turn_id": m.turn_id,
                        "stage": m.stage,
                        "text": m.text,
                        "focus": shown(m.focus),
                    }
                    for m in taken
                ],
            }
        if deferred:
            view_extra["queued_deferred"] = deferred
        context = self._freeze(
            lead=lead,
            history=history,
            kind=kind,
            stage=stage,
            focus=focus,
            message=taken[0].text if len(taken) == 1 else None,
            content=content,
            analysis=analysis,
            workspace_revision=workspace_revision,
            design_revision_id=design_revision.revision_id,
            view_extra=view_extra,
        )
        prompt = dict(context["layers"][0]["pin"])
        lead_turn_id = new_turn_id()
        digest = context_sha256(context)
        started = start_workflow(
            self.session,
            self.scope,
            project_id=project_id,
            revision=design_revision.revision,
            workflow_type=RESEARCH_LEAD,
            idempotency_key=f"{RESEARCH_LEAD}:{lead_turn_id}",
            metadata={
                "turn_id": lead_turn_id,
                "person_turn_id": taken[-1].turn_id if taken else None,
                "person_turn_ids": [m.turn_id for m in taken],
                "user_id": self.scope.actor_id,
                "kind": kind,
                "stage": stage,
                "context_sha256": digest,
                "harness_version": LEAD_HARNESS_VERSION,
                "prompt_version": prompt["version"],
                "prompt_origin": prompt["origin"],
                "design_revision_id": design_revision.revision_id,
            },
            step_inputs={
                "turn": {
                    "context": context,
                    "context_sha256": digest,
                    "harness_version": LEAD_HARNESS_VERSION,
                    "turn_id": lead_turn_id,
                    "user_id": self.scope.actor_id,
                    "design_revision_id": design_revision.revision_id,
                }
            },
            owner=DESIGN_PROJECT_OWNER,
        )
        turn = turns.append(
            turn_id=lead_turn_id,
            actor="lead",
            kind=kind,
            stage=stage,
            focus=focus,
            run_id=started.run_id,
            workspace_revision=workspace_revision,
            design_revision_id=design_revision.revision_id,
        )
        turns.record_answers(lead_turn_id, [m.turn_id for m in taken])
        return turn

    def _post_command(
        self,
        *,
        stage: str,
        text: str | None,
        focus: Mapping[str, str] | None,
        matched: MatchedCommand,
    ) -> list[dict[str, Any]]:
        """Store a typed start command as the person's own turn, naming the start the server
        matched. Nothing is queued and nothing is spent: its card starts the work only when the
        person approves it (:meth:`approve_request`, ledger ``chat_start``)."""
        self.scope.require(Permission.EDIT_STUDY)
        self.scope.require(Permission.RUN_WORKFLOW)
        self.scope.require_open_study()
        message, focus_ = self._checked(kind="message", stage=stage, text=text, focus=focus)
        content, _analysis, workspace_revision = self._working_content()
        self._focus_shown(focus_, content)
        turn = self._turns().append(
            actor="person",
            kind="message",
            stage=stage,
            text=message,
            focus=focus_,
            workspace_revision=workspace_revision,
            command=matched.start,
        )
        return self._annotated([turn])

    # -- deciding on what a turn proposed --------------------------------------------

    def decide_edits(
        self,
        turn_id: str,
        *,
        decision: str,
        indices: Sequence[int],
        base_revision: int | None,
        auto: bool = False,
    ) -> dict[str, Any]:
        """A person accepts or dismisses edits a Lead turn proposed (ADR 0019 gate 1).

        Needs ``EDIT_STUDY`` and ``APPROVE_GATE`` on an open Study, and the caller's own
        completed Lead turn. An accept applies the named edits, in order, to the **current**
        working content and analysis -- refused whole (:class:`LeadEditsStale`) when
        ``base_revision`` is not the current working revision -- saves the working copy once
        (``reason = "lead_edit_accepted"``) when any applied, and writes one ledger row per
        decided edit, all in one transaction under the Study's lock. An edit the content
        cannot take, or one that writes a locked Sociomap input (``sociomap_input_locked``), is
        ``refused`` with its reason and stays undecided. The applied edits are the vocabulary's
        operations, logged as the Lead's for this turn (``application/working_copy.py``,
        working-copy-edit-ops WCE2d); a copy whose ids the web keeps is settled, so a reworded
        research question keeps its links. An edit already
        decided keeps its first decision. A dismiss writes the ledger rows only.

        ``auto``: the accept is the researcher's standing choice, not a click (plan
        inline-decisions chunk 2). It is an accept, refused unless the caller's own Lead has
        ``auto_accept_text_edits`` on (``auto_accept_off``); an edit that is not a text edit
        (:func:`~aia_core.domain.research_lead.is_text_edit`) is ``refused`` as
        ``not_a_text_edit`` and stays undecided; each row it writes says ``"auto": true``. It
        is refused whole (:class:`LeadTurnStale`, ``stale_turn``) unless the turn was written
        from the current working revision: an edit made while the Lead worked is not
        overwritten without a click.
        """
        self.scope.require(Permission.EDIT_STUDY)
        self.scope.require(Permission.APPROVE_GATE)
        self.scope.require_open_study()
        if decision not in ("accept", "dismiss"):
            raise LeadRejected("an edit is accepted or dismissed", reason="invalid_decision")
        order = list(dict.fromkeys(int(i) for i in indices))
        if not order:
            raise LeadRejected("name the edits to decide", reason="invalid_decision")
        if auto:
            if decision != "accept":
                raise LeadRejected("only an accept is automatic", reason="invalid_decision")
            lead = ResearcherLeadRepository(self.session, self.scope).get()
            if lead is None or not lead.auto_accept_text_edits:
                raise LeadRejected(
                    "the researcher has not chosen to accept text edits automatically",
                    reason="auto_accept_off",
                )
        turn, output = self._completed(turn_id)
        assert turn.run_id is not None  # a completed Lead turn has its run
        self._turns().lock()
        workflows = self._workflows()
        decided = workflows.lead_decisions([turn_id]).get(turn_id, {}).get("edits", {})
        results: dict[int, dict[str, Any]] = {}
        pending: list[int] = []

        workspace = StudyWorkspaceRepository(self.session)
        working = workspace.content(self.scope)
        current = working.revision
        if decision == "accept" and not edited_from_current(
            base_revision, current, working.content, working.analysis
        ):
            raise LeadEditsStale(current)
        if auto and turn.workspace_revision != current:
            # The turn was written from an older working copy: a person's save made while the
            # Lead worked would be overwritten without a click. It waits for one.
            raise LeadTurnStale(current, turn.workspace_revision)
        # A set_n is accepted under the limits in force now, not those the turn was frozen
        # with: a version activated meanwhile is what the start will check (RQC9).
        limits, _ = readiness_in_force(self.session, self.scope)
        candidates: list[int] = []
        for index in order:
            if not 0 <= index < len(output.edits):
                results[index] = {"index": index, "status": "refused", "reason": "unknown_edit"}
                continue
            prior = decided.get(str(index))
            if prior is not None:
                results[index] = {"index": index, "status": prior["status"], "reason": None}
                continue
            if decision == "dismiss":
                pending.append(index)
                continue
            if auto and not is_text_edit(output.edits[index]):
                results[index] = {"index": index, "status": "refused", "reason": "not_a_text_edit"}
                continue
            candidates.append(index)

        revision, revision_id = current, working.revision_id
        if candidates:
            # The Lead's edits as the vocabulary's operations, each logged as the turn's
            # (working-copy-edit-ops WCE2d): the Lead wrote them, the researcher accepted them.
            batch = apply_edit_ops(
                self.session,
                self.scope,
                working,
                [output.edits[i] for i in candidates],
                by=WriteBy(ActorKind.LEAD, self.scope.actor_id, OpSource.LEAD_TURN, turn_id),
                reason="lead_edit_accepted",
                sample_size=limits.sample_size,
            )
            for position, index in enumerate(candidates):
                reason = batch.refused.get(position)
                if reason is not None:
                    results[index] = {"index": index, "status": "refused", "reason": reason}
                else:
                    pending.append(index)
            if batch.saved is not None:
                revision, revision_id = batch.saved.revision, batch.saved.revision_id
        for index in pending:
            workflows.record_lead_edit_decision(
                turn.run_id,
                turn_id=turn_id,
                index=index,
                decision=decision,
                op=output.edits[index].op,
                workspace_revision=revision if decision == "accept" else None,
                workspace_revision_id=revision_id if decision == "accept" else None,
                auto=auto,
            )
            results[index] = {
                "index": index,
                "status": "accepted" if decision == "accept" else "dismissed",
                "reason": None,
            }
        return {"workspace_revision": revision, "results": [results[i] for i in order]}

    def decide_self_update(self, turn_id: str, *, decision: str) -> dict[str, Any]:
        """The researcher accepts or dismisses what a Lead turn wanted to keep for all of
        their work: personal notes, and changes to SOUL, USER or the name (Codex on #484).

        These load into every client's studies, so the Lead's choice of scope is not trusted
        to keep a client's facts inside its client: they wait for this. Needs ``EDIT_STUDY``
        and ``APPROVE_GATE`` on an open Study and the caller's own completed Lead turn with a
        self-update waiting. Under the researcher's Lead row lock, in one transaction: an
        accept applies it (each replaced file text kept as a revision), and either decision is
        written to the approval ledger once; a second is :class:`LeadSelfUpdateDecided`.

        A file (SOUL, USER, the name) changed since the turn saw it is not replaced: accepting
        an older turn would put back what a newer one wrote. Its notes still apply (they have
        no base), the decision is recorded with the stale files, and ``stale`` names them: the
        researcher asks the Lead again.
        """
        self.scope.require(Permission.EDIT_STUDY)
        self.scope.require(Permission.APPROVE_GATE)
        self.scope.require_open_study()
        if decision not in ("accept", "dismiss"):
            raise LeadRejected("a self-update is accepted or dismissed", reason="invalid_decision")
        turn = self._turns().get(turn_id)
        if turn is None or turn.actor != "lead" or turn.run_id is None:
            raise LeadTurnNotFound(turn_id)
        leads = ResearcherLeadRepository(self.session, self.scope)
        current = leads.lock()
        if current is None:
            raise LeadNotHatched("hatch your Research Lead first")
        view = self._annotated([turn])[0]
        if view["status"] != "COMPLETED":
            raise LeadTurnNotReady("the Lead has not finished this turn")
        if view["self_update_decision"] is not None:
            raise LeadSelfUpdateDecided("this turn's self-update is already decided")
        pending = view["pending_self_update"]
        if not isinstance(pending, dict):
            raise LeadSelfUpdateNone("this turn left nothing waiting")
        applied = None
        stale: list[str] = []
        if decision == "accept":
            files = {"name": current.name, "soul": current.soul, "user": current.user}
            stale = stale_files(pending, view["self_update_base"], files)
            update = SelfUpdate.model_validate(pending).model_copy(
                update=dict.fromkeys(stale, None)
            )
            applied = leads.apply_self_update(update, source_turn_id=turn_id).model_dump(
                mode="json"
            )
        recorded = self._workflows().record_lead_self_update_decision(
            turn.run_id, turn_id=turn_id, decision=decision, applied=applied, stale=stale
        )
        if not recorded:  # pragma: no cover - the Lead row lock serialises deciders
            raise LeadSelfUpdateDecided("this turn's self-update is already decided")
        return {
            "status": "accepted" if decision == "accept" else "dismissed",
            "changes": applied,
            "stale": stale,
        }

    def approve_request(
        self,
        turn_id: str,
        *,
        confirm_cost_usd: float | None,
        reservation_usd: float | None,
        run_start: RunStartSettings | None = None,
        wallet_enabled: bool = False,
        workspace_revision: int | None = None,
        retry_run_id: str | None = None,
        deep_research: DeepResearchCardSettings | None = None,
    ) -> dict[str, Any]:
        """A person approves the paid job a Lead turn prepared, and it starts (ADR 0026
        decision 7).

        A Deep Research card (``design_research``, ``interpretation_research``,
        ``deep_research_retry``) starts on the server too (lead-orchestration LO5a.2, amending
        D7 for those kinds): :func:`~aia_core.application.lead_deep_research.
        approve_deep_research_card`, on ``deep_research``'s prices, mode and store, with the
        same once-only rule, Lead switch and (for a design card) LO10 check as a design job.

        The person's own typed command (a person's turn naming a ``command``, LO5) is approved
        here too, by :func:`~aia_core.application.lead_chat_start.approve_chat_start`: not Lead
        output, so not refused while the Lead is off (D22), under the same threshold, the
        wallet when ``wallet_enabled`` and the ledger row ``chat_start``. ``run_start`` is the
        deployment's run settings a typed research run starts under; ``retry_run_id`` the run a
        typed analysis retry's card named (another is refused, ``AnalysisRetryTargetMoved``).

        Needs ``EDIT_STUDY``, ``RUN_WORKFLOW`` and ``APPROVE_GATE`` on an open Study, and the
        caller's own completed Lead turn whose request is an ``agent_job``; any other request
        only opens a stage (:class:`NotAPaidRequest`). The card is the Lead model's output, as
        the stored turn says (:func:`_model_prepared`), so with the Lead switched off it is
        refused (:class:`LeadDisabled`, Q42) before anything is written; it waits until the
        Lead is on again. A card approved before the switch-off answers with its job, as any
        repeated approval does. The card is bound to the working revision its turn was written
        from (LO10): when anything but this turn's own accepted edits has saved the working copy
        since, it is refused (:class:`LeadCardStale`) unless ``workspace_revision`` names the
        current revision, the person's yes to running it on the design as it is now. Its
        ceiling is the design job's
        reservation (``reservation_usd``: a primary and one repair). At or above the study's
        spend limit it needs ``confirm_cost_usd`` at least the ceiling
        (:class:`CostConfirmationRequired`); with a limit and no reservation configured it is
        refused as unknown (:class:`CostCeilingUnknown`), never let through as zero. The
        working content is submitted as a Design Revision, the job started on it and the
        approval written to the ledger, in one transaction. Approved once: asked again, the
        same job is returned.
        """
        self.scope.require(Permission.EDIT_STUDY)
        self.scope.require(Permission.RUN_WORKFLOW)
        self.scope.require(Permission.APPROVE_GATE)
        self.scope.require_open_study()
        stored = self._turns().get(turn_id)
        if stored is not None and stored.actor == "person" and stored.command is not None:
            self._turns().lock()

            def submit(source_stage: str) -> Any:
                content, _analysis, workspace_revision = self._working_content()
                return self._submit_design(content, workspace_revision, source_stage=source_stage)

            return approve_chat_start(
                self.session,
                self.scope,
                stored,
                submit_design=submit,
                confirm_cost_usd=confirm_cost_usd,
                reservation_usd=reservation_usd,
                run_start=run_start,
                wallet_enabled=wallet_enabled,
                retry_run_id=retry_run_id,
            )
        turn, output = self._completed(turn_id)
        assert turn.run_id is not None
        request = output.request
        card = isinstance(
            request,
            DesignResearchRequest | InterpretationResearchRequest | DeepResearchRetryRequest,
        )
        if not isinstance(request, AgentJobRequest) and not card:
            raise NotAPaidRequest("this turn prepared no paid job")
        self._turns().lock()
        workflows = self._workflows()
        approved = workflows.lead_decisions([turn_id]).get(turn_id, {}).get("request")
        if approved:
            # Approved before any switch-off: the job exists and is answered as it is, so a
            # retry after a lost response is never misreported as refused (review of #561).
            run = (
                DeepResearchRuns(self.session, self.scope).get(str(approved["run_id"]))
                if card
                else ResearchAgentJobs(self.session, self.scope).get(str(approved["run_id"]))
            )
            return {
                "run_id": run["run_id"],
                "design_revision_id": run["metadata"]["design_revision_id"],
                "status": run["status"].value,
                **(
                    {
                        "purpose": run["metadata"].get("purpose"),
                        "research_run_id": (run["metadata"].get("target") or {}).get(
                            "research_run_id"
                        ),
                    }
                    if card
                    else {}
                ),
            }
        # Q42: only an approval that would create a job is held by the switch, before anything
        # is submitted, created, written or held.
        if _model_prepared(turn) and not self.enabled:
            raise LeadDisabled("the Research Lead is switched off; its card waits until it is on")
        if isinstance(
            request,
            DesignResearchRequest | InterpretationResearchRequest | DeepResearchRetryRequest,
        ):
            return self._approve_deep_research(
                turn,
                request,
                deep_research=deep_research,
                confirm_cost_usd=confirm_cost_usd,
                wallet_enabled=wallet_enabled,
                workspace_revision=workspace_revision,
            )
        assert isinstance(request, AgentJobRequest)
        # Read once: the revision checked is the one submitted, so a save landing after the
        # check leaves the next card stale and never runs this job on an unchecked design.
        content, _analysis, current = self._working_content()
        if workspace_revision != current and not self._only_own_accepts(turn, current):
            raise LeadCardStale(current, turn.workspace_revision)

        # The confirmation threshold's one rule, the job start's own (lead-orchestration LO15):
        # asked here before the design is submitted, and again by the start, which records the
        # job's spend row; this turn's approval row carries the same figures.
        jobs = ResearchAgentJobs(self.session, self.scope, reservation_usd=reservation_usd)
        confirmed = jobs.spend_gate(confirm_cost_usd)
        spend: dict[str, float] | None = None
        if confirmed is not None:
            assert confirm_cost_usd is not None
            spend = {
                "ceiling_usd": confirmed[0],
                "limit_usd": confirmed[1],
                "confirmed_usd": confirm_cost_usd,
            }

        revision = self._submit_design(
            content,
            current,
            source_stage=_SOURCE_STAGE.get(request.action, "questionnaire"),
        )
        started = jobs.start(
            design_revision_id=revision.revision_id,
            action=request.action,
            instruction=request.why,
            confirm_cost_usd=confirm_cost_usd,
        )
        workflows.record_lead_job_approval(
            turn.run_id,
            turn_id=turn_id,
            agent_run_id=started.run_id,
            design_revision_id=revision.revision_id,
            action=request.action.value,
            # A job that already existed was confirmed (or not) when it was created; this
            # approval confirmed no new spend, so its row records none.
            spend=spend if started.created else None,
        )
        return {
            "run_id": started.run_id,
            "design_revision_id": revision.revision_id,
            "status": started.run["status"].value,
        }

    def _approve_deep_research(
        self,
        turn: LeadTurn,
        request: DeepResearchCardRequest,
        *,
        deep_research: DeepResearchCardSettings | None,
        confirm_cost_usd: float | None,
        wallet_enabled: bool,
        workspace_revision: int | None,
    ) -> dict[str, Any]:
        """A Deep Research card's start (LO5a.2). A design card researches the working content
        the card was prepared on (LO10: the turn's working revision, else stale unless the
        person names the current one), submitted as its Design Revision; an Interpretation or a
        retry card reads no working content."""
        if deep_research is None:
            raise DeepResearchCardUnavailable("no Deep Research start is composed here")
        content: dict[str, Any] | None = None
        current: int | None = None
        if isinstance(request, DesignResearchRequest):
            content, _analysis, current = self._working_content()
            if workspace_revision != current and not self._only_own_accepts(turn, current):
                raise LeadCardStale(current, turn.workspace_revision)

        def submit() -> Any:
            assert content is not None
            return self._submit_design(content, current, source_stage="plan")

        return approve_deep_research_card(
            self.session,
            self.scope,
            turn,
            request,
            frozen=self._frozen(turn.turn_id),
            submit_design=submit,
            settings=deep_research,
            confirm_cost_usd=confirm_cost_usd,
            wallet_enabled=wallet_enabled,
        )

    # -- helpers ----------------------------------------------------------------

    def _only_own_accepts(self, turn: LeadTurn, current: int | None) -> bool:
        """Whether every save of the working copy since ``turn`` was written is an accept of
        this turn's own edits: accepting what a card came with does not make it stale."""
        since = turn.workspace_revision or 0
        if current is None or current <= since:
            return True
        prefix = f"{turn.turn_id}:"
        own = {
            json.loads(entry.comment or "{}").get("workspace_revision")
            for entry in self._workflows().ledger({ApprovalSubject.LEAD_EDIT})
            if entry.subject_id.startswith(prefix) and entry.decision == "accept"
        }
        return all(r in own for r in range(since + 1, current + 1))

    @staticmethod
    def _checked(
        *, kind: str, stage: str, text: str | None, focus: Mapping[str, str] | None
    ) -> tuple[str | None, dict[str, str] | None]:
        if kind not in ("message", "greeting"):
            raise LeadRejected("a turn is a message or a greeting", reason="invalid_lead_turn")
        if stage not in STAGES:
            raise LeadRejected(f"unknown stage {stage!r}", reason="invalid_lead_turn")
        message = (text or "").strip() or None
        if kind == "message" and message is None:
            raise LeadRejected("a message needs its text", reason="invalid_lead_turn")
        if kind == "greeting" and message is not None:
            raise LeadRejected("a greeting carries no text", reason="invalid_lead_turn")
        if kind == "greeting" and focus is not None:
            raise LeadRejected("a greeting carries no focus", reason="invalid_lead_turn")
        if message is not None and len(message) > MESSAGE_MAX_CHARS:
            raise LeadRejected(
                f"a message is at most {MESSAGE_MAX_CHARS} characters", reason="invalid_lead_turn"
            )
        if message is not None and len(message.encode("utf-8")) > MESSAGE_MAX_BYTES:
            raise LeadRejected(
                f"a message is at most {MESSAGE_MAX_BYTES} bytes of UTF-8",
                reason="message_too_long",
            )
        focus_ = None
        if focus is not None:
            focus_ = {"id": str(focus.get("id") or ""), "label": str(focus.get("label") or "")}
            if not FOCUS_ID.fullmatch(focus_["id"]):
                raise LeadRejected(
                    "a focus names an element of a stage screen: a known kind and an id",
                    reason="invalid_lead_turn",
                )
        return message, focus_

    @staticmethod
    def _focus_shown(focus: Mapping[str, str] | None, content: Mapping[str, Any]) -> None:
        """A person's focus names what ``content``, the working copy the turn is stored with,
        shows (artifact-audience AUD1): an audience filter it does not store is refused by
        name, never sent to the model."""
        if focus is None:
            return
        reason = target_refusal(focus["id"], content)
        if reason is not None:
            raise LeadRejected(
                f"the focus {focus['id']!r} names nothing the working copy shows ({reason})",
                reason="invalid_lead_turn",
            )

    def _working_content(self) -> tuple[dict[str, Any], dict[str, Any] | None, int | None]:
        working = StudyWorkspaceRepository(self.session).content(self.scope)
        if working.content is None:
            return research_template(), None, None
        return dict(working.content), working.analysis, working.revision

    def _submit_design(
        self, content: dict[str, Any], workspace_revision: int | None, *, source_stage: str
    ) -> Any:
        """The working content as a Design Revision naming the working revision it is (ADR 0026
        decision 5). A Study with no working copy yet has its template saved as one first."""
        designs = StudyDesignRepository(self.session, self.scope)
        if workspace_revision is None:
            revision, _ = designs.submit_as_working_copy(content=content, source_stage=source_stage)
        else:
            revision, _ = designs.submit(
                content=content, source_stage=source_stage, workspace_revision=workspace_revision
            )
        return revision

    def _design_project(
        self, content: dict[str, Any], workspace_revision: int | None
    ) -> tuple[str, Any]:
        """The Study's design project and its newest Design Revision.

        A Study with no Design Revision gets its working content submitted as the first one
        (``source_stage = "brief"``): the one writer of a Study's design, with its validation,
        creates the project the turn's run is owned by. Nothing new can write a design.
        """
        designs = StudyDesignRepository(self.session, self.scope)
        latest = designs.latest()
        if latest is None:
            latest = self._submit_design(content, workspace_revision, source_stage="brief")
        project_id = designs.project_id()
        assert project_id is not None  # a revision exists, so its project does
        return project_id, latest

    def _freeze(
        self,
        *,
        lead: ResearcherLead,
        history: Sequence[Mapping[str, Any]],
        kind: str,
        stage: str,
        focus: dict[str, str] | None,
        message: str | None,
        content: dict[str, Any],
        analysis: dict[str, Any] | None,
        workspace_revision: int | None,
        design_revision_id: str,
        view_extra: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        s = self.scope
        prompt = PromptResolver(self.session, s.organization_id).pin_for(LEAD_PROMPT_ID)
        notes: list[LeadNote] = ResearcherLeadRepository(self.session, s).notes_for_study()
        knowledge, omitted = knowledge_entries(ClientKnowledgeRepository(self.session).for_study(s))
        scopes = ScopeRepository(self.session)
        study = scopes.get_study(s)
        client = scopes.client_of_study(s)
        project_id = StudyDesignRepository(self.session, s).project_id()
        limits, _ = readiness_in_force(self.session, s)
        runs = (
            self._workflows().list_runs(
                project_id=project_id, workflow_type=RESEARCH, limit=RUNS_IN_CONTEXT
            )
            if project_id is not None
            else []
        )
        digest, digest_classes = self._decision_digest(history, focus)
        targets = self._targets()
        return freeze_context(
            prompt=prompt,
            lead={
                "name": lead.name,
                "soul": lead.soul,
                "user": lead.user,
                "notes": notes_layer([n.model_dump(mode="json") for n in notes]),
                "first_conversation": not self._turns().has_spoken_before(),
            },
            knowledge=knowledge,
            omitted_knowledge_ids=omitted,
            study={
                "name": study.name,
                "client_name": client.name,
                "budget_usd": study.budget_usd,
                "spent_usd": study.spent_usd,
                "spend_confirm_usd": study.spend_confirm_usd,
            },
            design={
                "workspace_revision": workspace_revision,
                "design_revision_id": design_revision_id,
                "content": design_material(content),
                "analysis": analysis,
                # The ids a focus names, shown beside the content that may not store them.
                **(
                    {"research_questions": listed}
                    if (listed := design_research_questions(content))
                    else {}
                ),
                # The valid n as readiness reads it (RQC9): what a set_n is grounded against.
                "readiness": readiness_layer(limits.sample_size, limits.methodology_version),
            },
            runs=[
                {
                    "run_id": r["run_id"],
                    "status": r["status"].value,
                    "design_revision_id": r["metadata"].get("design_revision_id"),
                }
                for r in runs
            ],
            view={
                "kind": kind,
                "stage": stage,
                "focus": focus,
                "message": message,
                **dict(view_extra or {}),
            },
            conversation=_conversation(history),
            external=self._external(),
            memory=digest,
            memory_classes=digest_classes,
            deep_research=self._deep_research((targets or {}).get("candidates") or ()),
            targets=targets,
        )

    def _deep_research(self, candidates: Sequence[Mapping[str, Any]]) -> dict[str, Any] | None:
        """The ``deep_research`` layer: this Study's newest Deep Research runs, read through
        the Study (``DeepResearchRuns``), with their steps; ``None`` when it has none."""
        runs = DeepResearchRuns(self.session, self.scope)
        listed = runs.runs(limit=DEEP_RESEARCH_RUNS)
        if not listed:
            return None
        return deep_research_layer([runs.get(r["run_id"]) for r in listed], candidates)

    def _targets(self) -> dict[str, Any] | None:
        """The ``targets`` layer: the Interpretation Research candidates over this Study's newest
        completed research runs, each read from its own pinned specification (verified by its
        SHA-256 as it is read); ``None`` without a store or a completed run."""
        if self.store is None:
            return None
        research = ResearchRuns(self.session, self.scope)
        artifacts = research_artifacts(self.session, self.scope, self.store)
        finished: list[FinishedRun] = []
        unreadable: list[str] = []
        # Completed runs are selected in the query, before the limit: newer runs that failed or
        # still run never hide an older completed one (review of #925).
        completed = research.runs(limit=RUNS_FOR_TARGETS, statuses=(WorkflowRunStatus.COMPLETED,))
        for listed in completed:
            try:
                finished.append(_finished_run(research.get(listed["run_id"]), artifacts))
            except (ArtifactNotFound, IntegrityError, ObjectNotFound):
                # A specification that does not read offers no target and is said so, never a
                # stop (as the external layer's bundle); its CORRUPT mark commits with the turn.
                unreadable.append(str(listed["run_id"]))
        if not finished and not unreadable:
            return None
        return targets_layer(finished, unreadable=unreadable)

    def _decision_digest(
        self, history: Sequence[Mapping[str, Any]], focus: Mapping[str, str] | None
    ) -> tuple[dict[str, Any], list[str | None]]:
        """What this researcher's conversation decided, from the ledger (ADR 0041 decision 4):
        every decision on one of their Lead turns, named by the item its edit touched where the
        turn is within ``history``, and the proposals in ``history`` still waiting for one;
        with the class each turn whose text the digest carries was sent as."""
        mine = set(self._turns().lead_turn_ids())
        outputs = {t["turn_id"]: t["output"] for t in history if isinstance(t.get("output"), dict)}
        decided: list[DigestEntry] = []
        for entry in self._workflows().ledger(_DIGEST_SUBJECTS):
            turn_id, _, index = entry.subject_id.rpartition(":")
            if entry.subject is ApprovalSubject.LEAD_EDIT and turn_id in mine:
                edits = (outputs.get(turn_id) or {}).get("edits") or []
                at = int(index) if index.isdigit() else len(edits)
                item = edit_item(edits[at]) if at < len(edits) else None
                kind = "edit"
            elif entry.subject is not ApprovalSubject.LEAD_EDIT and entry.subject_id in mine:
                turn_id, item = entry.subject_id, None
                kind = "job" if entry.subject is ApprovalSubject.LEAD_JOB_REQUEST else "self_update"
            else:
                continue
            decided.append(
                DigestEntry(kind, item, entry.decision, turn_id, ledger_id=entry.decision_id)
            )
        waiting: list[DigestEntry] = []
        for turn in history:
            output = turn.get("output")
            if turn["actor"] != "lead" or not isinstance(output, dict):
                continue
            decided_edits = turn.get("edit_decisions") or {}
            waiting.extend(
                DigestEntry("edit", edit_item(edit), None, turn["turn_id"], index=i)
                for i, edit in enumerate(output.get("edits") or [])
                if str(i) not in decided_edits
            )
            request = output.get("request")
            # Only a prepared agent job is decided through the ledger; a run or Deep Research
            # card is started from its own screen and never waits here.
            if (
                isinstance(request, dict)
                and request.get("kind") == "agent_job"
                and turn.get("request_decision") is None
            ):
                waiting.append(DigestEntry("job", None, None, turn["turn_id"], index=0))
        named = [focus["id"]] if focus and focus.get("id") else []
        digest = decision_digest(decided, waiting, named=named)
        # The class of every turn whose text a line carries (an item named by a turn's edit).
        sent = {t["turn_id"]: t.get("data_class") for t in history}
        carried = {
            line["turn"]
            for group in ("named", "undecided", "latest")
            for line in digest[group]
            if line.get("item") is not None
        }
        return digest, [sent.get(turn_id) for turn_id in sorted(carried)]

    def _external(self) -> dict[str, Any] | None:
        """The newest Design Research bundle's public findings, pinned and seal-verified as the
        analysis reads them; ``None`` when switched off or the Study has none. A bundle that does
        not read is said so in the layer, never read as no context and never stopping the turn."""
        if self.external_store is None:
            return None
        pin = ResearchRuns(self.session, self.scope).design_research_pin()
        if pin is None:
            return None
        try:
            lines = _external_context(self.session, self.scope, self.external_store, pin)
        except SourcesRefused as refused:
            return {"pin": pin, "lines": [], "unavailable": refused.reason}
        return {"pin": pin, "lines": list(lines)}


def _finished_run(run: Mapping[str, Any], artifacts: Any) -> FinishedRun:
    """A completed research run as the candidates read it: the specification its compile step
    pinned, and the artifacts its aggregate, Sociomap and analysis steps produced."""
    produced: dict[str, Mapping[str, Any]] = {
        s["node_key"]: s.get("output") or {}
        for s in run["steps"]
        if s["status"] is StepRunStatus.SUCCEEDED and (s.get("output") or {}).get("artifact_id")
    }
    compiled = produced.get("compile")
    specification = (
        artifacts.read_json(str(compiled["artifact_id"])).get("specification") or {}
        if compiled is not None
        else {}
    )
    modules = [
        ModuleOutcome(module, str(out["artifact_id"]), str(out.get("outcome") or ""))
        for key, out in produced.items()
        if (module := module_of_node(key)) is not None
    ]
    aggregate, sociomap = produced.get("aggregate"), produced.get("sociomap")
    return FinishedRun(
        run_id=str(run["run_id"]),
        specification=specification,
        aggregate_artifact_id=str(aggregate["artifact_id"]) if aggregate else None,
        sociomap_artifact_id=str(sociomap["artifact_id"]) if sociomap else None,
        modules=modules,
    )


def _model_prepared(turn: LeadTurn) -> bool:
    """Whether a card is the Lead model's output, read from the stored turn and never from a
    request body (D22): a Lead turn's request is what the worker's model answered."""
    return turn.actor == "lead"


def _conversation(history: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Earlier turns as the Lead is shown them: a person's text, or a Lead's reply with the
    class its turn was sent as. A Lead turn without a reply (queued, parked, failed) is not
    a turn of the conversation."""
    turns: list[dict[str, Any]] = []
    for t in history:
        if t["actor"] == "person" and t.get("text"):
            turns.append({"actor": "person", "stage": t["stage"], "text": t["text"]})
        elif t["actor"] == "lead" and isinstance(t.get("output"), dict):
            turns.append(
                {
                    "actor": "lead",
                    "stage": t["stage"],
                    "reply": t["output"].get("reply"),
                    "data_class": t.get("data_class"),
                }
            )
    return turns


@dataclass(frozen=True, slots=True)
class LeadProfile:
    """The calling researcher's own Lead, read-only but for hatching (product owner,
    2026-10-19): its files change only through chat."""

    session: Session
    scope: OrganizationContext

    def read(self) -> dict[str, Any]:
        repo = ResearcherLeadRepository(self.session, self.scope)
        lead = repo.get()
        if lead is None:
            return {"hatched": False, "lead": None, "pending_hatch": _hatch(repo.pending_hatch())}
        return {"hatched": True, "lead": _profile(lead, repo.active_notes())}

    def hatch(self) -> dict[str, Any]:
        repo = ResearcherLeadRepository(self.session, self.scope)
        lead = repo.hatch()
        return {"hatched": True, "lead": _profile(lead, repo.active_notes())}

    # -- hatching (lead-identity LI1) ----------------------------------------

    def request_hatch(self, hatch_input: Mapping[str, Any]) -> dict[str, Any]:
        """Ask the model to write the caller's Lead files. Refused by name until the AIA
        organization exists to pay for it; the input is validated first, so a person learns of
        a wrong input before the payer's absence."""
        HatchInput.model_validate(hatch_input)
        if ResearcherLeadRepository(self.session, self.scope).get() is not None:
            raise LeadAlreadyHatched("the Lead is already hatched")
        raise LeadHatchUnavailable("hatching has no payer outside a client yet")

    def accept_hatch(self, hatch_id: str) -> dict[str, Any]:
        """ "Přijmout": the caller's pending hatch becomes their Lead (ADR 0030 decision 2).
        The model's answer is checked again here, as it is kept: its bounds and ADR 0030
        decision 3's personal-file check against the organization's clients as they are now,
        the chosen name included (review of #919)."""
        repo = ResearcherLeadRepository(self.session, self.scope)
        pending = repo.pending_hatch()
        if pending is None or pending.hatch_id != hatch_id or pending.output is None:
            raise LeadHatchNotPending(hatch_id)
        hatch = HatchInput.model_validate(pending.input)
        output = HatchOutput.model_validate(pending.output)
        refused = hatch_refusals(output, repo.organization_client_names(), name=hatch.name)
        if refused:
            raise LeadHatchRefused(refused)
        lead = repo.accept_hatch(hatch_id, name=hatch.name, soul=output.soul, user=output.user)
        return {
            "hatched": True,
            "lead": _profile(lead, repo.active_notes()),
            "greeting": output.greeting,
        }

    def discard_hatch(self, hatch_id: str) -> dict[str, Any]:
        """ "Zadat znovu": the pending hatch is set aside; the person writes again, and a new
        request is a new paid request with its own cost shown."""
        ResearcherLeadRepository(self.session, self.scope).discard_hatch(hatch_id)
        return self.read()

    def set_preferences(self, *, auto_accept_text_edits: bool) -> dict[str, Any]:
        """The caller sets their own Lead's preferences (plan inline-decisions chunk 2): the
        standing choice to have its text edits accepted without a click. Audited."""
        repo = ResearcherLeadRepository(self.session, self.scope)
        lead = repo.set_preferences(auto_accept_text_edits=auto_accept_text_edits)
        return {"hatched": True, "lead": _profile(lead, repo.active_notes())}


def _hatch(pending: PendingHatch | None) -> dict[str, Any] | None:
    if pending is None:
        return None
    return {
        "hatch_id": pending.hatch_id,
        "input": pending.input,
        "output": pending.output,
        "created_at": pending.created_at,
    }


def _profile(lead: ResearcherLead, notes: Sequence[LeadNote]) -> dict[str, Any]:
    return {
        "lead_id": lead.lead_id,
        "name": lead.name,
        "hatched_at": lead.hatched_at,
        "updated_at": lead.updated_at,
        "files": {"soul": lead.soul, "user": lead.user},
        "preferences": {"auto_accept_text_edits": lead.auto_accept_text_edits},
        "memories": [
            {
                "memory_id": n.memory_id,
                "scope": n.scope,
                "client_id": n.client_id,
                "client_name": n.client_name,
                "text": n.text,
                "created_at": n.created_at,
                "source_turn_id": n.source_turn_id,
            }
            for n in notes
        ],
    }
