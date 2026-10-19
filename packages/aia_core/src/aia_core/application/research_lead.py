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

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any, Final

from sqlalchemy.orm import Session

from ..domain.design import DESIGN_PROJECT_OWNER
from ..domain.research_agents import ResearchAction, design_material, knowledge_entries
from ..domain.research_lead import (
    FOCUS_ID,
    LEAD_HARNESS_VERSION,
    LEAD_PROMPT_ID,
    MESSAGE_MAX_CHARS,
    STAGES,
    AgentJobRequest,
    LeadContextTooLarge,
    LeadNote,
    LeadOutput,
    LeadTurn,
    Refused,
    ResearcherLead,
    SelfUpdate,
    apply_edit,
    context_sha256,
    freeze_context,
    is_text_edit,
    new_turn_id,
    notes_layer,
    stale_files,
)
from ..domain.research_template import research_template
from ..domain.run_cost import CeilingUnknown
from ..domain.scope import OrganizationContext, Permission, StudyContext
from ..domain.workflow import StepRunStatus
from ..domain.workflow_templates import RESEARCH, RESEARCH_LEAD
from ..infrastructure.client_knowledge_repository import ClientKnowledgeRepository
from ..infrastructure.prompt_repository import PromptResolver
from ..infrastructure.researcher_lead_repository import (
    LeadAlreadyHatched,
    LeadNotHatched,
    ResearcherLeadRepository,
)
from ..infrastructure.scope_repository import ScopeRepository
from ..infrastructure.study_design_repository import StudyDesignRepository
from ..infrastructure.study_lead_repository import StudyLeadRepository
from ..infrastructure.study_workspace_repository import (
    StudyWorkspaceRepository,
    WorkspaceConflict,
)
from ..infrastructure.workflow_repository import WorkflowRepository
from .research import CostCeilingUnknown, CostConfirmationRequired, ResearchAgentJobs
from .workflows import start_workflow

__all__ = [
    "GREETING_WINDOW",
    "LeadAlreadyHatched",
    "LeadBusy",
    "LeadContextTooLarge",
    "LeadEditsStale",
    "LeadNotHatched",
    "LeadProfile",
    "LeadRejected",
    "LeadSelfUpdateDecided",
    "LeadSelfUpdateNone",
    "LeadTurnNotFound",
    "LeadTurnNotReady",
    "LeadUnavailable",
    "NotAPaidRequest",
    "ResearchLead",
    "WorkspaceConflict",
]

#: A greeting within this long of the Lead's last turn is a no-op: the Lead has spoken.
GREETING_WINDOW: Final = timedelta(hours=8)
#: The research runs a turn is shown, newest first.
RUNS_IN_CONTEXT: Final = 5
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


class LeadBusy(Exception):
    """A Lead turn of this researcher in this Study is queued or running."""

    reason = "lead_busy"


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
    """Whether a Lead turn holds the conversation: queued, running, or parked on the study's
    budget. A turn waiting for budget is paid for when the budget is lifted, so a message sent
    meanwhile would queue a second paid turn behind it. A turn parked for any other reason
    (the Lead not configured, the route refusing) does not hold it: nothing would ever free it.
    """
    return turn["actor"] == "lead" and (
        turn["status"] in ("QUEUED", "RUNNING") or turn["awaiting_budget"]
    )


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


@dataclass(frozen=True, slots=True)
class ResearchLead:
    """The calling researcher's Lead conversation in the Study in scope."""

    session: Session
    scope: StudyContext
    #: The API's ``ai_research_lead_enabled``: off, a message is refused, never queued.
    enabled: bool = False
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
        views = []
        for turn in turns:
            run = runs.get(turn.run_id) if turn.run_id else None
            step_id = run["steps"][0]["step_id"] if run and run.get("steps") else None
            views.append(
                _view(
                    turn,
                    run=run,
                    last=last.get(step_id) if step_id else None,
                    decisions=decisions.get(turn.turn_id),
                )
            )
        return views

    def state(self, *, limit: int = 100) -> dict[str, Any]:
        """This researcher's conversation in the Study, oldest first, and whether a Lead turn
        is queued or running (``busy``)."""
        turns = self._annotated(self._turns().turns(limit=limit))
        busy = any(_holds(t) for t in turns)
        return {"busy": busy, "turns": turns}

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
        no turns. The researcher's Lead row is locked first, so two posts at once (two tabs
        opening the Study) are decided one after the other: one greeting, never two.
        Returns the turns stored, as :meth:`state` reads them.
        """
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
        if latest is not None:
            current = self._annotated([latest])[0]
            if _holds(current):
                raise LeadBusy("the Lead is still answering your last message")

        history = self._annotated(turns.turns(limit=50))
        content, analysis, workspace_revision = self._working_content()
        project_id, design_revision = self._design_project(content, workspace_revision)
        stored: list[LeadTurn] = []
        person: LeadTurn | None = None
        if kind == "message":
            person = turns.append(
                actor="person",
                kind=kind,
                stage=stage,
                text=message,
                focus=focus_,
                workspace_revision=workspace_revision,
                design_revision_id=design_revision.revision_id,
            )
            stored.append(person)

        context = self._freeze(
            lead=lead,
            history=history,
            kind=kind,
            stage=stage,
            focus=focus_,
            message=message,
            content=content,
            analysis=analysis,
            workspace_revision=workspace_revision,
            design_revision_id=design_revision.revision_id,
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
                "person_turn_id": person.turn_id if person else None,
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
        stored.append(
            turns.append(
                turn_id=lead_turn_id,
                actor="lead",
                kind=kind,
                stage=stage,
                focus=focus_,
                run_id=started.run_id,
                workspace_revision=workspace_revision,
                design_revision_id=design_revision.revision_id,
            )
        )
        return self._annotated(stored)

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
        cannot take is ``refused`` with its reason and stays undecided. An edit already
        decided keeps its first decision. A dismiss writes the ledger rows only.

        ``auto``: the accept is the researcher's standing choice, not a click (plan
        inline-decisions chunk 2). It is an accept, refused unless the caller's own Lead has
        ``auto_accept_text_edits`` on (``auto_accept_off``); an edit that is not a text edit
        (:func:`~aia_core.domain.research_lead.is_text_edit`) is ``refused`` as
        ``not_a_text_edit`` and stays undecided; each row it writes says ``"auto": true``.
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
        if decision == "accept" and base_revision != current:
            raise LeadEditsStale(current)
        content: dict[str, Any] = (
            dict(working.content) if working.content is not None else research_template()
        )
        analysis: dict[str, Any] | None = working.analysis
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
            applied = apply_edit(content, analysis, output.edits[index])
            if isinstance(applied, Refused):
                results[index] = {"index": index, "status": "refused", "reason": applied.reason}
                continue
            content, analysis = applied
            pending.append(index)

        revision, revision_id = current, working.revision_id
        if decision == "accept" and pending:
            saved = workspace.save(
                self.scope,
                content=content,
                analysis=analysis,
                base_revision=current,
                reason="lead_edit_accepted",
            )
            revision, revision_id = saved.revision, saved.revision_id
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
    ) -> dict[str, Any]:
        """A person approves the paid job a Lead turn prepared, and it starts (ADR 0026
        decision 7).

        Needs ``EDIT_STUDY``, ``RUN_WORKFLOW`` and ``APPROVE_GATE`` on an open Study, and the
        caller's own completed Lead turn whose request is an ``agent_job``; any other request
        only opens a stage (:class:`NotAPaidRequest`). Its ceiling is the design job's
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
        turn, output = self._completed(turn_id)
        assert turn.run_id is not None
        request = output.request
        if not isinstance(request, AgentJobRequest):
            raise NotAPaidRequest("this turn prepared no paid job")
        self._turns().lock()
        workflows = self._workflows()
        approved = workflows.lead_decisions([turn_id]).get(turn_id, {}).get("request")
        if approved:
            jobs = ResearchAgentJobs(self.session, self.scope)
            run = jobs.get(str(approved["run_id"]))
            return {
                "run_id": run["run_id"],
                "design_revision_id": run["metadata"]["design_revision_id"],
                "status": run["status"].value,
            }

        spend: dict[str, float] | None = None
        limit = ScopeRepository(self.session).get_study(self.scope).spend_confirm_usd
        if limit is not None:
            if reservation_usd is None:
                raise CostCeilingUnknown(
                    CeilingUnknown.RESEARCH_RESERVATION_MISSING, limit_usd=limit
                )
            if reservation_usd >= limit:
                if confirm_cost_usd is None or confirm_cost_usd < reservation_usd:
                    raise CostConfirmationRequired(ceiling_usd=reservation_usd, limit_usd=limit)
                spend = {
                    "ceiling_usd": reservation_usd,
                    "limit_usd": limit,
                    "confirmed_usd": confirm_cost_usd,
                }

        content, _analysis, workspace_revision = self._working_content()
        revision = self._submit_design(
            content,
            workspace_revision,
            source_stage=_SOURCE_STAGE.get(request.action, "questionnaire"),
        )
        started = ResearchAgentJobs(self.session, self.scope).start(
            design_revision_id=revision.revision_id,
            action=request.action,
            instruction=request.why,
        )
        workflows.record_lead_job_approval(
            turn.run_id,
            turn_id=turn_id,
            agent_run_id=started.run_id,
            design_revision_id=revision.revision_id,
            action=request.action.value,
            spend=spend,
        )
        return {
            "run_id": started.run_id,
            "design_revision_id": revision.revision_id,
            "status": started.run["status"].value,
        }

    # -- helpers ----------------------------------------------------------------

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
        focus_ = None
        if focus is not None:
            focus_ = {"id": str(focus.get("id") or ""), "label": str(focus.get("label") or "")}
            if not FOCUS_ID.fullmatch(focus_["id"]):
                raise LeadRejected(
                    "a focus names an element: question:, section:, brief: or plan: and an id",
                    reason="invalid_lead_turn",
                )
        return message, focus_

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
    ) -> dict[str, Any]:
        s = self.scope
        prompt = PromptResolver(self.session, s.organization_id).pin_for(LEAD_PROMPT_ID)
        notes: list[LeadNote] = ResearcherLeadRepository(self.session, s).notes_for_study()
        knowledge, omitted = knowledge_entries(ClientKnowledgeRepository(self.session).for_study(s))
        scopes = ScopeRepository(self.session)
        study = scopes.get_study(s)
        client = scopes.client_of_study(s)
        project_id = StudyDesignRepository(self.session, s).project_id()
        runs = (
            self._workflows().list_runs(
                project_id=project_id, workflow_type=RESEARCH, limit=RUNS_IN_CONTEXT
            )
            if project_id is not None
            else []
        )
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
            },
            runs=[
                {
                    "run_id": r["run_id"],
                    "status": r["status"].value,
                    "design_revision_id": r["metadata"].get("design_revision_id"),
                }
                for r in runs
            ],
            view={"kind": kind, "stage": stage, "focus": focus, "message": message},
            conversation=_conversation(history),
        )


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
            return {"hatched": False, "lead": None}
        return {"hatched": True, "lead": _profile(lead, repo.active_notes())}

    def hatch(self) -> dict[str, Any]:
        repo = ResearcherLeadRepository(self.session, self.scope)
        lead = repo.hatch()
        return {"hatched": True, "lead": _profile(lead, repo.active_notes())}

    def set_preferences(self, *, auto_accept_text_edits: bool) -> dict[str, Any]:
        """The caller sets their own Lead's preferences (plan inline-decisions chunk 2): the
        standing choice to have its text edits accepted without a click. Audited."""
        repo = ResearcherLeadRepository(self.session, self.scope)
        lead = repo.set_preferences(auto_accept_text_edits=auto_accept_text_edits)
        return {"hatched": True, "lead": _profile(lead, repo.active_notes())}


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
